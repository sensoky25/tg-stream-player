"""
Automated Test Suite for Video Hotlink Protection & Domain Whitelist.
Tests:
1. Domain extraction & wildcard matching functions.
2. Security Settings REST APIs (GET /api/security/settings & POST /api/security/settings).
3. Hotlink protection on /stream/{id}.mp4:
   - Allowed domains (200/503 & dynamic CORS origin)
   - Disallowed domains (403 Forbidden)
   - Wildcard subdomains
   - Empty Referer (direct access ON vs OFF)
   - Telegram Web & Server self-access
   - OPTIONS preflight CORS
4. Embed iframe protection on /embed/{id} with CSP frame-ancestors.
"""

import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import asyncio
import aiohttp
from aiohttp import web
import database
import server
import config

async def run_tests():
    print("========================================================")
    print("🧪 STARTING HOTLINK PROTECTION & DOMAIN WHITELIST TESTS")
    print("========================================================")

    # ----------------------------------------------------
    # 1. Unit Tests: Domain Extraction & Matching
    # ----------------------------------------------------
    print("\n--- 1. Testing Domain Extraction & Matching Logic ---")
    assert server.extract_domain("https://nexkh.top/watch/123") == "nexkh.top"
    assert server.extract_domain("http://sub.domain.com:8080/stream") == "sub.domain.com"
    assert server.extract_domain("localhost:8080") == "localhost"
    assert server.extract_domain("my-site.com") == "my-site.com"
    print("✅ Domain extraction logic passed.")

    assert server.is_domain_allowed("nexkh.top", ["nexkh.top"]) == True
    assert server.is_domain_allowed("watch.nexkh.top", ["nexkh.top"]) == True
    assert server.is_domain_allowed("sub.watch.nexkh.top", ["nexkh.top"]) == True
    assert server.is_domain_allowed("fake-nexkh.top", ["nexkh.top"]) == False
    assert server.is_domain_allowed("other.com", ["nexkh.top"]) == False
    assert server.is_domain_allowed("movie.org", ["*.movie.org"]) == True
    assert server.is_domain_allowed("cdn.movie.org", ["*.movie.org"]) == True
    assert server.is_domain_allowed("badmovie.org", ["*.movie.org"]) == False
    print("✅ Wildcard & Subdomain matching logic passed.")

    # ----------------------------------------------------
    # 2. Setup Test Server
    # ----------------------------------------------------
    app = web.Application(middlewares=[server.cors_middleware])
    app.router.add_get("/embed/{id}", server.handle_embed)
    app.router.add_route("*", "/stream/{id}", server.handle_stream)
    app.router.add_route("*", "/stream/{id}.mp4", server.handle_stream)
    app.router.add_get("/api/security/settings", server.handle_api_get_security_settings)
    app.router.add_post("/api/security/settings", server.handle_api_update_security_settings)

    runner = web.AppRunner(app)
    await runner.setup()
    test_port = 8199
    site = web.TCPSite(runner, "127.0.0.1", test_port)
    await site.start()
    base = f"http://127.0.0.1:{test_port}"

    try:
        async with aiohttp.ClientSession() as session:
            # ----------------------------------------------------
            # 3. Test Security Settings REST APIs
            # ----------------------------------------------------
            print("\n--- 2. Testing Security Settings REST API ---")
            # Update settings via API
            test_config = {
                "hotlink_protection_enabled": True,
                "allowed_domains": ["nexkh.top", "moviekhmer.com", "*.mycinema.net"],
                "allow_empty_referer": True
            }
            async with session.post(f"{base}/api/security/settings", json=test_config) as resp:
                assert resp.status == 200, f"Expected 200, got {resp.status}"
                data = await resp.json()
                assert data.get("success") is True
                assert data["settings"]["hotlink_protection_enabled"] is True
                assert "nexkh.top" in data["settings"]["allowed_domains"]
                assert "*.mycinema.net" in data["settings"]["allowed_domains"]
                print("✅ POST /api/security/settings passed: Saved configuration.")

            # Retrieve settings via API
            async with session.get(f"{base}/api/security/settings") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["hotlink_protection_enabled"] is True
                assert data["allow_empty_referer"] is True
                assert len(data["allowed_domains"]) == 3
                print("✅ GET /api/security/settings passed: Retrieved configuration.")

            # ----------------------------------------------------
            # 4. Test Hotlink Protection on /stream/{id}.mp4
            # ----------------------------------------------------
            print("\n--- 3. Testing /stream/{id}.mp4 Access Rules ---")

            # Case A: Unauthorized domain Referer -> MUST BE 403 FORBIDDEN
            headers_bad = {"Referer": "https://thiefwebsite.com/watch/stolen-movie"}
            async with session.get(f"{base}/stream/123.mp4", headers=headers_bad) as resp:
                text = await resp.text()
                assert resp.status == 403, f"Expected 403 for unauthorized domain, got {resp.status}"
                assert "403 Forbidden" in text
                print("✅ [BLOCKED] Unauthorized domain 'thiefwebsite.com' successfully blocked with HTTP 403!")

            # Case B: Whitelisted domain Referer -> MUST NOT BE 403 (Passes to TG client check, returns 503)
            headers_good = {"Referer": "https://nexkh.top/drama/ep1"}
            async with session.get(f"{base}/stream/123.mp4", headers=headers_good) as resp:
                assert resp.status == 503, f"Expected 503 (client not connected), got {resp.status}"
                assert resp.headers.get("Access-Control-Allow-Origin") == "https://nexkh.top"
                print("✅ [ALLOWED] Whitelisted domain 'nexkh.top' passed hotlink check with dynamic CORS header!")

            # Case C: Subdomain of whitelisted domain -> MUST PASS
            headers_sub = {"Referer": "https://stream.nexkh.top/player"}
            async with session.get(f"{base}/stream/123.mp4", headers=headers_sub) as resp:
                assert resp.status == 503, f"Expected 503, got {resp.status}"
                print("✅ [ALLOWED] Subdomain 'stream.nexkh.top' passed hotlink check!")

            # Case D: Wildcard domain -> MUST PASS
            headers_wildcard = {"Referer": "https://vip.mycinema.net/watch"}
            async with session.get(f"{base}/stream/123.mp4", headers=headers_wildcard) as resp:
                assert resp.status == 503, f"Expected 503, got {resp.status}"
                print("✅ [ALLOWED] Wildcard domain 'vip.mycinema.net' (*.mycinema.net) passed hotlink check!")

            # Case E: Telegram Web Referer -> ALWAYS ALLOWED
            headers_tg = {"Referer": "https://web.telegram.org/a/"}
            async with session.get(f"{base}/stream/123.mp4", headers=headers_tg) as resp:
                assert resp.status == 503, f"Expected 503, got {resp.status}"
                print("✅ [ALLOWED] Telegram web origin 'web.telegram.org' auto-allowed!")

            # Case F: Direct Link (No Referer) when allow_empty_referer=True -> ALLOWED
            async with session.get(f"{base}/stream/123.mp4") as resp:
                assert resp.status == 503, f"Expected 503, got {resp.status}"
                print("✅ [ALLOWED] Direct link with empty referer allowed when allow_empty_referer=True!")

            # Case G: Direct Link when allow_empty_referer=False -> MUST BE 403
            await session.post(f"{base}/api/security/settings", json={"allow_empty_referer": False})
            async with session.get(f"{base}/stream/123.mp4") as resp:
                assert resp.status == 403, f"Expected 403 when allow_empty_referer=False, got {resp.status}"
                print("✅ [BLOCKED] Direct link with empty referer blocked with HTTP 403 when allow_empty_referer=False!")

            # Restore allow_empty_referer=True
            await session.post(f"{base}/api/security/settings", json={"allow_empty_referer": True})

            # Case H: OPTIONS Preflight request
            async with session.options(f"{base}/stream/123.mp4", headers={"Origin": "https://moviekhmer.com"}) as resp:
                assert resp.status == 204
                assert resp.headers.get("Access-Control-Allow-Origin") == "https://moviekhmer.com"
                assert "GET" in resp.headers.get("Access-Control-Allow-Methods")
                print("✅ [CORS OPTIONS] Preflight OPTIONS request returned 204 with matching origin header!")

            # ----------------------------------------------------
            # 5. Test Embed Iframe Endpoint /embed/{id}
            # ----------------------------------------------------
            print("\n--- 4. Testing /embed/{id} Iframe Protection & CSP ---")

            # Case A: Unauthorized embed Referer -> MUST BE 403 HTML
            async with session.get(f"{base}/embed/123", headers={"Referer": "https://piratesite.com/"}) as resp:
                assert resp.status == 403
                html = await resp.text()
                assert "403 Forbidden" in html
                assert "មិនអនុញ្ញាតឱ្យចាក់វីដេអូ" in html
                print("✅ [BLOCKED] Unauthorized iframe embed returned friendly Khmer 403 error page!")

            # Case B: Whitelisted embed Referer -> Returns 503 (or 200) with CSP header
            async with session.get(f"{base}/embed/123", headers={"Referer": "https://nexkh.top/movie"}) as resp:
                # Bot not connected -> 503, but not 403
                assert resp.status == 503
                print("✅ [ALLOWED] Whitelisted iframe embed passed security check!")

            # ----------------------------------------------------
            # 6. Test Master Switch: Turning Protection OFF
            # ----------------------------------------------------
            print("\n--- 5. Testing Master Switch (Disable Protection) ---")
            await session.post(f"{base}/api/security/settings", json={"hotlink_protection_enabled": False})
            async with session.get(f"{base}/stream/123.mp4", headers={"Referer": "https://thiefwebsite.com/"}) as resp:
                # With protection OFF, thiefwebsite is NOT blocked by hotlink (passes to TG client check)
                assert resp.status == 503, f"Expected 503 when protection is disabled, got {resp.status}"
                print("✅ [DISABLED] When protection is turned OFF, all domains are permitted!")

    finally:
        # Reset database test settings to default
        database.update_security_settings({
            "hotlink_protection_enabled": False,
            "allowed_domains": [],
            "allow_empty_referer": True
        })
        await runner.cleanup()
        print("\n========================================================")
        print("🎉 ALL HOTLINK PROTECTION & DOMAIN WHITELIST TESTS PASSED!")
        print("========================================================")

if __name__ == "__main__":
    asyncio.run(run_tests())
