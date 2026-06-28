import asyncio
import httpx
import sys
import json
sys.path.insert(0, '.')
from app.core.config import settings

async def main():
    headers = {
        'Authorization': f'Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}',
        'apikey': settings.SUPABASE_SERVICE_ROLE_KEY
    }
    url = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/bucket"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        if resp.status_code == 200:
            print(json.dumps(resp.json(), indent=2))
        else:
            print("Error:", resp.text)

if __name__ == "__main__":
    asyncio.run(main())
