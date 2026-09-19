import os
import sys
import asyncio
import logging
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from telethon import TelegramClient, events, Button
from telethon.tl import types
from telethon.tl.custom import Message

import config
import database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("TGStreamServer")

# Jinja2 Templates setup
TEMPLATES_DIR = Path(__file__).parent / "templates"
jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=True)

# Telethon client instance
tg_client: TelegramClient = None
bot_me = None

async def is_bot_ready() -> bool:
    """Check if Telegram Client is connected and authenticated."""
    if not tg_client or not tg_client.is_connected():
        return False
    try:
        return await tg_client.is_user_authorized()
    except Exception:
        return False

def human_size(size_bytes: int) -> str:
    """Format bytes into human-readable string (KB, MB, GB)."""
    if not size_bytes:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.2f} {units[i]}"

def get_media_info(message: Message):
    """Extract filename, size, and mime type from a Telegram message."""
    file_name = "video.mp4"
    file_size = 0
    mime_type = "video/mp4"

    media = message.media if message else None
    if not media:
        return file_name, file_size, mime_type

    if hasattr(media, "document") and media.document:
        doc = media.document
        file_size = doc.size or 0
        mime_type = doc.mime_type or "video/mp4"
        
        # Check filename attributes
        for attr in (doc.attributes or []):
            if hasattr(attr, "file_name") and attr.file_name:
                file_name = attr.file_name
                break
        else:
            ext = mimetypes.guess_extension(mime_type) or ".mp4"
            file_name = f"telegram_video_{message.id}{ext}"

    elif hasattr(media, "photo") and media.photo:
        file_name = f"telegram_photo_{message.id}.jpg"
        mime_type = "image/jpeg"
        # Calculate largest photo size
        sizes = getattr(media.photo, "sizes", [])
        if sizes:
            largest = sizes[-1]
            file_size = getattr(largest, "size", 0)

    # Fallback mime detection
    if mime_type in ("application/octet-stream", ""):
        guessed_type, _ = mimetypes.guess_type(file_name)
        if guessed_type:
            mime_type = guessed_type

    return file_name, file_size, mime_type

def parse_range_header(range_header: str, file_size: int):
    """
    Parse HTTP Range header.
    Supports formats like:
      bytes=0-
      bytes=1000-2000
      bytes=-500
    Returns (start, end, is_range_request)
    """
    if not range_header or not range_header.startswith("bytes="):
        return 0, file_size - 1, False

    range_str = range_header.replace("bytes=", "").strip()
    if "," in range_str:
        range_str = range_str.split(",")[0].strip()

    parts = range_str.split("-")
    if len(parts) != 2:
        return 0, file_size - 1, False

    start_str, end_str = parts[0].strip(), parts[1].strip()

    try:
        if not start_str and end_str:
            # Suffix range: -500 (last 500 bytes)
            length = int(end_str)
            start = max(0, file_size - length)
            end = file_size - 1
        elif start_str and not end_str:
            # Prefix range: 500-
            start = int(start_str)
            end = file_size - 1
        elif start_str and end_str:
            start = int(start_str)
            end = min(file_size - 1, int(end_str))
        else:
            return 0, file_size - 1, False
    except ValueError:
        return None, None, True

    if start > end or start >= file_size:
        return None, None, True

    return start, end, True

# ========================================================
# Hotlink Protection & Domain Whitelisting Logic
# ========================================================

def extract_domain(url_or_str: str) -> str:
    """Extract clean lowercase domain/hostname from a URL or domain string."""
    if not url_or_str:
        return ""
    raw = str(url_or_str).strip().lower()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    try:
        parsed = urlparse(raw)
        host = parsed.netloc or parsed.path
        return host.split(":")[0].strip().lower()
    except Exception:
        return ""

