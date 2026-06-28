import asyncio
import asyncpg
import sys

# List of IP addresses for poolers across regions
REGION_IPS = {
    "ap-south-1 (Mumbai)": "3.108.251.216",
    "ap-southeast-1 (Singapore)": "52.74.252.201",
    "us-east-1 (N. Virginia)": "52.45.94.125",
    "us-east-2 (Ohio)": "3.12.180.20",
    "us-west-1 (N. California)": "13.56.240.231",
    "us-west-2 (Oregon)": "35.88.225.109",
    "eu-west-1 (Ireland)": "52.215.228.163",
    "eu-west-2 (London)": "18.170.83.189",
    "eu-central-1 (Frankfurt)": "3.67.11.168",
    "ap-southeast-2 (Sydney)": "13.237.234.195"
}

async def test_ip(region_name, ip):
    conn_str = f"postgresql://postgres.ckhsziwgycbamscvyxis:6289379872Test@{ip}:5432/postgres"
    try:
        conn = await asyncio.wait_for(asyncpg.connect(conn_str), timeout=3.0)
        print(f"SUCCESS! Connected to {region_name}")
        await conn.close()
        return True
    except Exception as e:
        print(f"{region_name} IP {ip} error: {e}")
    return False

async def main():
    print("Testing connection to database using pooler IPs across regions...")
    for region_name, ip in REGION_IPS.items():
        await test_ip(region_name, ip)

if __name__ == "__main__":
    asyncio.run(main())
