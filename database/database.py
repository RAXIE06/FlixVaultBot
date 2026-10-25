# #Codeflix_Botz
# #rohit_1888 on Tg

import motor, asyncio
import motor.motor_asyncio
import time
import pymongo, os
from config import DB_URI, DB_NAME
import logging
from datetime import datetime, timedelta
import random
import string

dbclient = pymongo.MongoClient(DB_URI)
database = dbclient[DB_NAME]

logging.basicConfig(level=logging.INFO)

default_verify = {
    'is_verified': False,
    'verified_time': 0,
    'verify_token': "",
    'link': ""
}

def new_user(id):
    return {
        '_id': id,
        'verify_status': {
            'is_verified': False,
            'verified_time': "",
            'verify_token': "",
            'link': ""
        }
    }

class Rohit:

    def __init__(self, DB_URI, DB_NAME):
        self.dbclient = motor.motor_asyncio.AsyncIOMotorClient(DB_URI)
        self.database = self.dbclient[DB_NAME]

        self.channel_data = self.database['channels']
        self.admins_data = self.database['admins']
        self.user_data = self.database['users']
        self.sex_data = self.database['sex']
        self.banned_user_data = self.database['banned_user']
        self.autho_user_data = self.database['autho_user']
        self.del_timer_data = self.database['del_timer']
        self.fsub_data = self.database['fsub']    
        self.rqst_fsub_data = self.database['request_forcesub']
        self.rqst_fsub_Channel_data = self.database['request_forcesub_channel']
        
        # --- FLIXVAULT COLLECTIONS ---
        self.files_data = self.database['files']
        self.delivery_tokens_data = self.database['delivery_tokens']


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


    # ADMIN DATA
    async def admin_exist(self, admin_id: int):
        found = await self.admins_data.find_one({'_id': admin_id})
        return bool(found)

    async def add_admin(self, admin_id: int):
        if not await self.admin_exist(admin_id):
            await self.admins_data.insert_one({'_id': admin_id})
            return

    async def del_admin(self, admin_id: int):
        if await self.admin_exist(admin_id):
            await self.admins_data.delete_one({'_id': admin_id})
            return

    async def get_all_admins(self):
        users_docs = await self.admins_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in users_docs]
        return user_ids


    # BAN USER DATA
    async def ban_user_exist(self, user_id: int):
        found = await self.banned_user_data.find_one({'_id': user_id})
        return bool(found)

    async def add_ban_user(self, user_id: int):
        if not await self.ban_user_exist(user_id):
            await self.banned_user_data.insert_one({'_id': user_id})
            return

    async def del_ban_user(self, user_id: int):
        if await self.ban_user_exist(user_id):
            await self.banned_user_data.delete_one({'_id': user_id})
            return

    async def get_ban_users(self):
        users_docs = await self.banned_user_data.find().to_list(length=None)
        user_ids = [doc['_id'] for doc in users_docs]
        return user_ids



    # AUTO DELETE TIMER SETTINGS
    async def set_del_timer(self, value: int):        
        existing = await self.del_timer_data.find_one({})
        if existing:
            await self.del_timer_data.update_one({}, {'$set': {'value': value}})
        else:
            await self.del_timer_data.insert_one({'value': value})

    async def get_del_timer(self):
        data = await self.del_timer_data.find_one({})
        if data:
            return data.get('value', 600)
        return 0


    # CHANNEL MANAGEMENT
    async def channel_exist(self, channel_id: int):
        found = await self.fsub_data.find_one({'_id': channel_id})
        return bool(found)

    async def add_channel(self, channel_id: int, added_by: int = None):
        if not await self.channel_exist(channel_id):
            await self.fsub_data.insert_one({'_id': channel_id, 'added_by': added_by})
            return

    async def remove_channel(self, channel_id: int):
        if await self.channel_exist(channel_id):
            await self.fsub_data.delete_one({'_id': channel_id})
            return

    async def list_channels(self):
        channel_docs = await self.fsub_data.find().to_list(length=None)
        return channel_docs

    async def get_post(self, channel_id: int, message_id: int):
        # Optional post lookup if used by button_post
        return None

    async def save_post(self, channel_id: int, message_id: int, emoji_order=None):
        # Optional post save if used by button_post
        pass

    async def increment_reaction(self, channel_id: int, message_id: int, emoji: str):
        pass


    # --- FLIXVAULT FILE & TOKEN METHODS ---
    async def save_file_with_auto_code(self, file_id: str, file_name: str) -> str:
        """Generates a unique bot code (e.g. FLX-MOV-A7X9) and saves file info."""
        while True:
            rand_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
            bot_code = f"FLX-MOV-{rand_str}"
            existing = await self.files_data.find_one({'bot_code': bot_code})
            if not existing:
                break
        
        file_doc = {
            'bot_code': bot_code,
            'file_id': file_id,
            'file_name': file_name,
            'created_at': datetime.utcnow()
        }
        await self.files_data.insert_one(file_doc)
        return bot_code

    async def get_file_by_code(self, bot_code: str):
        """Fetches file document from MongoDB using the bot code."""
        return await self.files_data.find_one({'bot_code': bot_code})

    async def verify_and_consume_token(self, token: str, user_id: int):
        """Validates zero time-expiry, single-use delivery tokens generated by FlixVault web app."""
        token_doc = await self.delivery_tokens_data.find_one({'token': token})
        if not token_doc:
            return {"success": False, "error": "❌ Invalid or non-existent secure link."}
        
        if token_doc.get('status') == 'used':
            return {"success": False, "error": "❌ This secure link has already been used. Links are single-use only."}
        
        # Mark token as used to prevent reuse
        await self.delivery_tokens_data.update_one(
            {'token': token},
            {'$set': {'status': 'used', 'used_by': user_id, 'used_at': datetime.utcnow()}}
        )
        
        return {"success": True, "bot_code": token_doc.get('bot_code')}


db = Rohit(DB_URI, DB_NAME)
