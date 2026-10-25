from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo, InputMediaDocument
import asyncio
import re
import logging

from config import START_MSG, START_PIC, HELP_TXT, ABOUT_TXT, is_admin
from database.database import db

logger = logging.getLogger(__name__)

# ephemeral drafts keyed by user_id
DRAFTS = {}


async def _attempt_send_preview(client, dest_chat_id, msg, reply_markup=None):
    """Try to present a message to dest_chat: copy -> forward -> re-send by type."""
    try:
        return await client.copy_message(chat_id=dest_chat_id, from_chat_id=msg.chat.id, message_id=msg.message_id, reply_markup=reply_markup)
    except Exception as e:
        logger.debug("copy_message failed for preview: %s", e)
    try:
        return await client.forward_messages(dest_chat_id, msg.chat.id, msg.message_id)
    except Exception as e:
        logger.debug("forward_messages failed for preview: %s", e)
    
    try:
        if msg.text:
            return await client.send_message(dest_chat_id, msg.text, reply_markup=reply_markup)
        if getattr(msg, 'photo', None):
            fid = msg.photo[-1].file_id
            return await client.send_photo(dest_chat_id, fid, caption=msg.caption or None, reply_markup=reply_markup)
        if getattr(msg, 'video', None):
            fid = msg.video.file_id
            return await client.send_video(dest_chat_id, fid, caption=msg.caption or None, reply_markup=reply_markup)
        if getattr(msg, 'document', None):
            fid = msg.document.file_id
            return await client.send_document(dest_chat_id, fid, caption=msg.caption or None, reply_markup=reply_markup)
        if getattr(msg, 'animation', None):
            fid = msg.animation.file_id
            return await client.send_animation(dest_chat_id, fid, caption=msg.caption or None, reply_markup=reply_markup)
        if getattr(msg, 'audio', None):
            fid = msg.audio.file_id
            return await client.send_audio(dest_chat_id, fid, caption=msg.caption or None, reply_markup=reply_markup)
        if getattr(msg, 'voice', None):
            fid = msg.voice.file_id
            return await client.send_voice(dest_chat_id, fid, caption=msg.caption or None, reply_markup=reply_markup)
        if getattr(msg, 'sticker', None):
            fid = msg.sticker.file_id
            return await client.send_sticker(dest_chat_id, fid)
    except Exception as e:
        logger.exception("Resend-by-type failed for preview: %s", e)
    return None


def build_start_kb():
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🌐 Visit Website", url="https://flix-vault-self.vercel.app/")], # Apni website ka link yahan daal dein
            [InlineKeyboardButton("Create Post", callback_data="create_post")],
            [InlineKeyboardButton("About", callback_data="about"), InlineKeyboardButton("Help", callback_data="help")],
            [InlineKeyboardButton("Close", callback_data="close")]
        ]
    )
    return kb


def parse_url_buttons(text: str):
    rows = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("|") if p.strip()]
        row = []
        for p in parts:
            if "-" not in p:
                continue
            label, url = p.split("-", 1)
            label = label.strip()
            url = url.strip()
            row.append(InlineKeyboardButton(label, url=url))
        if row:
            rows.append(row)
    return rows


def parse_reactions(text: str):
    emojis = [t for t in re.split(r"\s+|,|\\n", text.strip()) if t]
    return emojis


