import asyncio
import httpx
import sys
sys.path.insert(0, '.')
from app.core.config import settings

async def main():
    headers = {
        'Authorization': f'Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}',
        'apikey': settings.SUPABASE_SERVICE_ROLE_KEY,
        'Content-Type': 'application/json'
    }
    buckets = ["product-images", "category-images", "brand-images", "banners"]
    
    for bucket in buckets:
        url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/bucket/{bucket}"
        payload = {
            "id": bucket,
            "name": bucket,
            "public": True,
            "allowed_mime_types": ["image/jpeg", "image/png", "image/jpg", "image/webp", "image/gif"],
            "file_size_limit": 52428800
        }
        async with httpx.AsyncClient() as client:
            resp = await client.put(url, headers=headers, json=payload)
            print(f"Bucket {bucket} update status:", resp.status_code)
            if resp.status_code != 200:
                print("Error:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
