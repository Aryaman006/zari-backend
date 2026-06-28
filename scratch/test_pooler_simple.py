import asyncio
import asyncpg
import sys

async def main():
    # Test port 5432 (session) and port 6543 (transaction) using the resolved IPv4 IP
    ip = "3.108.251.216"
    
    conn_str_5432 = f"postgresql://postgres.ckhsziwgycbamscvyxis:6289379872Test@{ip}:5432/postgres"
    print(f"Testing connection to pooler IP {ip} on port 5432...")
    try:
        conn = await asyncpg.connect(conn_str_5432)
        print("Success! Connected to port 5432.")
        await conn.close()
    except Exception as e:
        print(f"Port 5432 failed: {e}", file=sys.stderr)

    conn_str_6543 = f"postgresql://postgres.ckhsziwgycbamscvyxis:6289379872Test@{ip}:6543/postgres"
    print(f"\nTesting connection to pooler IP {ip} on port 6543...")
    try:
        conn = await asyncpg.connect(conn_str_6543)
        print("Success! Connected to port 6543.")
        await conn.close()
    except Exception as e:
        print(f"Port 6543 failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
