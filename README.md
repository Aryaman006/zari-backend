# Zari & Jasi Backend API

Production-grade, high-performance REST API built using FastAPI, SQLAlchemy, and PostgreSQL. Serves as the central backend API for the Zari & Jasi fashion e-commerce platform.

---

## Technical Stack
- **FastAPI**: Modern, fast web framework for building APIs.
- **SQLAlchemy (Async)**: SQL toolkit and Object-Relational Mapper (ORM).
- **PostgreSQL**: Production relational database (fully compatible with Supabase).
- **Alembic**: Database migrations management.
- **WeasyPrint**: HTML-to-PDF invoice generation engine.

---

## Directory Structure
This service is fully self-contained and can be built, run, and deployed independently of the frontends.

```
/backend
├── app/                  # Application source code
│   ├── api/              # API endpoints (v1 routes)
│   ├── core/             # Configuration, database setup, dependencies, security
│   ├── models/           # SQLAlchemy models
│   ├── repositories/     # Data access patterns
│   ├── schemas/          # Pydantic validation schemas
│   ├── services/         # Business logic (Storage, Invoices, Orders, Shipping)
│   └── templates/        # Jinja2 HTML templates (invoices)
├── alembic/              # Database migration scripts
├── Dockerfile            # Production Docker image configuration
└── requirements.txt      # Python dependencies
```

---

## Environment Variables Configuration

Copy `.env.example` from the root of the project to `backend/.env` and configure:

### 1. App Configuration
- `APP_NAME`: Name of the application (e.g. `Zari & Jasi`)
- `APP_ENV`: Deployment environment (`development` | `production`)
- `DEBUG`: Enable debug endpoints and detailed logging (`true` | `false`)
- `SECRET_KEY`: Internal application key (`openssl rand -hex 32`)

### 2. Database Integration
- `DATABASE_URL`: Primary application connection pooler URL (Port 6543, Transaction mode for Supabase/PgBouncer)
  - Format: `postgresql+asyncpg://user:password@host:6543/dbname`
- `DATABASE_DIRECT_URL`: Direct database connection URL (Port 5432) for running migrations. Bypasses connection poolers to support DDL operations.
  - Format: `postgresql+asyncpg://user:password@host:5432/dbname`
- `DATABASE_POOL_SIZE`: Connection pool size limit (default: `5` to prevent Supabase connection exhaustion)
- `DATABASE_MAX_OVERFLOW`: Max overflow connections allowed (default: `10`)

### 3. JWT Security
- `JWT_SECRET_KEY`: Signing key for JWT tokens (`openssl rand -hex 32`)
- `JWT_ALGORITHM`: Signature hashing algorithm (default: `HS256`)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Expiry duration for access tokens (default: `60`)

### 4. Storage Providers (Supabase Storage)
- `STORAGE_BACKEND`: Storage driver to use (`local` | `supabase`)
- `SUPABASE_URL`: Supabase Project REST API URL (e.g. `https://abcdef.supabase.co`)
- `SUPABASE_SERVICE_ROLE_KEY`: Service role JWT token (bypass policies, never expose to frontends)
- `SUPABASE_STORAGE_BUCKET`: Default fallback bucket (e.g. `zari-assets`)

#### Multi-Bucket Setup:
For production (`STORAGE_BACKEND=supabase`), ensure the following buckets are configured in your Supabase Dashboard:
- **Public Buckets**:
  - `product-images`: Product catalog images
  - `category-images`: Category icons/banners
  - `brand-images`: Designer brand logo files
  - `banners`: Homepage promo slider images
- **Private Buckets**:
  - `invoices`: Order tax invoice PDFs (strictly protected)
  - `user-uploads`: Secure customer profile avatars

### 5. Razorpay Payments
- `RAZORPAY_KEY_ID`: Integration public key id
- `RAZORPAY_KEY_SECRET`: Integration secret key
- `RAZORPAY_WEBHOOK_SECRET`: Secure payload verification token

### 6. Email (Resend)
- `RESEND_API_KEY`: API authorization key
- `RESEND_FROM_EMAIL`: Authorized sender email address

### 7. CORS Allowed Origins
- `CUSTOMER_FRONTEND_URL`: URL of the Customer Frontend (Vercel)
- `ADMIN_FRONTEND_URL`: URL of the Admin Frontend (Vercel)

---

## Local Development Setup

### 1. Prerequisite Setup
Ensure Python 3.12+ and PostgreSQL are installed.

### 2. Create Virtual Environment
```bash
# Navigate to the backend directory
cd backend

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Database Migrations
Make sure `DATABASE_URL` is set in your `backend/.env` file.
```bash
# Run migrations using Alembic
alembic upgrade head
```

### 4. Start Development Server
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
API Documentation will be available locally at `http://localhost:8000/api/docs`.

---

## Docker Deployment (Render)

The backend is packaged into a minimal production-hardened Docker image running **Gunicorn** with **Uvicorn workers** and preloaded memory configuration.

To test the Docker image locally:
```bash
# Build the image
docker build -t zari-backend .

# Run the container
docker run -p 8000:8000 --env-file .env zari-backend
```
For production deployment guides, refer to `/docs/deploy-backend.md`.
