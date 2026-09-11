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
    time.sleep(2)

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Test Index route
            async with session.get("http://localhost:8080/") as resp:
                print(f"Index status: {resp.status}")
                text = await resp.text()
                assert resp.status == 200, f"Expected 200, got {resp.status}"
                assert "Telegram Stream Engine" in text, "Header missing in HTML"
                print("[SUCCESS] Index page rendered successfully with rich UI!")

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
