"""
Storage service abstraction layer.

Supports three backends:
  - LocalStorageService    : saves files to the local uploads/ directory (default / dev)
  - SupabaseStorageService : uploads files to Supabase Storage via REST API (production)
  - R2StorageService       : uploads files to Cloudflare R2 via boto3 S3-compatible API (legacy)

The active backend is determined by settings.STORAGE_BACKEND:
  "local"    → LocalStorageService    (no credentials needed)
  "supabase" → SupabaseStorageService (requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
  "r2"       → R2StorageService       (requires R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)

The module-level `storage_service` singleton is created by `_create_storage_service()`
which reads settings at import time. Swap backends by changing STORAGE_BACKEND in .env
and restarting the server — no code changes required.
"""
import logging
import mimetypes
import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Abstract Interface ────────────────────────────────────────────────────────

class BaseStorageService(ABC):
    """Abstract storage backend. Implement this interface to add new backends."""

    @abstractmethod
    async def generate_upload_url(
        self,
        folder: str,
        filename: str,
        content_type: Optional[str] = None,
        expires_in: int = 3600,
        bucket: Optional[str] = None,
    ) -> dict:
        """
        Return upload metadata.
        For local storage: returns a POST endpoint URL.
        For Supabase/R2: returns a presigned PUT URL.

        Returns: { upload_url, key, public_url }
        """

    @abstractmethod
    async def generate_download_url(
        self,
        key: str,
        expires_in: int = 3600,
        bucket: Optional[str] = None,
    ) -> str:
        """Return a URL to download/access the stored object."""

    @abstractmethod
    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: Optional[str] = None,
    ) -> str:
        """Upload raw bytes and return the public URL."""

    @abstractmethod
    async def delete_object(self, key: str, bucket: Optional[str] = None) -> None:
        """Delete a stored object."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """Human-readable backend identifier."""


# ── Local File Storage Backend ────────────────────────────────────────────────

class LocalStorageService(BaseStorageService):
    """
    Stores files in the local filesystem under settings.LOCAL_UPLOADS_DIR.
    Files are served at {BACKEND_URL}/uploads/{key}.

    For direct browser uploads, the frontend should POST the file to
    /api/v1/uploads/direct with form-data, and receive back the public URL.
    The generate_upload_url() method returns a local API endpoint URL.
    """

    def __init__(self):
        self._uploads_dir: Optional[Path] = None

    @property
    def uploads_dir(self) -> Path:
        if self._uploads_dir is None:
            path = Path(settings.LOCAL_UPLOADS_DIR)
            if not path.is_absolute():
                # Resolve relative to the backend working directory
                path = Path.cwd() / path
            path.mkdir(parents=True, exist_ok=True)
            self._uploads_dir = path
        return self._uploads_dir

    def _public_url(self, key: str) -> str:
        return f"{settings.BACKEND_URL.rstrip('/')}/uploads/{key}"

    def _file_path(self, key: str) -> Path:
        return self.uploads_dir / key.replace("/", os.sep)

    async def generate_upload_url(
        self,
        folder: str,
        filename: str,
        content_type: Optional[str] = None,
        expires_in: int = 3600,
        bucket: Optional[str] = None,
    ) -> dict:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        key = f"{folder}/{uuid4().hex}.{ext}"
        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        # Return a local upload endpoint URL — frontend posts file here
        upload_url = f"{settings.BACKEND_URL.rstrip('/')}/api/v1/uploads/direct?key={key}"
        return {
            "upload_url": upload_url,
            "key": key,
            "public_url": self._public_url(key),
        }

    async def generate_download_url(self, key: str, expires_in: int = 3600, bucket: Optional[str] = None) -> str:
        """For local storage, the download URL is just the public URL."""
        return self._public_url(key)

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: Optional[str] = None,
    ) -> str:
        file_path = self._file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        logger.info(f"[LocalStorage] Saved {len(data)} bytes → {file_path}")
        return self._public_url(key)

    async def delete_object(self, key: str, bucket: Optional[str] = None) -> None:
        file_path = self._file_path(key)
        if file_path.exists():
            file_path.unlink()
            logger.info(f"[LocalStorage] Deleted {file_path}")

    def save_upload(self, key: str, data: bytes) -> str:
        """Synchronous helper used by the upload endpoint."""
        file_path = self._file_path(key)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        return self._public_url(key)

    @property
    def backend_name(self) -> str:
        return "local"


# ── Supabase Storage Backend ──────────────────────────────────────────────────

class SupabaseStorageService(BaseStorageService):
    """
    Uploads files to Supabase Storage via its REST API using httpx.

    Supports Multi-Bucket Architecture:
      Public Buckets:
        - product-images (for products/ folder)
        - category-images (for categories/ folder)
        - brand-images (for brands/ folder)
        - banners (for banners/ folder)
      Private Buckets:
        - invoices (for invoices/ folder)
        - user-uploads (for user avatars, avatars/ folder)

    The bucket is resolved dynamically based on the key or folder prefix if not passed explicitly.
    """

    def __init__(self):
        self._base_url = (settings.SUPABASE_URL or "").rstrip("/")
        self._service_key = settings.SUPABASE_SERVICE_ROLE_KEY or ""

        if not self._base_url or not self._service_key:
            raise ValueError(
                "SupabaseStorageService requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY to be set in environment."
            )

    def _get_bucket(self, key_or_folder: str, bucket: Optional[str] = None) -> str:
        """Resolve the bucket name based on folder/key prefix or direct input."""
        if bucket:
            return bucket
        path_str = key_or_folder.lower().replace("\\", "/").lstrip("/")
        if path_str.startswith("products/") or path_str.startswith("product/"):
            return "product-images"
        elif path_str.startswith("categories/") or path_str.startswith("category/"):
            return "category-images"
        elif path_str.startswith("brands/") or path_str.startswith("brand/"):
            return "brand-images"
        elif path_str.startswith("banners/") or path_str.startswith("banner/"):
            return "banners"
        elif path_str.startswith("invoices/") or path_str.startswith("invoice/"):
            return "invoices"
        elif path_str.startswith("avatars/") or path_str.startswith("avatar/") or path_str.startswith("user-uploads/"):
            return "user-uploads"
        
        raise ValueError(
            f"Could not resolve Supabase Storage bucket for path '{key_or_folder}'. "
            "Please configure a valid prefix or pass an explicit bucket name."
        )

    def _auth_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._service_key}",
            "apikey": self._service_key,
        }

    def _object_url(self, key: str, bucket: str) -> str:
        """Internal REST URL for a storage object."""
        return f"{self._base_url}/storage/v1/object/{bucket}/{key}"

    def _public_url(self, key: str, bucket: str) -> str:
        """
        Returns the public CDN URL for an object.
        NOTE: Only works if the bucket has public access enabled.
        For private buckets, use generate_download_url() instead.
        """
        return f"{self._base_url}/storage/v1/object/public/{bucket}/{key}"

    async def generate_upload_url(
        self,
        folder: str,
        filename: str,
        content_type: Optional[str] = None,
        expires_in: int = 3600,
        bucket: Optional[str] = None,
    ) -> dict:
        """
        Create a signed upload URL that allows the browser to upload
        directly to Supabase Storage without exposing the service role key.

        Returns: { upload_url, key, public_url }
        """
        import httpx

        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        key = f"{folder}/{uuid4().hex}.{ext}"
        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

        resolved_bucket = self._get_bucket(folder, bucket)
        sign_url = f"{self._base_url}/storage/v1/object/sign/{resolved_bucket}/{key}"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                sign_url,
                headers=self._auth_headers(),
                json={"expiresIn": expires_in},
            )
            resp.raise_for_status()
            data = resp.json()

        # Supabase returns { signedURL: "/storage/v1/object/sign/..." }
        signed_path = data.get("signedURL", "")
        upload_url = (
            f"{self._base_url}{signed_path}"
            if signed_path.startswith("/")
            else signed_path
        )

        return {
            "upload_url": upload_url,
            "key": key,
            "public_url": self._public_url(key, resolved_bucket),
        }

    async def generate_download_url(self, key: str, expires_in: int = 3600, bucket: Optional[str] = None) -> str:
        """
        Create a signed download URL for private objects (e.g. invoices).
        The URL expires after `expires_in` seconds.
        """
        import httpx

        resolved_bucket = self._get_bucket(key, bucket)
        sign_url = f"{self._base_url}/storage/v1/object/sign/{resolved_bucket}/{key}"

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                sign_url,
                headers=self._auth_headers(),
                json={"expiresIn": expires_in},
            )
            resp.raise_for_status()
            data = resp.json()

        signed_path = data.get("signedURL", "")
        if signed_path.startswith("/"):
            return f"{self._base_url}{signed_path}"
        return signed_path

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: Optional[str] = None,
    ) -> str:
        """
        Upload raw bytes directly to Supabase Storage using the service role key.
        Used for server-side uploads (e.g. generated invoice PDFs).
        Returns the public CDN URL.
        """
        import httpx

        resolved_bucket = self._get_bucket(key, bucket)
        url = self._object_url(key, resolved_bucket)
        headers = {
            **self._auth_headers(),
            "Content-Type": content_type,
            "x-upsert": "true",  # Overwrite if key already exists
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, content=data)
            resp.raise_for_status()

        logger.info(f"[SupabaseStorage] Uploaded {len(data)} bytes → {key} in bucket {resolved_bucket}")
        return self._public_url(key, resolved_bucket)

    async def delete_object(self, key: str, bucket: Optional[str] = None) -> None:
        """Delete an object from Supabase Storage."""
        import httpx

        resolved_bucket = self._get_bucket(key, bucket)
        url = f"{self._base_url}/storage/v1/object/{resolved_bucket}"
        async with httpx.AsyncClient() as client:
            resp = await client.delete(
                url,
                headers=self._auth_headers(),
                json={"prefixes": [key]},
            )
            if resp.status_code not in (200, 204, 404):
                logger.error(f"[SupabaseStorage] Failed to delete {key} from bucket {resolved_bucket}: {resp.text}")
            else:
                logger.info(f"[SupabaseStorage] Deleted {key} from bucket {resolved_bucket}")

    @property
    def backend_name(self) -> str:
        return "supabase"


# ── Cloudflare R2 Backend (legacy) ───────────────────────────────────────────

class R2StorageService(BaseStorageService):
    """
    Uploads files to Cloudflare R2 using the boto3 S3-compatible API.
    Requires: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY in settings.
    """

    def __init__(self):
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import boto3
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.r2_endpoint_url,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                region_name="auto",
            )
        return self._client

    def _public_url(self, key: str) -> str:
        if settings.R2_PUBLIC_URL:
            return f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
        return f"{settings.r2_endpoint_url}/{settings.R2_BUCKET_NAME}/{key}"

    async def generate_upload_url(
        self,
        folder: str,
        filename: str,
        content_type: Optional[str] = None,
        expires_in: int = 3600,
        bucket: Optional[str] = None,
    ) -> dict:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
        key = f"{folder}/{uuid4().hex}.{ext}"
        if not content_type:
            content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        
        target_bucket = bucket or settings.R2_BUCKET_NAME
        upload_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": target_bucket,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in,
        )
        return {"upload_url": upload_url, "key": key, "public_url": self._public_url(key)}

    async def generate_download_url(self, key: str, expires_in: int = 3600, bucket: Optional[str] = None) -> str:
        target_bucket = bucket or settings.R2_BUCKET_NAME
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": target_bucket, "Key": key},
            ExpiresIn=expires_in,
        )

    async def upload_bytes(
        self,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        bucket: Optional[str] = None,
    ) -> str:
        target_bucket = bucket or settings.R2_BUCKET_NAME
        self.client.put_object(
            Bucket=target_bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return self._public_url(key)

    async def delete_object(self, key: str, bucket: Optional[str] = None) -> None:
        target_bucket = bucket or settings.R2_BUCKET_NAME
        try:
            self.client.delete_object(Bucket=target_bucket, Key=key)
        except Exception as e:
            logger.error(f"Failed to delete R2 object {key} from bucket {target_bucket}: {e}")

    @property
    def backend_name(self) -> str:
        return "r2"


# ── Factory ───────────────────────────────────────────────────────────────────

def _create_storage_service() -> BaseStorageService:
    """
    Create the appropriate storage backend based on settings.STORAGE_BACKEND.

    Priority:
      supabase → SupabaseStorageService (production recommended)
      r2       → R2StorageService       (legacy)
      local    → LocalStorageService    (default / dev)
    """
    backend = settings.STORAGE_BACKEND.lower()

    if backend == "supabase":
        if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY:
            logger.info("Storage backend: Supabase Storage")
            return SupabaseStorageService()
        else:
            logger.warning(
                "STORAGE_BACKEND=supabase but SUPABASE_URL or "
                "SUPABASE_SERVICE_ROLE_KEY is not set. "
                "Falling back to local file storage."
            )

    elif backend == "r2":
        if settings.R2_ACCOUNT_ID:
            logger.info("Storage backend: Cloudflare R2")
            return R2StorageService()
        else:
            logger.warning(
                "STORAGE_BACKEND=r2 but R2_ACCOUNT_ID is not set. "
                "Falling back to local file storage."
            )

    logger.info(f"Storage backend: Local filesystem ({settings.LOCAL_UPLOADS_DIR}/)")
    return LocalStorageService()


# ── Module-level singleton ────────────────────────────────────────────────────
storage_service: BaseStorageService = _create_storage_service()
