"""
Automated Verification Script for Telegram Mini App API and Frontend.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import aiohttp
from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import database
import server

async def run_tests():
    # Setup test app
    app = web.Application(middlewares=[server.cors_middleware])
    
    app.router.add_get("/app", server.handle_miniapp)
    app.router.add_get("/api/series", server.handle_api_get_series)
    app.router.add_post("/api/series", server.handle_api_create_series)
    app.router.add_get("/api/series/{id}", server.handle_api_get_series_detail)
    app.router.add_put("/api/series/{id}", server.handle_api_update_series)
    app.router.add_delete("/api/series/{id}", server.handle_api_delete_series)
    app.router.add_post("/api/series/{id}/episodes", server.handle_api_add_episode)
    app.router.add_put("/api/episodes/{id}", server.handle_api_update_episode)
    app.router.add_delete("/api/episodes/{id}", server.handle_api_delete_episode)
    app.router.add_get("/api/recent-media", server.handle_api_recent_media)
    app.router.add_get("/api/stats", server.handle_api_stats)

    runner = web.AppRunner(app)
    await runner.setup()
    test_port = 8189
    site = web.TCPSite(runner, "127.0.0.1", test_port)
    await site.start()

    base = f"http://127.0.0.1:{test_port}"
    print(f"Testing Telegram Mini App Server on {base}...")

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Test GET /app (Mini App HTML UI)
            async with session.get(f"{base}/app") as resp:
                assert resp.status == 200, f"Expected 200 for /app, got {resp.status}"
                html = await resp.text()
                assert "telegram-web-app.js" in html, "Telegram WebApp SDK missing"
                assert "Telegram Drama & Movie Manager" in html, "Page title missing"
                assert "id=\"modalDramaForm\"" in html, "Drama modal missing"
                print("✅ 1. GET /app passed: Telegram Mini App UI rendered successfully with WebApp SDK!")

            # 2. Test POST /api/series (Create Series)
            new_drama = {
                "title": "និស្ស័យស្នេហ៍ដាវទេព 2026",
                "type": "series",
                "genres": "រឿងភាគចិន, សកម្មភាព, មនោសញ្ចេតនា",
                "poster_url": "https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=800",
                "description": "សាច់រឿងនិទានអំពីយុវជនក្លាហានក្នុងពិភពគុន..."
            }
            async with session.post(f"{base}/api/series", json=new_drama) as resp:
                assert resp.status == 200
                res_data = await resp.json()
                assert res_data.get("success") is True
                series_id = res_data.get("id")
                assert series_id > 0
                print(f"✅ 2. POST /api/series passed: Created drama with ID={series_id}")

            # 3. Test GET /api/series (List with search)
            async with session.get(f"{base}/api/series?search=និស្ស័យស្នេហ៍") as resp:
                assert resp.status == 200
                res_data = await resp.json()
                items = res_data.get("series", [])
                assert any(s["id"] == series_id for s in items)
                print(f"✅ 3. GET /api/series passed: Search returned {len(items)} matching item(s)")

            # 4. Test POST /api/series/{id}/episodes (Add Episode)
            ep_data = {
                "episode_num": 1,
                "title": "ភាគ ០១",
                "msg_id": 9999,
                "stream_url": "http://example.com/stream/9999.mp4"
            }
            async with session.post(f"{base}/api/series/{series_id}/episodes", json=ep_data) as resp:
                assert resp.status == 200
                res_data = await resp.json()
                assert res_data.get("success") is True
                episode_id = res_data.get("id")
                print(f"✅ 4. POST /api/series/{series_id}/episodes passed: Added episode ID={episode_id}")

            # 5. Test GET /api/series/{id} (Get detail with episodes)
            async with session.get(f"{base}/api/series/{series_id}") as resp:
                assert resp.status == 200
                detail = await resp.json()
                assert detail["id"] == series_id
                assert len(detail.get("episodes", [])) == 1
                assert detail["episodes"][0]["msg_id"] == 9999
                print(f"✅ 5. GET /api/series/{series_id} passed: Retrieved detail with 1 episode")

            # 6. Test GET /api/stats
            async with session.get(f"{base}/api/stats") as resp:
                assert resp.status == 200
                stats = await resp.json()
                assert stats.get("total_series", 0) >= 1
                assert stats.get("total_episodes", 0) >= 1
                print(f"✅ 6. GET /api/stats passed: Stats = {stats}")

            # 7. Test PUT /api/series/{id} (Update)
            async with session.put(f"{base}/api/series/{series_id}", json={"status": "completed"}) as resp:
                assert resp.status == 200
                res_data = await resp.json()
                assert res_data.get("success") is True
                print("✅ 7. PUT /api/series/{id} passed: Updated status to completed")

            # 8. Test DELETE episode and series
            async with session.delete(f"{base}/api/episodes/{episode_id}") as resp:
                assert resp.status == 200
                print(f"✅ 8. DELETE /api/episodes/{episode_id} passed")

            async with session.delete(f"{base}/api/series/{series_id}") as resp:
                assert resp.status == 200
                print(f"✅ 9. DELETE /api/series/{series_id} passed: Cleaned up test data")

            print("\n🎉 ALL TELEGRAM MINI APP API TESTS PASSED 100%!")

    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(run_tests())
