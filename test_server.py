import asyncio
import aiohttp
import subprocess
import time
import sys

async def verify():
    # Start server in subprocess
    proc = subprocess.Popen(
        [sys.executable, "server.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    time.sleep(4)

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Test Index route (handles 302 redirect or 200)
            async with session.get("http://localhost:8080/", allow_redirects=False) as resp:
                print(f"Index status: {resp.status}")
                assert resp.status in (200, 302), f"Expected 200 or 302, got {resp.status}"
                print("[SUCCESS] Index route returned valid response!")

            # 2. Test Stream endpoint without Telegram client
            async with session.get("http://localhost:8080/stream/123.mp4") as resp:
                print(f"Stream status without bot: {resp.status}")
                assert resp.status == 503, f"Expected 503 (client not connected), got {resp.status}"
                print("[SUCCESS] Stream endpoint correctly handles non-connected Telegram client state!")

    finally:
        proc.terminate()
        proc.wait(timeout=5)
        print("Server process terminated cleanly.")

if __name__ == "__main__":
    asyncio.run(verify())
