import asyncio
from telethon import TelegramClient
import config

async def test():
    print("Connecting to Telegram...")
    client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
    await client.start(bot_token=config.BOT_TOKEN)
    me = await client.get_me()
    print(f"[SUCCESS] Bot Connected: @{me.username} (ID: {me.id})")
    
    try:
        chat = await client.get_entity(config.BIN_CHANNEL)
        print(f"[SUCCESS] Bin Channel Verified: {getattr(chat, 'title', 'Channel')} (ID: {chat.id})")
    except Exception as e:
        print(f"[WARNING] Bin Channel Error: {e}")
        print("Please make sure you have added the bot as an Administrator to this channel!")
        
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(test())
