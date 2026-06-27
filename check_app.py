
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

# Set dummy env vars
os.environ["DATABASE_URL"] = "postgresql+asyncpg://dummy:dummy@localhost:5432/dummy"
os.environ["SECRET_KEY"] = "test_secret_key_for_verification"
os.environ["APP_ENV"] = "development"

from app.main import app

print("OK: FastAPI app loaded successfully!")
print("\nRegistered Routers:")
for route in app.routes:
    if hasattr(route, "methods"):
        methods = ", ".join(sorted(route.methods))
        print(f"  [{methods:20}] {route.path}")
