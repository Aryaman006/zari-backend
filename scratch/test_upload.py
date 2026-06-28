import asyncio
import sys
sys.path.insert(0, '.')
from app.services.storage_service import storage_service
import httpx

async def main():
    print("Active storage backend:", storage_service.backend_name)
    # A tiny 1x1 transparent PNG bytes:
    png_bytes = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xfc\xcf\xc0\x00\x00\x03\x01\x01\x00\x18\xdd\x8d\xb0\x00\x00\x00\x00IEND\xaeB`\x82'
    key = "products/test-product/test-file.png"
    try:
        url = await storage_service.upload_bytes(
            key=key,
            data=png_bytes,
            content_type="image/png"
        )
        print("Upload successful!")
        print("Returned URL:", url)
    except httpx.HTTPStatusError as e:
        print("HTTP Status Error!")
        print("Status Code:", e.response.status_code)
        print("Response Text:", e.response.text)
    except Exception as e:
        import traceback
        print("Upload failed!")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