async def send_draft_menu(client, chat_id: int, uid: int):
    """Send or update an interactive draft menu to the admin with edit/remove options."""
    draft = DRAFTS.get(uid)
    if not draft:
        await client.send_message(chat_id, "No active draft.")
        return

    ctrl_kb = []
    ctrl_kb.append([
        InlineKeyboardButton("Edit URL Buttons", callback_data=f"edit_url|{uid}"),
        InlineKeyboardButton("Remove URL Buttons", callback_data=f"remove_url|{uid}")
    ])
    ctrl_kb.append([
        InlineKeyboardButton("Edit Reactions", callback_data=f"edit_react|{uid}"),
        InlineKeyboardButton("Remove Reactions", callback_data=f"remove_react|{uid}")
    ])
    ctrl_kb.append([
        InlineKeyboardButton("Preview", callback_data=f"preview_draft|{uid}"),
        InlineKeyboardButton("Post (Choose Channel)", callback_data=f"choose_channel|{uid}")
    ])
    ctrl_kb.append([InlineKeyboardButton("Cancel", callback_data=f"cancel_post|{uid}")])

    kb = InlineKeyboardMarkup(ctrl_kb)

    if draft['messages']:
        sent_any = False
        for i, m in enumerate(draft['messages']):
            rm = kb if i == 0 else None
            try:
                res = await _attempt_send_preview(client, chat_id, m, reply_markup=rm)
                if res:
                    sent_any = True
            except Exception as e:
                logger.exception("_attempt_send_preview failed for message: %s", e)
        if not sent_any:
            text = "Draft saved. (preview failed to resend media). Use the buttons below to edit or post."
            if draft.get('url_buttons'):
                text += f"\nURL buttons: {sum(len(r) for r in draft['url_buttons'])}"
            if draft.get('reactions'):
                text += f"\nReactions: {' '.join(draft['reactions'])}"
            await client.send_message(chat_id, text, reply_markup=kb)
    else:
        await client.send_message(chat_id, "Draft saved. Use the buttons below to edit or post.", reply_markup=kb)


async def post_draft_to_target(client, uid, target_id, reply_chat_id):
    """Helper to post a draft to a target channel id and notify the requester."""
    if uid not in DRAFTS:
        await client.send_message(reply_chat_id, "No active draft.")
        return
    draft = DRAFTS[uid]
    keyboard = []
    if draft.get('url_buttons'):
        keyboard.extend(draft['url_buttons'])
    kb = InlineKeyboardMarkup(keyboard) if keyboard else None

    posted_msg_id = None
    first = True
    for m in draft['messages']:
        try:
            if first:
                sent = await client.copy_message(chat_id=target_id, from_chat_id=m.chat.id, message_id=m.message_id, reply_markup=kb)
                posted_msg_id = sent.message_id
                first = False
            else:
                await client.copy_message(chat_id=target_id, from_chat_id=m.chat.id, message_id=m.message_id)
        except Exception as e:
            await client.send_message(reply_chat_id, f"Failed to post message: {e}")
            return

    if draft.get('reactions') and posted_msg_id:
        try:
            current_kb = []
            if draft.get('url_buttons'):
                current_kb.extend(draft['url_buttons'])
            row = []
            for e in draft['reactions']:
                b = e.encode('utf-8').hex()
                cbdata = f"react|{target_id}|{posted_msg_id}|{b}"
                row.append(InlineKeyboardButton(f"{e} 0", callback_data=cbdata))
            current_kb.append(row)
            await client.edit_message_reply_markup(target_id, posted_msg_id, reply_markup=InlineKeyboardMarkup(current_kb))
        except Exception:
            pass

    try:
        await db.save_post(target_id, posted_msg_id, emoji_order=draft.get('reactions'))
    except Exception:
        pass

    await client.send_message(reply_chat_id, "Posted successfully.")
    DRAFTS.pop(uid, None)