def is_domain_allowed(req_domain: str, allowed_domains: list) -> bool:
    """
    Check if a requested domain matches any allowed domain.
    Supports:
      - exact match: 'nexkh.top' == 'nexkh.top'
      - subdomains: 'sub.nexkh.top' matches 'nexkh.top' or '*.nexkh.top'
      - wildcards: '*.movie.com' matches 'abc.movie.com'
    """
    if not req_domain:
        return False
    req_domain = req_domain.strip().lower()

    for allowed in allowed_domains:
        allowed = str(allowed).strip().lower()
        if not allowed:
            continue
        if "://" in allowed:
            allowed = allowed.split("://", 1)[1]
        allowed = allowed.split("/", 1)[0].split(":")[0].strip()

        if allowed.startswith("*."):
            base = allowed[2:]
            if req_domain == base or req_domain.endswith("." + base):
                return True
        else:
            if req_domain == allowed or req_domain.endswith("." + allowed):
                return True
    return False

def check_hotlink_access(request: web.Request):
    """
    Determine whether the request is authorized to access video streams/embeds.
    Returns: (is_allowed: bool, allowed_origin: str, reason: str)
    """
    sec = database.get_security_settings()
    if not sec.get("hotlink_protection_enabled", False):
        return True, "*", "protection_disabled"

    origin_hdr = request.headers.get("Origin", "").strip()
    referer_hdr = request.headers.get("Referer", "").strip()
    sec_fetch_site = request.headers.get("Sec-Fetch-Site", "").strip().lower()

    # Server's own domain, localhost, and Telegram are ALWAYS allowed
    server_fqdn_domain = extract_domain(config.FQDN)
    host_header_domain = extract_domain(request.headers.get("Host", ""))
    auto_allowed = {"localhost", "127.0.0.1", "telegram.org", "web.telegram.org"}
    if server_fqdn_domain:
        auto_allowed.add(server_fqdn_domain)
    if host_header_domain:
        auto_allowed.add(host_header_domain)

    # Candidate domains from request
    req_domains = []
    client_origin = None

    if origin_hdr:
        d = extract_domain(origin_hdr)
        if d:
            req_domains.append(d)
            client_origin = origin_hdr.rstrip("/")

    if referer_hdr:
        d = extract_domain(referer_hdr)
        if d:
            req_domains.append(d)
            if not client_origin:
                try:
                    parsed = urlparse(referer_hdr)
                    client_origin = f"{parsed.scheme}://{parsed.netloc}"
                except Exception:
                    pass

    # Direct Link / Empty Referer
    if not req_domains:
        allow_empty = sec.get("allow_empty_referer", True)
        if allow_empty:
            return True, "*", "empty_referer_allowed"

        if sec_fetch_site == "cross-site":
            return False, "", "cross_site_hidden_referer"

        return False, "", "empty_referer_forbidden"

    # Check if request comes from self / auto-allowed
    for d in req_domains:
        if d in auto_allowed or is_domain_allowed(d, list(auto_allowed)):
            return True, client_origin or "*", "server_self_allowed"

    # Check against user-configured allowed whitelist
    allowed_domains = sec.get("allowed_domains", [])
    for d in req_domains:
        if is_domain_allowed(d, allowed_domains):
            return True, client_origin or "*", "whitelist_matched"

    return False, "", f"domain_unauthorized: {', '.join(req_domains)}"

# ========================================================
# HTTP Request Handlers
# ========================================================

async def handle_index(request: web.Request):
    """Redirect landing page to main website so visitors cannot see stream engine dashboard."""
    host = request.host.split(":")[0]
    parts = host.split(".")
    if len(parts) >= 2 and parts[0] in ("stream", "video", "media", "cdn"):
        main_url = f"https://{'.'.join(parts[1:])}"
    else:
        main_url = "https://nexkh.top"

    raise web.HTTPFound(location=main_url)

