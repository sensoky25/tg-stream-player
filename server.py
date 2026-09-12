import os
import sys
import asyncio
import logging
import mimetypes
from pathlib import Path

from aiohttp import web
from jinja2 import Environment, FileSystemLoader
from telethon import TelegramClient, events, Button
from telethon.tl import types
from telethon.tl.custom import Message

import config

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

    if not tg_client or not tg_client.is_connected():
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
    """Minimalist player for iframe embeds."""
    raw_id = request.match_info.get("id", "")
    try:
        msg_id = int(raw_id.replace(".mp4", ""))
    except ValueError:
        return web.Response(status=400, text="Invalid message ID")

    if not tg_client or not tg_client.is_connected():
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
    return web.Response(text=rendered, content_type="text/html")

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

    if not tg_client or not tg_client.is_connected():
        return web.Response(status=503, text="Telegram Client not connected.")

    try:
        message = await tg_client.get_messages(config.BIN_CHANNEL, ids=msg_id)
    except Exception as e:
        logger.error(f"Error fetching message {msg_id}: {e}")
        return web.Response(status=404, text="Message not found")

    if not message or not message.media:
        return web.Response(status=404, text="Media not found")

    file_name, file_size, mime_type = get_media_info(message)
    if not file_size:
        return web.Response(status=400, text="Unable to determine media file size")

    # Range header parsing
    range_header = request.headers.get("Range")
    start, end, is_range = parse_range_header(range_header, file_size)

    if start is None:
        # Invalid range requested
        return web.Response(
            status=416,
            headers={
                "Content-Range": f"bytes */{file_size}",
                "Accept-Ranges": "bytes"
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
        "Access-Control-Allow-Origin": "*",
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
        async for chunk in tg_client.iter_download(message.media, offset=start):
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

    if not tg_client or not tg_client.is_connected():
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

        # Handle /start command
        if event.raw_text and event.raw_text.strip().startswith("/start"):
            welcome_text = (
                f"👋 **សួស្ដី {sender_name}! សូមស្វាគមន៍មកកាន់ Telegram Video Stream Bot**\n\n"
                "🚀 ផ្ញើ ឬ **Forward** វីដេអូ ឬ Document ណាមួយមកកាន់ខ្ញុំ ដើម្បីទទួលបាន **Direct Stream Link (.mp4)** សម្រាប់ចាក់លើ Web Player ភ្លាមៗ!\n\n"
                "✨ **មុខងារពិសេស៖**\n"
                "• គាំទ្រ **HTTP 206 Partial Content** (អាចទាញ Seek ទៅមុខ-ថយក្រោយបានរលូន)\n"
                "• មិនប្រើប្រាស់ទំហំ Hard disk (Passthrough Direct)\n"
                "• គាំទ្រ Browser, VLC, និង Web Player គ្រប់ប្រភេទ"
            )
            await event.reply(welcome_text)
            return

        # Check if message contains media
        if not event.media:
            await event.reply("⚠️ សូមផ្ញើ ឬ Forward ជា Video ឬ File Document ដែលអ្នកចង់ Stream។")
            return

        status_msg = await event.reply("⏳ កំពុងដំណើរការ និងបង្កើត Stream Link សូមរង់ចាំបន្តិច...")

        try:
            # Forward message to bin channel
            msg_id = None
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

            reply_text = (
                f"🎬 **វីដេអូត្រូវបានបង្កើត Stream Link រួចរាល់!**\n\n"
                f"📁 **ឈ្មោះ:** `{file_name}`\n"
                f"📦 **ទំហំ:** `{human_size(file_size)}`\n\n"
                f"🔗 **Direct Stream (.mp4):**\n`{stream_url}`"
            )

            # Inline keyboard button
            try:
                if "localhost" not in config.FQDN and "127.0.0.1" not in config.FQDN:
                    buttons = [
                        [
                            Button.url("🔗 Direct Stream (.mp4)", stream_url)
                        ]
                    ]
                    await status_msg.edit(reply_text, buttons=buttons)
                else:
                    await status_msg.edit(reply_text)
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

    # Initialize aiohttp Web Application
    app = web.Application()

    # Routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/watch/{id}", handle_watch)
    app.router.add_get("/embed/{id}", handle_embed)
    app.router.add_route("*", "/stream/{id}", handle_stream)
    app.router.add_route("*", "/stream/{id}.mp4", handle_stream)
    app.router.add_get("/api/info/{id}", handle_api_info)

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
        if tg_client and tg_client.is_connected():
            logger.info("Listening for incoming Telegram messages...")
            await tg_client.run_until_disconnected()
        else:
            while True:
                await asyncio.sleep(3600)
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutting down...")
    finally:
        if tg_client and tg_client.is_connected():
            await tg_client.disconnect()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(start_server())
    except KeyboardInterrupt:
        print("\nServer stopped.")
