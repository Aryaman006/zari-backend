"""
Zari & Jasi — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

from fastapi import FastAPI, Request, UploadFile, File, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.core.config import settings
from app.api.v1 import auth, products, orders, customer, admin

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Rate Limiter ──────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"🚀 Starting {settings.APP_NAME} API [{settings.APP_ENV}]")
    logger.info(f"💾 Storage backend: {settings.STORAGE_BACKEND}")

    # ── Load persisted store settings from DB into memory ─────────────────────
    # This ensures settings saved via the admin panel (e.g. store name, tax rates)
    # are available immediately on startup, not just the .env defaults.
    try:
        from app.core.database import AsyncSessionLocal
        import json

        # Mapping of DB keys → settings attribute names
        SETTINGS_MAP = {
            "BUSINESS_NAME":          "BUSINESS_NAME",
            "EMAIL_FROM":             "EMAIL_FROM",
            "STORE_PHONE":            "STORE_PHONE",
            "BUSINESS_ADDRESS":       "BUSINESS_ADDRESS",
            "RAZORPAY_KEY_ID":        "RAZORPAY_KEY_ID",
            "RAZORPAY_KEY_SECRET":    "RAZORPAY_KEY_SECRET",
            "RAZORPAY_WEBHOOK_SECRET": "RAZORPAY_WEBHOOK_SECRET",
            "RESEND_API_KEY":         "RESEND_API_KEY",
            "RESEND_FROM_EMAIL":      "RESEND_FROM_EMAIL",
            "RAZORPAY_CURRENCY":      "RAZORPAY_CURRENCY",
            "CGST_RATE":              "CGST_RATE",
            "SGST_RATE":              "SGST_RATE",
        }

        async with AsyncSessionLocal() as session:
            from app.models.store_settings import StoreSetting
            from sqlalchemy import select
            result = await session.execute(select(StoreSetting))
            rows = result.scalars().all()
            loaded_count = 0
            for row in rows:
                if row.key in SETTINGS_MAP:
                    attr = SETTINGS_MAP[row.key]
                    try:
                        value = json.loads(row.value)
                        setattr(settings, attr, value)
                        loaded_count += 1
                    except Exception:
                        pass
            if loaded_count:
                logger.info(f"⚙️  Loaded {loaded_count} store settings from DB")
    except Exception as e:
        # Non-fatal: app starts fine with .env defaults if DB load fails
        logger.warning(f"Could not load store settings from DB (using .env defaults): {e}")

    # ── Ensure local uploads directory exists (local storage only) ────────────
    if settings.STORAGE_BACKEND == "local":
        uploads_path = Path(settings.LOCAL_UPLOADS_DIR)
        if not uploads_path.is_absolute():
            uploads_path = Path.cwd() / uploads_path
        uploads_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Uploads directory: {uploads_path}")

    yield
    logger.info("Shutting down...")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title=f"{settings.APP_NAME} API",
    description="Production-grade fashion e-commerce REST API",
    version="1.0.0",
    docs_url="/api/docs" if not settings.is_production else None,
    redoc_url="/api/redoc" if not settings.is_production else None,
    openapi_url="/api/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Use settings.cors_origins which dynamically includes CUSTOMER_FRONTEND_URL
# and ADMIN_FRONTEND_URL in addition to the hard-coded localhost origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


# ── Exception Handlers ────────────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = {}
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"] if loc != "body")
        errors[field] = error["msg"]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Validation failed", "errors": errors},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."},
    )


# ── Routes ────────────────────────────────────────────────────────────────────
PREFIX = settings.API_V1_PREFIX

app.include_router(auth.router, prefix=PREFIX)
app.include_router(products.router, prefix=PREFIX)
app.include_router(products.category_router, prefix=PREFIX)
app.include_router(products.admin_router, prefix=PREFIX)
app.include_router(products.admin_category_router, prefix=PREFIX)
app.include_router(orders.router, prefix=PREFIX)
app.include_router(orders.payment_router, prefix=PREFIX)
app.include_router(orders.admin_order_router, prefix=PREFIX)
app.include_router(orders.invoice_router, prefix=PREFIX)
app.include_router(customer.router, prefix=PREFIX)
app.include_router(admin.router, prefix=PREFIX)


# ── Direct File Upload Endpoint ──────────────────────────────────────────────
@app.post("/api/v1/uploads/direct", tags=["Uploads"])
async def direct_upload(key: str, file: UploadFile = File(...)):
    """
    Direct file upload endpoint.
    Uploads files to the active storage service backend (local, supabase, or r2).
    """
    from app.services.storage_service import storage_service
    data = await file.read()
    content_type = file.content_type or "application/octet-stream"
    
    public_url = await storage_service.upload_bytes(
        key=key,
        data=data,
        content_type=content_type
    )
    return {"key": key, "public_url": public_url, "size": len(data)}


# ── Static File Serving (local uploads only) ──────────────────────────────────
# Only mount the /uploads static route when using local storage.
# In production (Supabase/R2), files are served from the CDN directly.
def _mount_uploads():
    """Mount local uploads directory as static files (local storage only)."""
    uploads_path = Path(settings.LOCAL_UPLOADS_DIR)
    if not uploads_path.is_absolute():
        uploads_path = Path.cwd() / uploads_path
    uploads_path.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(uploads_path)), name="uploads")
    logger.info(f"📂 Mounted /uploads → {uploads_path}")


if settings.STORAGE_BACKEND == "local":
    _mount_uploads()


# ── Health Check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health_check():
    from app.services.storage_service import storage_service
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "storage_backend": storage_service.backend_name,
    }


@app.get("/", tags=["Root"])
async def root():
    return {"message": f"Welcome to {settings.APP_NAME} API", "docs": "/api/docs"}
