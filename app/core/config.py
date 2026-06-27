from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
import secrets


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "Zari & Jasi"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = secrets.token_urlsafe(32)
    API_V1_PREFIX: str = "/api/v1"

    # CORS origins — always includes localhost for dev.
    # In production, set CUSTOMER_FRONTEND_URL and ADMIN_FRONTEND_URL
    # to your Vercel domains and they will be auto-added.
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]

    # ── Database ─────────────────────────────────────────
    # DATABASE_URL: Used at runtime by the FastAPI app (connection pooler for Supabase).
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/zari_db"
    # DATABASE_DIRECT_URL: Used ONLY by Alembic migrations.
    # For Supabase: set to the direct (non-pooled) connection URL (port 5432).
    # This bypasses PgBouncer, which is required for DDL operations.
    # If not set, falls back to DATABASE_URL.
    DATABASE_DIRECT_URL: Optional[str] = None

    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # ── JWT ──────────────────────────────────────────────
    JWT_SECRET_KEY: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    JWT_EMAIL_VERIFY_EXPIRE_HOURS: int = 24
    JWT_PASSWORD_RESET_EXPIRE_HOURS: int = 1

    # ── Email (Resend) ────────────────────────────────────
    RESEND_API_KEY: Optional[str] = None
    RESEND_FROM_EMAIL: Optional[str] = None
    EMAIL_FROM: str = "noreply@yourdomain.com"
    EMAIL_FROM_NAME: str = "Zari & Jasi"

    # ── Storage ───────────────────────────────────────────
    # "local"    = local filesystem (default — dev/test, no credentials needed)
    # "supabase" = Supabase Storage (production — requires SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY)
    # "r2"       = Cloudflare R2 (legacy — requires R2_* credentials)
    STORAGE_BACKEND: str = "local"
    LOCAL_UPLOADS_DIR: str = "uploads"
    BACKEND_URL: str = "http://localhost:8000"

    # ── Supabase ──────────────────────────────────────────
    # Used for both Database (via DATABASE_URL) and Storage.
    SUPABASE_URL: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_STORAGE_BUCKET: str = "zari-assets"
    # Signed URL expiry for private assets (invoices, etc.)
    SUPABASE_SIGNED_URL_EXPIRE: int = 3600  # 1 hour

    # ── Cloudflare R2 (legacy) ────────────────────────────
    R2_ACCOUNT_ID: Optional[str] = None
    R2_ACCESS_KEY_ID: Optional[str] = None
    R2_SECRET_ACCESS_KEY: Optional[str] = None
    R2_BUCKET_NAME: str = "zari-assets"
    R2_PUBLIC_URL: Optional[str] = None
    R2_PRESIGNED_URL_EXPIRE: int = 3600

    # ── Razorpay ──────────────────────────────────────────
    RAZORPAY_KEY_ID: Optional[str] = None
    RAZORPAY_KEY_SECRET: Optional[str] = None
    RAZORPAY_WEBHOOK_SECRET: Optional[str] = None
    RAZORPAY_CURRENCY: str = "INR"

    # ── GST / Business ───────────────────────────────────
    GSTIN: str = "22AAAAA0000A1Z5"
    BUSINESS_NAME: str = "Zari & Jasi"
    BUSINESS_ADDRESS: str = "123 Fashion Street, Mumbai, Maharashtra - 400001"
    STORE_PHONE: str = ""
    CGST_RATE: float = 0.09   # 9%
    SGST_RATE: float = 0.09   # 9%

    # ── COD ───────────────────────────────────────────────
    COD_ENABLED: bool = True
    COD_MAX_AMOUNT: float = 5000.0

    # ── Frontend URLs (also used for CORS) ───────────────
    CUSTOMER_FRONTEND_URL: str = "http://localhost:3000"
    ADMIN_FRONTEND_URL: str = "http://localhost:3001"

    # ── Computed Properties ───────────────────────────────

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def effective_email_from(self) -> str:
        """Return the best available FROM email address."""
        return self.RESEND_FROM_EMAIL or self.EMAIL_FROM

    @property
    def use_local_storage(self) -> bool:
        """Returns True when local file storage should be used."""
        return self.STORAGE_BACKEND == "local"

    @property
    def cors_origins(self) -> list[str]:
        """
        Build the full CORS origin list.
        Always includes localhost for dev. In production, adds the
        CUSTOMER_FRONTEND_URL and ADMIN_FRONTEND_URL values.
        """
        origins = set(self.ALLOWED_ORIGINS)
        if self.CUSTOMER_FRONTEND_URL:
            origins.add(self.CUSTOMER_FRONTEND_URL.rstrip("/"))
        if self.ADMIN_FRONTEND_URL:
            origins.add(self.ADMIN_FRONTEND_URL.rstrip("/"))
        return list(origins)

    @property
    def alembic_database_url(self) -> str:
        """
        URL for Alembic migrations. Uses DATABASE_DIRECT_URL if set
        (required for Supabase to bypass PgBouncer during DDL).
        Falls back to DATABASE_URL.
        """
        return self.DATABASE_DIRECT_URL or self.DATABASE_URL


settings = Settings()