async def handle_watch(request: web.Request):
    """Full Web Player page."""
    raw_id = request.match_info.get("id", "")
    try:
        msg_id = int(raw_id.replace(".mp4", ""))
    except ValueError:
        return web.Response(status=400, text="Invalid message ID")

    if not await is_bot_ready():
        return web.Response(status=503, text="Telegram Client is not connected. Please configure .env")

    try:
        message = await tg_client.get_messages(config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        logger.error(f"Failed to fetch message {msg_id}: {e}")
        return web.Response(status=404, text=f"Message not found in bin channel: {e}")

    if not message or not message.media:
        return web.Response(status=404, text="Video media not found or deleted from Telegram channel.")

    file_name, file_size, mime_type = get_media_info(message)
    stream_url = f"{config.FQDN}/stream/{msg_id}.mp4"
    embed_url = f"{config.FQDN}/embed/{msg_id}"
    download_url = f"{stream_url}?download=1"

    template = jinja_env.get_template("player.html")
    rendered = template.render(
        msg_id=msg_id,
        file_name=file_name,
        file_size=file_size,
        file_size_human=human_size(file_size),
        mime_type=mime_type,
        stream_url=stream_url,
        embed_url=embed_url,
        download_url=download_url
    )
    return web.Response(text=rendered, content_type="text/html")

async def handle_embed(request: web.Request):
    """Minimalist player for iframe embeds with CSP & Hotlink Protection."""
    raw_id = request.match_info.get("id", "")
    try:
        msg_id = int(raw_id.replace(".mp4", ""))
    except ValueError:
        return web.Response(status=400, text="Invalid message ID")

    # Hotlink Protection Check
    is_allowed, allowed_origin, reason = check_hotlink_access(request)
    if not is_allowed:
        logger.warning(f"🚫 Hotlink embed blocked for msg={msg_id}: reason={reason} referer={request.headers.get('Referer')} origin={request.headers.get('Origin')}")
        return web.Response(
            status=403,
            text="""<!DOCTYPE html>
<html lang="km">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>403 Forbidden - Hotlink Restricted</title>
    <link href="https://fonts.googleapis.com/css2?family=Kantumruy+Pro:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            background-color: #0d1117;
            color: #f0f6fc;
            font-family: 'Kantumruy Pro', sans-serif;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            padding: 20px;
        }
        .card {
            background: rgba(22, 27, 34, 0.95);
            border: 1px solid rgba(239, 68, 68, 0.3);
            border-radius: 16px;
            padding: 28px 24px;
            max-width: 440px;
            text-align: center;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
        }
        .icon {
            font-size: 44px;
            margin-bottom: 12px;
            display: inline-block;
        }
        h2 {
            font-size: 18px;
            color: #ef4444;
            margin-bottom: 10px;
            font-weight: 600;
        }
        p {
            font-size: 13px;
            color: #8b949e;
            line-height: 1.6;
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="icon">🚫</div>
        <h2>មិនអនុញ្ញាតឱ្យចាក់វីដេអូ (403 Forbidden)</h2>
        <p>គេហទំព័រនេះមិនត្រូវបានអនុញ្ញាតឱ្យយក Link វីដេអូទៅចាក់ឡើយ (Hotlink Protection Active)។</p>
        <p style="margin-top: 8px;">សូមទាក់ទងម្ចាស់ Server ដើម្បីបន្ថែម Domain របស់អ្នកទៅក្នុងបញ្ជីអនុញ្ញាត (Whitelist)។</p>
    </div>
</body>
</html>""",
            content_type="text/html"
        )

    if not await is_bot_ready():
        return web.Response(status=503, text="Telegram Client not connected.")

    try:
        message = await tg_client.get_messages(config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        return web.Response(status=404, text=f"Media not found: {e}")

    if not message or not message.media:
        return web.Response(status=404, text="Media not found.")

    file_name, file_size, mime_type = get_media_info(message)
    stream_url = f"{config.FQDN}/stream/{msg_id}.mp4"

    template = jinja_env.get_template("embed.html")
    rendered = template.render(
        file_name=file_name,
        mime_type=mime_type,
        stream_url=stream_url
    )

    # Content-Security-Policy: frame-ancestors
    sec = database.get_security_settings()
    csp_header = "frame-ancestors 'self'"
    if sec.get("hotlink_protection_enabled"):
        allowed_list = sec.get("allowed_domains", [])
        for dom in allowed_list:
            clean = dom.strip().lower()
            if clean:
                if clean.startswith("*."):
                    csp_header += f" https://{clean} http://{clean}"
                else:
                    csp_header += f" https://{clean} https://*.{clean} http://{clean} http://*.{clean}"

    return web.Response(
        text=rendered,
        content_type="text/html",
        headers={"Content-Security-Policy": csp_header}
    )

async def handle_stream(request: web.Request):
    """
    Direct Video Streaming with HTTP 206 Partial Content support.
    Streams directly from Telegram MTProto to Browser on-the-fly.
    """
    raw_id = request.match_info.get("id", "")
    try:
        msg_id = int(raw_id.replace(".mp4", ""))
    except ValueError:
        return web.Response(status=400, text="Invalid message ID")

    # Hotlink Protection Check
    is_allowed, allowed_origin, reason = check_hotlink_access(request)
    if not is_allowed:
        logger.warning(f"🚫 Hotlink stream blocked for msg={msg_id}: reason={reason} referer={request.headers.get('Referer')} origin={request.headers.get('Origin')}")
        return web.Response(
            status=403,
            text="403 Forbidden: Hotlink protection active. This domain is not authorized to stream this video.",
            content_type="text/plain",
            headers={
                "Access-Control-Allow-Origin": allowed_origin or "*",
            }
        )

    # Handle OPTIONS preflight request
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": allowed_origin or "*",
                "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
                "Access-Control-Allow-Headers": "Range, Content-Type, Accept, Origin, User-Agent",
                "Access-Control-Max-Age": "86400",
            }
        )

    if not await is_bot_ready():
        return web.Response(
            status=503,
            text="Telegram Client not connected.",
            headers={"Access-Control-Allow-Origin": allowed_origin or "*"}
        )

    try:
        message = await tg_client.get_messages(config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        logger.error(f"Error fetching message {msg_id}: {e}")
        return web.Response(
            status=404,
            text="Message not found",
            headers={"Access-Control-Allow-Origin": allowed_origin or "*"}
        )

    if not message or not message.media:
        return web.Response(
            status=404,
            text="Media not found",
            headers={"Access-Control-Allow-Origin": allowed_origin or "*"}
        )

    file_name, file_size, mime_type = get_media_info(message)
    if not file_size:
        return web.Response(
            status=400,
            text="Unable to determine media file size",
            headers={"Access-Control-Allow-Origin": allowed_origin or "*"}
        )

    # Range header parsing
    range_header = request.headers.get("Range")
    start, end, is_range = parse_range_header(range_header, file_size)

    if start is None:
        # Invalid range requested
        return web.Response(
            status=416,
            headers={
                "Content-Range": f"bytes */{file_size}",
                "Accept-Ranges": "bytes",
                "Access-Control-Allow-Origin": allowed_origin or "*"
            },
            text="Requested Range Not Satisfiable"
        )

    content_length = (end - start) + 1
    status = 206 if is_range else 200

    # Disposition: inline for web stream, attachment for download
    is_download = request.query.get("download") == "1"
    disposition = f'attachment; filename="{file_name}"' if is_download else f'inline; filename="{file_name}"'

    headers = {
        "Content-Type": mime_type,
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Disposition": disposition,
        "Access-Control-Allow-Origin": allowed_origin or "*",
        "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
        "X-Accel-Buffering": "no",
        "Cache-Control": "public, max-age=86400, no-transform",
    }

    if is_range:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    # Handle HEAD request (Used by video players & browsers before GET)
    if request.method == "HEAD":
        return web.Response(status=status, headers=headers)

    # Initialize Stream Response
    response = web.StreamResponse(status=status, headers=headers)
    await response.prepare(request)

    logger.info(f"Streaming msg={msg_id} range={start}-{end}/{file_size} ({human_size(content_length)})")

    # Stream chunks from Telegram MTProto
    bytes_left = content_length
    try:
        # Request 512KB chunks (MAX_CHUNK_SIZE) from Telegram MTProto for 4-8x faster throughput
        async for chunk in tg_client.iter_download(
            message.media,
            offset=start,
            chunk_size=524288,
            request_size=524288
        ):
            if not chunk:
                break
            
            chunk_len = len(chunk)
            if chunk_len > bytes_left:
                chunk = chunk[:bytes_left]
                chunk_len = bytes_left

            await response.write(chunk)
            bytes_left -= chunk_len

            if bytes_left <= 0:
                break

    except (asyncio.CancelledError, ConnectionResetError):
        # Client aborted connection (user sought to different position or paused)
        pass
    except Exception as err:
        logger.warning(f"Client disconnected or streaming interrupted for msg {msg_id}: {err}")
    finally:
        try:
            await response.write_eof()
        except Exception:
            pass

    return response

async def handle_api_info(request: web.Request):
    """API endpoint to get media JSON information."""
    raw_id = request.match_info.get("id", "")
    try:
        msg_id = int(raw_id.replace(".mp4", ""))
    except ValueError:
        return web.json_response({"error": "Invalid ID"}, status=400)

    if not await is_bot_ready():
        return web.json_response({"error": "Bot not connected"}, status=503)

    try:
        message = await tg_client.get_messages(config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=404)

    if not message or not message.media:
        return web.json_response({"error": "Media not found"}, status=404)

    file_name, file_size, mime_type = get_media_info(message)
    return web.json_response({
        "id": msg_id,
        "file_name": file_name,
        "file_size": file_size,
        "file_size_human": human_size(file_size),
        "mime_type": mime_type,
        "stream_url": f"{config.FQDN}/stream/{msg_id}.mp4",
        "watch_url": f"{config.FQDN}/watch/{msg_id}",
        "embed_url": f"{config.FQDN}/embed/{msg_id}"
    })

# ========================================================
# Telegram Mini App & Drama Management Handlers
# ========================================================

@web.middleware
async def cors_middleware(request: web.Request, handler):
    """Enable CORS for API calls and WebApp requests."""
    # Do not alter headers on stream routes (stream handler sets its own streaming headers)
    if request.path.startswith("/stream"):
        return await handler(request)

    if request.method == "OPTIONS":
        response = web.Response(status=204)
    else:
        try:
            response = await handler(request)
        except web.HTTPRedirection as redirect:
            response = redirect
        except Exception:
            raise
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Requested-With"
    return response

async def handle_miniapp(request: web.Request):
    """Serve Telegram Mini App interface."""
    template = jinja_env.get_template("miniapp.html")
    rendered = template.render(fqdn=config.FQDN)
    return web.Response(text=rendered, content_type="text/html")

async def handle_api_get_series(request: web.Request):
    """API endpoint to list series with filters and search."""
    search = request.query.get("search")
    genre = request.query.get("genre")
    series_type = request.query.get("type")
    status = request.query.get("status")
    series_list = database.get_all_series(search=search, genre=genre, series_type=series_type, status=status)
    return web.json_response({"series": series_list})

async def handle_api_create_series(request: web.Request):
    """API endpoint to create a new series or movie."""
    try:
        data = await request.json()
        series_id = database.create_series(data)
        return web.json_response({"success": True, "id": series_id})
    except Exception as e:
        logger.error(f"Error creating series: {e}")
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_get_series_detail(request: web.Request):
    """API endpoint to get series detail and all its episodes."""
    try:
        series_id = int(request.match_info.get("id", 0))
        series = database.get_series_by_id(series_id)
        if not series:
            return web.json_response({"error": "Series not found"}, status=404)
        return web.json_response(series)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_update_series(request: web.Request):
    """API endpoint to update series."""
    try:
        series_id = int(request.match_info.get("id", 0))
        data = await request.json()
        success = database.update_series(series_id, data)
        return web.json_response({"success": success})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_delete_series(request: web.Request):
    """API endpoint to delete series."""
    try:
        series_id = int(request.match_info.get("id", 0))
        success = database.delete_series(series_id)
        return web.json_response({"success": success})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_add_episode(request: web.Request):
    """API endpoint to add an episode to a series."""
    try:
        series_id = int(request.match_info.get("id", 0))
        data = await request.json()
        
        msg_id = data.get("msg_id")
        if msg_id and tg_client and tg_client.is_connected() and not data.get("file_name"):
            try:
                msg = await tg_client.get_messages(config.BIN_CHANNEL, ids=int(msg_id))
                if msg and msg.media:
                    fn, fs, _ = get_media_info(msg)
                    data["file_name"] = fn
                    data["file_size"] = fs
            except Exception as tg_err:
                logger.warning(f"Could not auto-fetch media info for msg {msg_id}: {tg_err}")

        if not data.get("stream_url") and msg_id:
            data["stream_url"] = f"{config.FQDN}/stream/{msg_id}.mp4"

        episode_id = database.add_episode(series_id, data)
        return web.json_response({"success": True, "id": episode_id})
    except Exception as e:
        logger.error(f"Error adding episode: {e}")
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_update_episode(request: web.Request):
    """API endpoint to update an episode."""
    try:
        episode_id = int(request.match_info.get("id", 0))
        data = await request.json()
        success = database.update_episode(episode_id, data)
        return web.json_response({"success": success})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_delete_episode(request: web.Request):
    """API endpoint to delete an episode."""
    try:
        episode_id = int(request.match_info.get("id", 0))
        success = database.delete_episode(episode_id)
        return web.json_response({"success": success})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_recent_media(request: web.Request):
    """API endpoint to fetch recent video messages for quick assignment."""
    fetch_id = request.query.get("fetch_id")
    if fetch_id and tg_client and tg_client.is_connected():
        try:
            m_id = int(fetch_id)
            msg = await tg_client.get_messages(config.BIN_CHANNEL, ids=m_id)
            if msg and msg.media:
                fn, fs, mime = get_media_info(msg)
                s_url = f"{config.FQDN}/stream/{m_id}.mp4"
                database.save_recent_upload(m_id, fn, fs, mime, s_url)
        except Exception as e:
            logger.warning(f"Failed to fetch single message {fetch_id}: {e}")

    uploads = database.get_recent_uploads(limit=50)
    return web.json_response({"media": uploads})

async def handle_api_add_recent_media(request: web.Request):
    """API endpoint to import a message ID into recent uploads."""
    try:
        data = await request.json()
        msg_id = int(data.get("msg_id"))
        if not tg_client or not tg_client.is_connected():
            return web.json_response({"error": "Bot not connected"}, status=503)

        msg = await tg_client.get_messages(config.BIN_CHANNEL, ids=msg_id)
        if not msg or not msg.media:
            return web.json_response({"error": "Message not found in bin channel or has no media"}, status=404)

        fn, fs, mime = get_media_info(msg)
        s_url = f"{config.FQDN}/stream/{msg_id}.mp4"
        database.save_recent_upload(msg_id, fn, fs, mime, s_url)
        return web.json_response({"success": True, "media": {
            "id": msg_id,
            "file_name": fn,
            "file_size": fs,
            "mime_type": mime,
            "stream_url": s_url
        }})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=400)

