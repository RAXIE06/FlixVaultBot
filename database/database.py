#Codeflix_Botz
#rohit_1888 on Tg

import motor, asyncio
import motor.motor_asyncio
import time
import pymongo, os
import random
import string
from config import DB_URI, DB_NAME
import logging
from datetime import datetime, timedelta

dbclient = pymongo.MongoClient(DB_URI)
database = dbclient[DB_NAME]

logging.basicConfig(level=logging.INFO)


class Rohit:

    def __init__(self, DB_URI, DB_NAME):
        self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self.database = self.dbclient[DB_NAME]

        self.user_data = self.database['users']
        # Channels where bot is allowed to post (added by admins)
        self.channels = self.database['channels']
        # Posts metadata for reaction tracking
        self.posts = self.database['posts']
        # persisted templates, channel-specific admin list/settings
        self.templates = self.database['templates']
        self.channel_admins = self.database['channel_admins']
        self.channel_settings = self.database['channel_settings']
        
        # --- FLIXVAULT INTEGRATION COLLECTIONS ---
        self.files = self.database['files'] # FileStore files collection
        self.delivery_tokens = self.database['delivery_tokens'] # Shared with website for instant purchase delivery

    # USER DATA
    async def present_user(self, user_id: int):
        found = await self.user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_user(self, user_id: int):
        await self.user_data.insert_one({'_id': user_id})
        return

    async def full_userbase(self):
        user_docs = await self.user_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in user_docs]
        return user_ids

    async def del_user(self, user_id: int):
        await self.user_data.delete_one({'_id': user_id})
        return

    # CHANNELS & POSTS
    async def add_channel(self, channel_id: int, added_by: int):
        await self.channels.update_one({'_id': channel_id}, {'$set': {'added_by': added_by}}, upsert=True)
        return

    async def remove_channel(self, channel_id: int):
        await self.channels.delete_one({'_id': channel_id})
        return

    async def list_channels(self):
        docs = await self.channels.find().to_list(length=None)
        return docs

    async def save_post(self, channel_id: int, message_id: int, emoji_order: list = None):
        emoji_order = emoji_order or []
        doc = {
            'channel_id': channel_id,
            'message_id': message_id,
            'reactions': {},
            'emoji_order': emoji_order
        }
        await self.posts.insert_one(doc)
        return

    async def get_post(self, channel_id: int, message_id: int):
        return await self.posts.find_one({'channel_id': channel_id, 'message_id': message_id})

    async def increment_reaction(self, channel_id: int, message_id: int, emoji: str):
        # Atomically increment reaction count and return the new value
        result = await self.posts.find_one_and_update(
            {'channel_id': channel_id, 'message_id': message_id},
            {'$inc': {f'reactions.{emoji}': 1}},
            return_document=True
        )
        if result:
            return result.get('reactions', {}).get(emoji, 0)
        return 0

    # Templates
    async def add_template(self, owner: int, name: str, content: str):
        await self.templates.update_one({'owner': owner, 'name': name}, {'$set': {'content': content, 'updated_at': datetime.utcnow()}}, upsert=True)
        return

    async def list_templates(self, owner: int):
        docs = await self.templates.find({'owner': owner}).to_list(length=None)
        return docs

    async def get_template(self, owner: int, name: str):
        return await self.templates.find_one({'owner': owner, 'name': name})

    async def remove_template(self, owner: int, name: str):
        await self.templates.delete_one({'owner': owner, 'name': name})
        return

    # Channel admins & settings
    async def add_channel_admin(self, channel_id: int, user_id: int):
        await self.channel_admins.update_one({'channel_id': channel_id}, {'$addToSet': {'admins': user_id}}, upsert=True)
        return

    async def remove_channel_admin(self, channel_id: int, user_id: int):
        await self.channel_admins.update_one({'channel_id': channel_id}, {'$pull': {'admins': user_id}})
        return

    async def list_channel_admins(self, channel_id: int):
        doc = await self.channel_admins.find_one({'channel_id': channel_id})
        return doc.get('admins', []) if doc else []

    async def set_channel_setting(self, channel_id: int, key: str, value):
        await self.channel_settings.update_one({'_id': channel_id}, {'$set': {key: value}}, upsert=True)
        return

    async def get_channel_setting(self, channel_id: int, key: str, default=None):
        doc = await self.channel_settings.find_one({'_id': channel_id})
        if not doc:
            return default
        return doc.get(key, default)

    # --- FLIXVAULT BOT FILE & TOKEN METHODS ---
    async def save_file_with_auto_code(self, file_id: str, file_name: str = ""):
        """Automatically generates a unique botCode and saves file info."""
        rand_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        bot_code = f"FLX-MOV-{rand_str}"
        
        doc = {
            'file_id': file_id,
            'file_name': file_name,
            'bot_code': bot_code,
            'created_at': datetime.utcnow()
        }
        await self.files.update_one({'bot_code': bot_code}, {'$set': doc}, upsert=True)
        return bot_code

    async def get_file_by_code(self, bot_code: str):
        """Finds file reference using the unique botCode."""
        return await self.files.find_one({'bot_code': bot_code})

    async def verify_and_consume_token(self, token: str, telegram_user_id: str):
        """
        Verifies website delivery token (No time expiry, single-use only).
        Marks status as 'used' once verified so it cannot be reused.
        """
        token_doc = await self.delivery_tokens.find_one({"token": token})
        if not token_doc:
            return {"success": False, "error": "❌ Invalid link. Please purchase from the website."}
        
        if token_doc.get("status") == "used":
            return {"success": False, "error": "⚠️ This link has already been used. Each link works only once."}
        
        # Mark token as used permanently (No time-expiry check)
        await self.delivery_tokens.update_one(
            {"token": token},
            {
                "$set": {
                    "status": "used", 
                    "usedAt": datetime.utcnow(), 
                    "telegramUserId": str(telegram_user_id)
                }
            }
        )
        
        return {
            "success": True,
            "bot_code": token_doc.get("botCode")
        }


db = Rohit(DB_URI, DB_NAME)
