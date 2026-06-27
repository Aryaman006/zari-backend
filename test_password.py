
from app.core.security import verify_password, hash_password

test_hash = "$2b$12$UbbmKy1kKoke4..."
print("Testing password 'Admin@12345'...")
result = verify_password("Admin@12345", "$2b$12$UbbmKy1kKoke4dZ8M8HteO67Xw70Fy29oNcN5WjHj2y6F9l9pX7Wm")
print(f"Result: {result}")