async def handle_api_stats(request: web.Request):
    """API endpoint to get total counts."""
    stats = database.get_stats()
    return web.json_response(stats)

async def handle_api_get_security_settings(request: web.Request):
    """API endpoint to get security & hotlink settings."""
    settings = database.get_security_settings()
    settings["server_domain"] = extract_domain(config.FQDN)
    return web.json_response(settings)

async def handle_api_update_security_settings(request: web.Request):
    """API endpoint to update security & hotlink settings."""
    try:
        data = await request.json()
        updated = database.update_security_settings(data)
        updated["server_domain"] = extract_domain(config.FQDN)
        logger.info(f"Updated security settings: {updated}")
        return web.json_response({"success": True, "settings": updated})
    except Exception as e:
        logger.error(f"Error updating security settings: {e}")
        return web.json_response({"error": str(e)}, status=400)

# ========================================================
# Telegram Bot Message Handler
# ========================================================

def setup_bot_handlers():
    """Register message handlers on Telegram bot."""
    if not tg_client:
        return

    @tg_client.on(events.NewMessage(incoming=True))
    async def on_private_message(event: events.NewMessage.Event):
        # Ignore outgoing messages (sent by the bot itself)
        if event.out:
            return
        if bot_me and event.sender_id == bot_me.id:
            return

        # Only process private messages sent to the bot
        if not event.is_private:
            return

        sender = await event.get_sender()
        sender_name = getattr(sender, "first_name", "User") or "User"
        logger.info(f"Incoming message from {sender_name} (ID {event.sender_id}): text='{event.raw_text}' has_media={bool(event.media)}")

        # Check access permission (Whitelist / Private Mode)
        if config.ALLOWED_USERS and event.sender_id not in config.ALLOWED_USERS:
            logger.warning(f"Unauthorized access by {sender_name} (ID: {event.sender_id})")
            await event.reply(
                f"⛔ **សូមអភ័យទោស! Bot នេះត្រូវបានកំណត់ជាឯកជន (Private) សម្រាប់តែម្ចាស់ប៉ុណ្ណោះ។**\n\n"
                f"👤 **Telegram ID របស់អ្នកគឺ:** `{event.sender_id}`"
            )
            return

        # Handle /start or /app commands
        if event.raw_text and any(event.raw_text.strip().startswith(cmd) for cmd in ("/start", "/app", "/manage", "/drama")):
            welcome_text = (
                f"👋 **សួស្ដី {sender_name}! សូមស្វាគមន៍មកកាន់ប្រព័ន្ធ Telegram Video & Drama Stream**\n\n"
                "🚀 **មុខងារសំខាន់ៗ៖**\n"
                "• ផ្ញើ ឬ **Forward** វីដេអូមកកាន់ខ្ញុំ ដើម្បីទទួលបាន Direct Stream Link (.mp4)\n"
                "• ចុច **🎬 បើកគ្រប់គ្រងរឿង (Mini App)** ខាងក្រោម ដើម្បីរៀបចំរឿងភាគ រឿងដុំ និងភាគនីមួយៗបានយ៉ាងងាយស្រួល!\n\n"
                "✨ គាំទ្រ HTTP 206 Partial Content (Seek បានរលូន) និងមិនប្រើ Disk ទំហំ VPS ឡើយ។"
            )
            buttons = [
                [
                    Button.url("🎬 បើកគ្រប់គ្រងរឿង (Mini App)", f"{config.FQDN}/app")
                ]
            ]
            await event.reply(welcome_text, buttons=buttons)
            return

        # Check if message contains media
        if not event.media:
            await event.reply("⚠️ សូមផ្ញើ ឬ Forward ជា Video ឬ File Document ដែលអ្នកចង់ Stream។")
            return

        status_msg = await event.reply("⏳ កំពុងដំណើរការ និងបង្កើត Stream Link សូមរង់ចាំបន្តិច...")

        try:
            # Check if forwarded from the bin channel itself to prevent duplicates
            msg_id = None
            if getattr(event.message, "fwd_from", None) and getattr(event.message.fwd_from, "channel_post", None):
                from_id = getattr(event.message.fwd_from, "from_id", None)
                from_channel_id = None
                if from_id:
                    try:
                        from telethon import utils
                        from_channel_id = utils.get_peer_id(from_id)
                    except Exception:
                        pass
                if from_channel_id == config.BIN_CHANNEL:
                    msg_id = event.message.fwd_from.channel_post
                    logger.info(f"Video already in bin channel (msg_id={msg_id}), skipping duplicate forward.")

            # If not already in bin channel, forward message to bin channel
            if not msg_id:
                try:
                    forwarded = await tg_client.forward_messages(config.BIN_CHANNEL, event.message)
                    if isinstance(forwarded, list):
                        msg_id = forwarded[0].id
                    else:
                        msg_id = forwarded.id
                except Exception as fwd_err:
                    logger.warning(f"Forward failed ({fwd_err}), falling back to sending file copy...")
                    sent = await tg_client.send_file(
                        config.BIN_CHANNEL,
                        file=event.message.media,
                        caption=event.message.text or ""
                    )
                    msg_id = sent.id

            # Extract info
            file_name, file_size, mime_type = get_media_info(event.message)
            stream_url = f"{config.FQDN}/stream/{msg_id}.mp4"
            watch_url = f"{config.FQDN}/watch/{msg_id}"
            download_url = f"{stream_url}?download=1"

            # Automatically save into recent_uploads table so Mini App shows it immediately!
            try:
                database.save_recent_upload(msg_id, file_name, file_size, mime_type, stream_url)
                logger.info(f"Saved media {msg_id} to recent_uploads database.")
            except Exception as db_err:
                logger.warning(f"Could not save to recent_uploads: {db_err}")

            reply_text = (
                f"🎬 **វីដេអូត្រូវបានបង្កើត Stream Link រួចរាល់!**\n\n"
                f"📁 **ឈ្មោះ:** `{file_name}`\n"
                f"📦 **ទំហំ:** `{human_size(file_size)}`\n"
                f"🆔 **Message ID:** `{msg_id}`\n\n"
                f"🔗 **Direct Stream (.mp4):**\n`{stream_url}`"
            )

            # Inline keyboard buttons
            try:
                buttons = [
                    [
                        Button.url("🔗 Direct Stream (.mp4)", stream_url)
                    ],
                    [
                        Button.url("🎬 គ្រប់គ្រងរឿង (Mini App)", f"{config.FQDN}/app?add_id={msg_id}")
                    ]
                ]
                await status_msg.edit(reply_text, buttons=buttons)
            except Exception as btn_err:
                logger.warning(f"Could not attach buttons ({btn_err}), sending text only.")
                await status_msg.edit(reply_text)

            logger.info(f"Successfully generated stream link for msg={msg_id}, file={file_name}")

        except Exception as e:
            logger.error(f"Failed to process media: {e}")
            await status_msg.edit(f"❌ មានបញ្ហាក្នុងការបង្កើត Link៖ `{e}`\n\nសូមប្រាកដថា Bot ត្រូវបាន Add ជា Admin ក្នុង Bin Channel រួចហើយ!")

