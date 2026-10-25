# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# Ask Doubt on telegram @CodeflixSupport
#
# Copyright (C) 2025 by Codeflix-Bots@Github, < https://github.com/Codeflix-Bots >.
#
# This file is part of < https://github.com/Codeflix-Bots/FileStore > project,
# and is released under the MIT License.
# Please see < https://github.com/Codeflix-Bots/FileStore/blob/master/LICENSE >
#
# All rights reserved.
#

from aiohttp import web
from plugins import web_server
import asyncio
import pyromod.listen
from pyrogram import Client
from pyrogram.enums import ParseMode
import sys
import pytz
from datetime import datetime

# FlixVault & Bot Configs
from config import *
from database.database import *
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging

# Suppress APScheduler logs below WARNING level
logging.getLogger("apscheduler").setLevel(logging.WARNING)

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")

# If you have background cleanup tasks, you can keep or adjust them here
# scheduler.add_job(remove_expired_users, "interval", seconds=10)

class Bot(Client):
    def __init__(self):
        super().__init__(
            name="FlixVaultBot",
            api_hash=API_HASH,
            api_id=APP_ID,
            plugins={
                "root": "plugins"
            },
            workers=TG_BOT_WORKERS,
            bot_token=TG_BOT_TOKEN
        )
        self.LOGGER = LOGGER

    async def start(self):
        await super().start()
        scheduler.start()
        usr_bot_me = await self.get_me()
        self.uptime = datetime.now()

        # Optional: Database Channel Check (Agar aapko DB channel ki zaroorat hai)
        try:
            if "CHANNEL_ID" in globals() or hasattr(sys.modules['config'], 'CHANNEL_ID'):
                from config import CHANNEL_ID
                if CHANNEL_ID:
                    db_channel = await self.get_chat(CHANNEL_ID)
                    self.db_channel = db_channel
                    test = await self.send_message(chat_id=db_channel.id, text="Test Message")
                    await test.delete()
        except Exception as e:
            self.LOGGER(__name__).warning(e)
            self.LOGGER(__name__).warning("Make sure bot is admin in DB channel if CHANNEL_ID is configured.")

        self.set_parse_mode(ParseMode.HTML)
        self.username = usr_bot_me.username
        self.LOGGER(__name__).info("Bot Running..!")

        # Start Web Server (For Render / Koyeb / VPS health checks or web app hooks)
        try:
            app = web.AppRunner(await web_server())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", int(PORT)).start()
            self.LOGGER(__name__).info(f"Web server started on port {PORT}")
        except Exception as e:
            self.LOGGER(__name__).warning(f"Web server failed to start: {e}")

        # Notify Owner on Restart
        try:
            await self.send_message(OWNER_ID, text="<b><blockquote>FlixVault Bot Restarted Successfully! 🚀</blockquote></b>")
        except Exception:
            pass

    async def stop(self, *args):
        await super().stop()
        self.LOGGER(__name__).info("Bot stopped.")

    def run(self):
        """Run the bot."""
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.start())
        self.LOGGER(__name__).info("Bot is now running. Thanks to @rohit_1888")
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            self.LOGGER(__name__).info("Shutting down...")
        finally:
            loop.run_until_complete(self.stop())
