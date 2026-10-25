# Don't Remove Credit @CodeFlix_Bots, @rohit_1888
# FlixVault Secure Delivery Start Plugin

import asyncio
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from bot import Bot
from config import *
from database.database import *

@Bot.on_message(filters.command('start') & filters.private)
async def start_command(client: Client, message: Message):
    user_id = message.from_user.id

    # Add user to database if not already present
    if not await db.present_user(user_id):
        try:
            await db.add_user(user_id)
        except Exception:
            pass

    # Check if user is banned
    banned_users = await db.get_ban_users()
    if user_id in banned_users:
        return await message.reply_text(
            "<b>⛔️ You are Banned from using this bot.</b>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Contact Support", url=BAN_SUPPORT)]]
            )
        )

    text = message.text
    args = text.split(" ", 1)

    # Check if the start command contains a secure delivery token from FlixVault website
    if len(args) > 1:
        token = args[1].strip()
        
        temp_msg = await message.reply("<b>🔍 Verifying your secure delivery token...</b>")
        
        try:
            # 1. Verify and consume the token via shared database
            token_result = await db.verify_and_consume_token(token, user_id)
            
            if not token_result.get("success"):
                return await temp_msg.edit(f"<b>{token_result.get('error', '❌ Invalid or expired token.')}</b>")
            
            bot_code = token_result.get("bot_code")
            
            # 2. Fetch the corresponding file from database using bot_code
            file_doc = await db.get_file_by_code(bot_code)
            
            if not file_doc:
                return await temp_msg.edit("<b>❌ File not found in database for this code. Please contact support.</b>")
            
            file_id = file_doc.get("file_id")
            file_name = file_doc.get("file_name", "Digital Asset / Movie")
            
            await temp_msg.edit("<b>📥 Sending your file to your DM...</b>")
            
            # 3. Send file directly to user's personal chat
            await client.send_cached_media(
                chat_id=user_id,
                file_id=file_id,
                caption=f"<b>🎬 {file_name}\n\n• Powered by FlixVault</b>",
                protect_content=PROTECT_CONTENT
            )
            
            await temp_msg.delete()
            
        except Exception as e:
            print(f"Delivery Error: {e}")
            await temp_msg.edit(f"<b>⚠️ An error occurred during file delivery: {e}</b>")
            
    else:
        # Default Welcome Message (When opened normally without token)
        reply_markup = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("• 🌐 FlixVault Website •", url="https://flix-vault-self.vercel.app/")],
                [
                    InlineKeyboardButton("• ᴀʙᴏᴜᴛ", callback_data="about"),
                    InlineKeyboardButton("ʜᴇʟᴘ •", callback_data="help")
                ]
            ]
        )
        await message.reply_photo(
            photo=START_PIC,
            caption=START_MSG.format(
                first=message.from_user.first_name,
                last=message.from_user.last_name,
                username=None if not message.from_user.username else '@' + message.from_user.username,
                mention=message.from_user.mention,
                id=message.from_user.id
            ),
            reply_markup=reply_markup
        )