@Client.on_callback_query()
async def cb_handler(client, cb):
    data = cb.data
    uid = cb.from_user.id

    if data == "about":
        await cb.answer()
        await cb.message.edit_text(ABOUT_TXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back_start")]]))
        return

    if data == "help":
        await cb.answer()
        await cb.message.edit_text(HELP_TXT, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="back_start")]]))
        return

    if data == "close":
        await cb.answer("Closed")
        try:
            await cb.message.delete()
        except:
            pass
        return

    if data == "back_start":
        await cb.answer()
        try:
            await cb.message.edit_caption(caption=cb.message.caption or "", reply_markup=build_start_kb())
        except Exception:
            await cb.message.edit_text(cb.message.text or "", reply_markup=build_start_kb())
        return

    if data == "create_post":
        await cb.answer()
        if not is_admin(uid):
            await cb.message.reply_text("Only bot owner or admins can create posts.")
            return
        DRAFTS[uid] = {'messages': [], 'url_buttons': [], 'reactions': [], 'target': None}
        await cb.message.reply_text("Send me the message (text, media or album) you want to post. Send /cancel to abort.")
        try:
            msg = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            DRAFTS.pop(uid, None)
            await cb.message.reply_text("Timed out. Please start creating the post again.")
            return

        if msg.text and msg.text.lower() == "/cancel":
            DRAFTS.pop(uid, None)
            await msg.reply_text("Cancelled.")
            return

        messages = [msg]
        mgid = getattr(msg, 'media_group_id', None)
        if mgid:
            while True:
                try:
                    more = await client.listen(cb.message.chat.id, timeout=1)
                    if getattr(more, 'media_group_id', None) == mgid:
                        messages.append(more)
                    else:
                        break
                except asyncio.TimeoutError:
                    break
        DRAFTS[uid]['messages'] = messages

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("Add URL Buttons", callback_data="add_url")],
            [InlineKeyboardButton("Add Reaction Buttons", callback_data="add_react")],
            [InlineKeyboardButton("Preview", callback_data="preview"), InlineKeyboardButton("Post", callback_data="post_now")],
            [InlineKeyboardButton("Cancel", callback_data="cancel_post")]
        ])
        await msg.reply_text("Message saved. Choose next action:", reply_markup=kb)
        return

    if data == "cancel_post":
        if "|" in data:
            DRAFTS.pop(uid, None)
            await cb.answer("Cancelled")
            await cb.message.edit_text("Draft cancelled.")
            return
        DRAFTS.pop(uid, None)
        await cb.answer("Cancelled")
        await cb.message.edit_text("Draft cancelled.")
        return

    if data == "add_url":
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid not in DRAFTS:
            await cb.message.reply_text("No active draft. Start with Create Post.")
            return
        await cb.message.reply_text("Send me a list of URL buttons for the message. Use this format:\nButton text 1 - http://example.com | Button text 2 - http://...\nYou can use '|' to put buttons in same row. Send /done when finished or /cancel to abort.")
        try:
            msg = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            await cb.message.reply_text("Timed out. Returning to menu.")
            return
        if msg.text and msg.text.lower() == "/cancel":
            await msg.reply_text("Cancelled adding buttons.")
            return
        rows = parse_url_buttons(msg.text)
        if not rows:
            await msg.reply_text("Could not parse any buttons. Make sure format is: Label - URL | Label2 - URL2\nTry again.")
            return
        DRAFTS[uid]['url_buttons'] = rows
        await msg.reply_text("URL buttons saved.")
        await send_draft_menu(client, cb.message.chat.id, uid)
        return

    if data == "add_react":
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid not in DRAFTS:
            await cb.message.reply_text("No active draft. Start with Create Post.")
            return
        await cb.message.reply_text("Send emojis (space separated or in one message). Each emoji will become a reaction button. Send /done when finished or /cancel to abort.")
        try:
            msg = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            await cb.message.reply_text("Timed out. Returning to menu.")
            return
        if msg.text and msg.text.lower() == "/cancel":
            await msg.reply_text("Cancelled adding reactions.")
            return
        emojis = parse_reactions(msg.text)
        if not emojis:
            await msg.reply_text("No emojis detected. Try again.")
            return
        DRAFTS[uid]['reactions'] = emojis
        await msg.reply_text(f"Added {len(emojis)} reaction(s): {' '.join(emojis)}")
        await send_draft_menu(client, cb.message.chat.id, uid)
        return

    if data == "preview" or data.startswith("preview_draft"):
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid not in DRAFTS:
            await cb.message.reply_text("No active draft.")
            return
        draft = DRAFTS[uid]
        keyboard = []
        if draft['url_buttons']:
            keyboard.extend(draft['url_buttons'])
        if draft['reactions']:
            row = []
            for e in draft['reactions']:
                row.append(InlineKeyboardButton(f"{e}", callback_data="noop"))
            keyboard.append(row)
        kb = InlineKeyboardMarkup(keyboard) if keyboard else None

        for i, m in enumerate(draft['messages']):
            try:
                await _attempt_send_preview(client, cb.message.chat.id, m, reply_markup=kb if i == 0 else None)
            except Exception:
                logger.exception("_attempt_send_preview failed in preview flow")
        await cb.message.reply_text("This is a preview. Use Post to publish or add more buttons.")
        return

    if data == "post_now":
        await cb.answer()
        if uid not in DRAFTS:
            await cb.message.reply_text("No active draft.")
            return
        await cb.message.reply_text("Send the channel username (eg @channelusername) or channel ID (eg -10012345) where I should post. I must be admin in that channel.")
        try:
            ch = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            await cb.message.reply_text("Timed out. Post aborted.")
            return
        if ch.text and ch.text.lower() == "/cancel":
            await ch.reply_text("Cancelled.")
            return
        channel = ch.text.strip()
        try:
            target = await client.get_chat(channel)
        except Exception as e:
            await ch.reply_text("Could not find that channel. Make sure I am in the channel and provided the correct username or ID.")
            return
        try:
            member = await client.get_chat_member(target.id, (await client.get_me()).id)
            if not (str(member.status).lower() in ("administrator", "creator") or getattr(member, 'can_post_messages', False)):
                await ch.reply_text("I am not an admin in that channel. Please make me admin (with right to post/edit) and try again.")
                return
        except Exception:
            pass

        await post_draft_to_target(client, uid, target.id, cb.message.chat.id)
        return

    if data.startswith("choose_channel"):
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        channels = await db.list_channels()
        if not channels:
            await cb.message.reply_text("No configured channels. Use /add_channel first or specify a channel id manually with 'Post Now' option.")
            return
        rows = []
        for c in channels:
            ch_id = c.get('_id')
            label = str(ch_id)
            try:
                chinfo = await client.get_chat(ch_id)
                label = chinfo.title or chinfo.username or str(ch_id)
            except Exception:
                pass
            rows.append([InlineKeyboardButton(label, callback_data=f"post_to|{uid}|{ch_id}")])
        rows.append([InlineKeyboardButton("Custom channel (enter id)", callback_data=f"post_custom|{uid}")])
        rows.append([InlineKeyboardButton("Back", callback_data=f"preview_draft|{uid}")])
        await cb.message.reply_text("Choose channel:", reply_markup=InlineKeyboardMarkup(rows))
        return

    if data.startswith("post_to|"):
        await cb.answer()
        try:
            _, _uid, ch_id = data.split("|", 2)
            uid = int(_uid)
            ch_id = int(ch_id)
        except Exception:
            await cb.message.reply_text("Invalid channel selection.")
            return
        try:
            member = await client.get_chat_member(ch_id, (await client.get_me()).id)
            member_info = f"status={getattr(member, 'status', None)} can_post_messages={getattr(member, 'can_post_messages', None)}"
            if not (str(getattr(member, 'status', '')).lower() in ("administrator", "creator") or getattr(member, 'can_post_messages', False)):
                await cb.message.reply_text(f"I am not an admin in that channel ({member_info}). Please make me admin (with right to post/edit) and try again.")
                return
        except Exception as e:
            logger.exception("Error checking chat member in post_to")
            await cb.message.reply_text(f"Could not verify admin status due to error: {e}")
            return
        await post_draft_to_target(client, uid, ch_id, cb.message.chat.id)
        return

    if data.startswith("post_custom|"):
        await cb.answer()
        _, _uid = data.split("|", 1)
        uid = int(_uid)
        await cb.message.reply_text("Send the channel username (eg @channelusername) or channel ID (eg -10012345) where I should post. I must be admin in that channel.")
        try:
            ch = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            await cb.message.reply_text("Timed out. Post aborted.")
            return
        if ch.text and ch.text.lower() == "/cancel":
            await ch.reply_text("Cancelled.")
            return
        try:
            target = await client.get_chat(ch.text.strip())
            ch_id = target.id
        except Exception:
            await cb.message.reply_text("Could not find that channel. Make sure I am in the channel and provided the correct username or ID.")
            return
        try:
            member = await client.get_chat_member(ch_id, (await client.get_me()).id)
            member_info = f"status={getattr(member, 'status', None)} can_post_messages={getattr(member, 'can_post_messages', None)}"
            if not (str(getattr(member, 'status', '')).lower() in ("administrator", "creator") or getattr(member, 'can_post_messages', False)):
                await cb.message.reply_text(f"I am not an admin in that channel ({member_info}). Please make me admin (with right to post/edit) and try again.")
                return
        except Exception as e:
            logger.exception("Error checking chat member in post_custom")
            await cb.message.reply_text(f"Could not verify admin status due to error: {e}")
            return
        await post_draft_to_target(client, uid, ch_id, cb.message.chat.id)
        return

    if data.startswith("edit_url|") or data.startswith("edit_url"):
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid not in DRAFTS:
            await cb.message.reply_text("No active draft.")
            return
        await cb.message.reply_text("Send me a list of URL buttons (Label - URL | Label2 - URL2). Send /cancel to abort.")
        try:
            msg = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            await cb.message.reply_text("Timed out.")
            return
        if msg.text and msg.text.lower() == "/cancel":
            await msg.reply_text("Cancelled.")
            return
        rows = parse_url_buttons(msg.text)
        if not rows:
            await msg.reply_text("Could not parse any buttons. No changes made.")
            return
        DRAFTS[uid]['url_buttons'] = rows
        await msg.reply_text("URL buttons updated.")
        await send_draft_menu(client, cb.message.chat.id, uid)
        return

    if data.startswith("remove_url|") or data == "remove_url":
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid in DRAFTS:
            DRAFTS[uid]['url_buttons'] = []
        await cb.message.reply_text("URL buttons removed.")
        await send_draft_menu(client, cb.message.chat.id, uid)
        return

    if data.startswith("edit_react|") or data == "edit_react":
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid not in DRAFTS:
            await cb.message.reply_text("No active draft.")
            return
        await cb.message.reply_text("Send emojis (space separated) to set reaction buttons. Send /cancel to abort.")
        try:
            msg = await client.listen(cb.message.chat.id, timeout=300)
        except asyncio.TimeoutError:
            await cb.message.reply_text("Timed out.")
            return
        if msg.text and msg.text.lower() == "/cancel":
            await msg.reply_text("Cancelled.")
            return
        emojis = parse_reactions(msg.text)
        if not emojis:
            await msg.reply_text("No emojis detected. No changes made.")
            return
        DRAFTS[uid]['reactions'] = emojis
        await msg.reply_text(f"Reactions updated: {' '.join(emojis)}")
        await send_draft_menu(client, cb.message.chat.id, uid)
        return

    if data.startswith("remove_react|") or data == "remove_react":
        await cb.answer()
        if "|" in data:
            _, _uid = data.split("|", 1)
            uid = int(_uid)
        if uid in DRAFTS:
            DRAFTS[uid]['reactions'] = []
        await cb.message.reply_text("Removed reactions.")
        await send_draft_menu(client, cb.message.chat.id, uid)
        return

    if data.startswith("react|"):
        await cb.answer()
        try:
            _, ch_id_s, msg_id_s, emo_hex = data.split("|", 3)
            ch_id = int(ch_id_s)
            msg_id = int(msg_id_s)
            emoji = bytes.fromhex(emo_hex).decode('utf-8')
        except Exception:
            await cb.answer("Invalid reaction data.")
            return

        try:
            await db.increment_reaction(ch_id, msg_id, emoji)
        except Exception:
            pass

        try:
            msg = await client.get_messages(ch_id, msg_id)
            current_kb = []
            if msg.reply_markup and getattr(msg.reply_markup, 'inline_keyboard', None):
                for row in msg.reply_markup.inline_keyboard:
                    is_react_row = False
                    for btn in row:
                        if getattr(btn, 'callback_data', None) and str(btn.callback_data).startswith('react|'):
                            is_react_row = True
                            break
                    if not is_react_row:
                        new_row = []
                        for btn in row:
                            if getattr(btn, 'url', None):
                                new_row.append(InlineKeyboardButton(btn.text, url=btn.url))
                            else:
                                new_row.append(InlineKeyboardButton(btn.text, callback_data=btn.callback_data))
                        current_kb.append(new_row)
            else:
                current_kb = []

            post = await db.get_post(ch_id, msg_id)
            emoji_order = post.get('emoji_order') if post else []
            react_row = []
            for e in emoji_order or [emoji]:
                b = e.encode('utf-8').hex()
                cnt = 0
                if post and post.get('reactions'):
                    cnt = post.get('reactions', {}).get(e, 0)
                react_row.append(InlineKeyboardButton(f"{e} {cnt}", callback_data=f"react|{ch_id}|{msg_id}|{b}"))
            if react_row:
                current_kb.append(react_row)

            await client.edit_message_reply_markup(ch_id, msg_id, reply_markup=InlineKeyboardMarkup(current_kb))
        except Exception:
            pass
        return


