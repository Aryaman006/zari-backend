import asyncio
import asyncpg
import sys

REGIONS = [
    "ap-south-1", "ap-southeast-1", "ap-southeast-2", "ap-northeast-1", "ap-northeast-2",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1",
    "us-east-1", "us-east-2", "us-west-1", "us-west-2",
    "ca-central-1", "sa-east-1"
]

async def test_region(region):
    host = f"aws-0-{region}.pooler.supabase.com"
    conn_str = f"postgresql://postgres.ckhsziwgycbamscvyxis:6289379872Test@{host}:5432/postgres"
    try:
        # 1-second timeout to check fast
        conn = await asyncio.wait_for(asyncpg.connect(conn_str), timeout=3.0)
        print(f"SUCCESS in region: {region} (host: {host})")
        await conn.close()
        return True
    except asyncio.TimeoutError:
        # Timeout means network exists but slow/blocked
        print(f"Timeout in region: {region}")
    except Exception as e:
        err_msg = str(e)
        if "tenant/user" not in err_msg:
            print(f"Region {region} error: {err_msg}")
    return False

async def main():
    print("Testing connection pooler across regions...")
    for region in REGIONS:
        found = await test_region(region)
        if found:
            print("Found correct region pooler!")
            break

if __name__ == "__main__":
    asyncio.run(main())