# ========================================================
# Main Entrypoint
# ========================================================

async def start_server():
    global tg_client, bot_me

    missing = config.validate_config()
    if missing:
        logger.warning("=========================================================")
        logger.warning("⚠️  MISSING CONFIGURATION VARIABLES in .env:")
        for item in missing:
            logger.warning(f"   - {item}")
        logger.warning("Please edit .env file and restart to enable Telegram Bot.")
        logger.warning(f"Starting Web Dashboard anyway on {config.FQDN}...")
        logger.warning("=========================================================")
    else:
        logger.info("Connecting Telegram Client to MTProto...")
        try:
            tg_client = TelegramClient(
                config.SESSION_NAME,
                config.API_ID,
                config.API_HASH
            )
            tg_client.catch_up = True
            setup_bot_handlers()
            await tg_client.start(bot_token=config.BOT_TOKEN)
            bot_me = await tg_client.get_me()
            logger.info(f"✅ Telegram Bot @{bot_me.username} (ID: {bot_me.id}) is connected and ready!")
        except Exception as e:
            logger.error(f"❌ Failed to start Telegram Bot: {e}")

    # Initialize aiohttp Web Application with CORS support
    app = web.Application(middlewares=[cors_middleware])

    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/app", handle_miniapp)
    app.router.add_get("/watch/{id}", handle_watch)
    app.router.add_get("/embed/{id}", handle_embed)
    app.router.add_route("*", "/stream/{id}", handle_stream)
    app.router.add_route("*", "/stream/{id}.mp4", handle_stream)
    app.router.add_get("/api/info/{id}", handle_api_info)

    # Mini App REST APIs
    app.router.add_get("/api/series", handle_api_get_series)
    app.router.add_post("/api/series", handle_api_create_series)
    app.router.add_get("/api/series/{id}", handle_api_get_series_detail)
    app.router.add_put("/api/series/{id}", handle_api_update_series)
    app.router.add_delete("/api/series/{id}", handle_api_delete_series)
    app.router.add_post("/api/series/{id}/episodes", handle_api_add_episode)
    app.router.add_put("/api/episodes/{id}", handle_api_update_episode)
    app.router.add_delete("/api/episodes/{id}", handle_api_delete_episode)
    app.router.add_get("/api/recent-media", handle_api_recent_media)
    app.router.add_post("/api/recent-media/add", handle_api_add_recent_media)
    app.router.add_get("/api/stats", handle_api_stats)
    app.router.add_get("/api/security/settings", handle_api_get_security_settings)
    app.router.add_post("/api/security/settings", handle_api_update_security_settings)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=config.HOST, port=config.PORT)
    await site.start()

    logger.info("=========================================================")
    logger.info(f"🚀 Telegram Stream Server running on: {config.FQDN}")
    logger.info(f"📺 Web Player Endpoint: {config.FQDN}/watch/<id>")
    logger.info(f"🎥 Direct Stream URL:  {config.FQDN}/stream/<id>.mp4")
    logger.info("=========================================================")

    # Keep running and listen for Telegram updates
    try:
        if await is_bot_ready():
            logger.info("Listening for incoming Telegram messages...")
            await tg_client.run_until_disconnected()
        else:
            logger.warning("Telegram Bot is not authorized or not connected. Web server running in fallback mode.")
            while True:
                await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down...")
    except Exception as e:
        logger.error(f"Telegram client runtime error: {e}")
    finally:
        if tg_client and tg_client.is_connected():
            await tg_client.disconnect()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\nServer stopped.")