@Client.on_message(filters.private & filters.command("cmds"))
async def cmds_handler(client, message):
    txt = (
        "Available commands:\n"
        "/create_post - Start the create-post flow\n"
        "/send - Send post messages to a selected channel\n"
        "/add_channel - Add a channel where bot can post\n"
        "/remove_channel - Remove a channel\n"
        "/list_channels - List configured channels\n"
        "/diag_channels - Check bot admin status in configured channels\n"
        "/cmds - Show this message\n"
    )
    await message.reply_text(txt)


@Client.on_message(filters.private & filters.command("add_channel"))
async def add_channel_handler(client, message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text("Only owner or admins can add channels.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        channel = args[1].strip()
    else:
        await message.reply_text("Send the channel username or ID to add.")
        try:
            reply = await client.listen(message.chat.id, timeout=60)
            channel = reply.text.strip()
        except asyncio.TimeoutError:
            await message.reply_text("Timed out.")
            return
    try:
        ch = await client.get_chat(channel)
        await db.add_channel(ch.id, uid)
        await message.reply_text(f"Added channel: {ch.title or ch.username} ({ch.id})")
    except Exception as e:
        await message.reply_text(f"Failed to add channel: {e}")


@Client.on_message(filters.private & filters.command("remove_channel"))
async def remove_channel_handler(client, message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text("Only owner or admins can remove channels.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        channel = args[1].strip()
    else:
        await message.reply_text("Send the channel username or ID to remove.")
        try:
            reply = await client.listen(message.chat.id, timeout=60)
            channel = reply.text.strip()
        except asyncio.TimeoutError:
            await message.reply_text("Timed out.")
            return
    try:
        ch = await client.get_chat(channel)
        await db.remove_channel(ch.id)
        await message.reply_text(f"Removed channel: {ch.title or ch.username} ({ch.id})")
    except Exception as e:
        await message.reply_text(f"Failed to remove channel: {e}")


@Client.on_message(filters.private & filters.command("list_channels"))
async def list_channels_handler(client, message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text("Only owner or admins can list channels.")
        return
    channels = await db.list_channels()
    if not channels:
        await message.reply_text("No channels configured.")
        return
    text = "Configured channels:\n"
    for c in channels:
        text += f"- {c.get('added_by')} -> {c.get('_id')}\n"
    await message.reply_text(text)


@Client.on_message(filters.private & filters.command("diag_channels"))
async def diag_channels(client, message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text("Only owner or admins can run diagnostics.")
        return
    channels = await db.list_channels()
    if not channels:
        await message.reply_text("No configured channels.")
        return
    lines = []
    me = await client.get_me()
    for c in channels:
        ch_id = c.get('_id')
        try:
            chinfo = await client.get_chat(ch_id)
            member = await client.get_chat_member(ch_id, me.id)
            lines.append(f"{chinfo.title or chinfo.username or ch_id}: status={member.status} can_post={getattr(member,'can_post_messages',None)}")
        except Exception as e:
            logger.exception("diag check failed for %s", ch_id)
            lines.append(f"{ch_id}: error={e}")
    await message.reply_text("\n".join(lines))


@Client.on_message(filters.private & filters.command("send"))
async def send_cmd(client, message):
    uid = message.from_user.id
    if not is_admin(uid):
        await message.reply_text("Only owner or admins can send messages.")
        return
    DRAFTS[uid] = {'messages': [], 'url_buttons': [], 'reactions': [], 'options': {}, 'target': None}

    channels = await db.list_channels()
    if not channels:
        await message.reply_text("No configured channels. Use /add_channel to add one first.")
        return
    rows = []
    for c in channels:
        ch_id = c.get('_id')
        label = str(ch_id)
        try:
            chinfo = await client.get_chat(ch_id)
            label = chinfo.title or chinfo.username or str(ch_id)
        except Exception:
            pass
        rows.append([InlineKeyboardButton(label, callback_data=f"send_select|{uid}|{ch_id}")])
    rows.append([InlineKeyboardButton("Custom channel (enter id)", callback_data=f"send_custom|{uid}")])
    await message.reply_text("Choose channel to send to:", reply_markup=InlineKeyboardMarkup(rows))
    return


# --- 1. ADMIN FILE UPLOAD HANDLER (Auto Code Generator) ---
@Client.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def handle_admin_file_upload(client, message):
    uid = message.from_user.id
    if not is_admin(uid):
        return  # Agar user admin nahi hai toh yeh handler kuch nahi karega
    
    # Media file extract karein
    media = message.document or message.video or message.audio or (message.photo[-1] if message.photo else None)
    if not media:
        return
    
    file_id = media.file_id
    file_name = getattr(media, "file_name", "FlixVault_Movie_File")
    
    # Database mein save karke automatic bot_code generate karein
    bot_code = await db.save_file_with_auto_code(file_id, file_name)
    
    await message.reply_text(
        f"<b>✅ File Saved Successfully!</b>\n\n"
        f"📁 <b>File Name:</b> {file_name}\n"
        f"🔑 <b>Bot Code:</b> <code>{bot_code}</code>\n\n"
        f"<i>Is code ko copy karein aur apni FlixVault website ke admin panel mein movie add karte waqt paste kar dein!</i>"
    )


# --- 2. TOKEN START HANDLER (Website Purchase Delivery & Normal Start) ---
@Client.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message):
    text = message.text
    args = text.split(" ")
    
    # Check karein ki kya start command ke sath token aaya hai (jaise /start TOKEN_XYZ)
    if len(args) > 1:
        token = args[1].strip()
        user_id = message.from_user.id
        
        # Database mein token verify aur consume karein (No time expiry, single-use)
        result = await db.verify_and_consume_token(token, user_id)
        
        if not result.get("success"):
            await message.reply_text(result.get("error", "❌ Invalid or expired link."))
            return
        
        bot_code = result.get("bot_code")
        
        # bot_code ke zariye database se file find karein
        file_doc = await db.get_file_by_code(bot_code)
        
        if not file_doc:
            await message.reply_text("❌ Movie file database mein nahi mili. Kripya admin se sampark karein.")
            return
        
        file_id = file_doc.get("file_id")
        file_name = file_doc.get("file_name", "Movie")
        
        await message.reply_text(f"✅ Payment Verified! Aapki movie send ki ja rahi hai: <b>{file_name}</b>...")
        
        try:
            # User ke personal DM mein file deliver karein
            await client.send_cached_media(chat_id=user_id, file_id=file_id)
        except Exception as e:
            try:
                # Fallback agar cached media fail ho jaye
                await client.send_document(chat_id=user_id, document=file_id)
            except Exception as err:
                await message.reply_text(f"❌ File send karne mein error aayi: {err}")
        return

    # Normal Start Command Behavior (Agar bina token ke aaye)
    mention = message.from_user.mention if message.from_user else "user"
    try:
        await message.reply_photo(photo=START_PIC, caption=START_MSG.format(mention=mention), reply_markup=build_start_kb())
    except Exception:
        await message.reply_text(START_MSG.format(mention=mention), reply_markup=build_start_kb())
