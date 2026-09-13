import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Telegram Credentials
API_ID_RAW = os.getenv("API_ID", "")
try:
    API_ID = int(API_ID_RAW) if API_ID_RAW.strip() else None
except ValueError:
    API_ID = None

API_HASH = os.getenv("API_HASH", "").strip()
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Bin Channel (Storage Channel ID)
BIN_CHANNEL_RAW = os.getenv("BIN_CHANNEL", "").strip()
try:
    BIN_CHANNEL = int(BIN_CHANNEL_RAW) if BIN_CHANNEL_RAW else None
except ValueError:
    BIN_CHANNEL = BIN_CHANNEL_RAW if BIN_CHANNEL_RAW else None

# Allowed Users / Owner ID (Whitelist for private bot security)
ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", os.getenv("OWNER_ID", "")).strip()
ALLOWED_USERS = set()
if ALLOWED_USERS_RAW:
    for uid in ALLOWED_USERS_RAW.split(","):
        uid_clean = uid.strip()
        if uid_clean:
            try:
                ALLOWED_USERS.add(int(uid_clean))
            except ValueError:
                pass

# Server settings
PORT = int(os.getenv("PORT", "8080"))
HOST = os.getenv("HOST", "0.0.0.0")

# FQDN (Fully Qualified Domain Name or Base URL)
FQDN = os.getenv("FQDN", f"http://localhost:{PORT}").rstrip("/")

SESSION_NAME = os.getenv("SESSION_NAME", "tg_stream_bot")

def validate_config():
    """Verify that all required environment variables are set."""
    missing = []
    if not API_ID:
        missing.append("API_ID (Telegram API ID)")
    if not API_HASH:
        missing.append("API_HASH (Telegram API Hash)")
    if not BOT_TOKEN:
        missing.append("BOT_TOKEN (Telegram Bot Token from @BotFather)")
    if not BIN_CHANNEL:
        missing.append("BIN_CHANNEL (Channel ID for storing files, e.g. -100xxxxxxxxxx)")
    
    return missing
