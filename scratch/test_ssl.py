import asyncio
import asyncpg
import socket
import sys

# Monkeypatch socket.getaddrinfo to resolve pooler host to its IPv4 address
original_getaddrinfo = socket.getaddrinfo
def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    if host == "aws-0-ap-south-1.pooler.supabase.com":
        return original_getaddrinfo("3.108.251.216", port, family, type, proto, flags)
    return original_getaddrinfo(host, port, family, type, proto, flags)
socket.getaddrinfo = patched_getaddrinfo

async def main():
    host = "aws-0-ap-south-1.pooler.supabase.com"
    conn_str = f"postgresql://postgres.ckhsziwgycbamscvyxis:6289379872Test@{host}:5432/postgres"
    
    print("Testing connection with patched DNS resolver...")
    try:
        conn = await asyncpg.connect(conn_str)
        print("Success! Connected to database.")
        await conn.close()
    except Exception as e:
        print(f"Connection failed: {e}", file=sys.stderr)

if __name__ == "__main__":
    asyncio.run(main())
