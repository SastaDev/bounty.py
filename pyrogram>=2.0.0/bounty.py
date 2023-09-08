# Author: https://github.com/SastaDev
# Created on: Thu, Sep 7 2023.
# Support chat: https://t.me/KangersChat
# For pyrogram v2.0.0 and above.

from os import remove as delete_file
from typing import Any, BinaryIO, Dict, Optional, Tuple, Union
from time import time
from uuid import uuid4

from motor.motor_asyncio import AsyncIOMotorCollection
from httpx import AsyncClient, Response

from pyrogram.enums import MessageMediaType
from pyrogram.types import (
    Chat, Message, User,
    InlineKeyboardMarkup, InlineKeyboardButton,
    )
from pyrogram import Client, filters

# Replace `YourRobot` with your robot's name.
from YourRobot.mongo import db
from YourRobot import pbot

API_URL: str = "https://sasta-api.vercel.app"
API_METHOD: str = "bounty"

httpx_client: AsyncClient = AsyncClient(timeout=120)

class DB:
    bounty_stats: AsyncIOMotorCollection = db.bounty_stats
    
    @classmethod
    def get_highest_bounty(cls, user_id: int) -> Optional[Tuple[int, str]]:
        result: Optional[Dict[str, Any]] = cls.bounty_stats.find_one({"user_id": user_id})
        if not result:
            return None, None
        return result["highest_bounty"], result["image_link"]
    
    @classmethod
    def set_highest_bounty(cls, user_id: int, highest_bounty: int, image_link: str) -> None:
        update: Dict[str, Dict[str, Any]] = {
            "$set": {
                "highest_bounty": highest_bounty,
                "image_link": image_link
            }
        }
        cls.bounty_stats.update_one({"user_id": user_id}, update, upsert=True)

class STRINGS:
    SYNTAX: str = """
<b>Syntax:</b>
- <b>/bounty</b> <code>{image_url}</code> <code>{reply to media}</code>

- <code>image_url</code> is <i>optional</i>, uses current set profile picture.
- <code>reply to media</code> is <i>optional</i>, and can be used to set the replied message's photo or document as the profile picture in the poster.

ℹ️ <b>Note:</b> Ensure your main profile picture is an image, not a video or any other format.
    """
    
    UNSUPPORTED_REPLIED_MEDIA: str = "⚠️ <b>Unsupported replied media!</b>\nℹ️ Only photo and document is supported."
    
    NO_PROFILE_PICTURE: str = "ℹ️ You <b>don't</b> seem to have a profile picture. (or perhaps you've blocked me or your profile privacy restrictions.)"
    
    DOWNLOADING_PHOTO: str = "⏳ <b>Downloading profile picture...</b>"
    UPLOADING_TO_API_SERVER: str = "📡 Uploading profile picture to <b>API Server</b>... 📶"
    PARSING_RESULT: str = "💻 <b>Parsing result...</b>"
    
    EXCEPTION_OCCURRED: str = "❌ <b>Exception occurred!</b>\n\n<b>Exception:</b> {}"
    SUPPORT_CHAT: str = "🆘 <b>Support Chat:</b> @KangersChat"
    
    RESULT_CAPTION: str = """
💰 <b>Bounty Prize:</b> <code>${bounty_prize}</code>
🔗 <b>Image Link:</b> <a href="{image_link}">Link</a>

⌛️ <b>Time Taken:</b> <code>{time_taken}</code> seconds.
🧑‍💻 <b>Credits:</b> @KangersNetwork
    """
    IMAGE_LINK: str = "↗️ Open Image Link"
    
    NEW_RECORD: str = """
🆕 <b>NEW RECORD!</b>

🎉 <b>Congratulations!</b> This is your highest bounty prize! 🥳

💰 <b>Old Highest Bounty:</b> <code>{old_highest_bounty}</code>
💰 <b>Highest Bounty Prize:</b> <code>{new_highest_bounty}</code>
    """

async def download(url: str, file_name: str) -> None:
    response = await httpx_client.get(url)
    with open(file_name, "wb") as file:
        file.write(response.content)

async def request(name: str, data: Union[BinaryIO, str]) -> Dict[str, str]:
    url = f"{API_URL}/{API_METHOD}"
    if isinstance(data, str):
        params: Dict[str, str] = {
            "name": name,
            "image_url": data
        }
        response: Response = await httpx_client.get(url, params=params)
        return response
    params: Dict[str, str] = {"name": name}
    files: Dict[str, str] = {"file": data}
    response: Response = await httpx_client.post(url, params=params, files=files)
    return response

@pbot.on_message(filters.command("bounty"))
async def on_bounty(client: Client, message: Message) -> None:
    sender: Union[User, Chat] = message.from_user or message.sender_chat
    if isinstance(sender, User):
        name: str = f"{sender.first_name} {sender.last_name}" if sender.last_name else sender.first_name
    else:
        name: str = sender.title
    
    status_msg: Message = await message.reply(STRINGS.DOWNLOADING_PHOTO)
    start_time: float = time()
    
    file_path: str = f"temp_downloads/{uuid4()}"
    splited_text = message.text.split()
    if len(splited_text) > 1:
        image_url: str = splited_text[1]
        try:
            await download(image_url, file_name=file_path)
        except Exception as exc:
            text = STRINGS.EXCEPTION_OCCURRED.format(exc)
            await message.reply(text)
            await status_msg.delete()
            try:
                delete_file(file_path)
            except FileNotFoundError:
                pass
            return
    else:
        if (message.reply_to_message and
            message.reply_to_message.media and
            message.reply_to_message.media not in (MessageMediaType.PHOTO, MessageMediaType.DOCUMENT)
            ):
            await message.reply(STRINGS.UNSUPPORTED_REPLIED_MEDIA)
            await status_msg.delete()
            return
        if not sender.photo:
            text: str = STRINGS.NO_PROFILE_PICTURE + "\n" + STRINGS.SYNTAX
            await message.reply(text)
            await status_msg.delete()
            return
        
        if message.reply_to_message and message.reply_to_message.media:
            await message.reply_to_message.download(file_path)
        else:
            big_file_id: str = sender.photo.big_file_id
            await client.download_media(big_file_id, file_path)
    
    await status_msg.edit(STRINGS.UPLOADING_TO_API_SERVER)
    try:
        with open(file_path, "rb") as file:
            response: Response = await request(name, data=file.read())
        delete_file(file_path)
    except Exception as exc:
        text = STRINGS.EXCEPTION_OCCURRED.format(exc) + "\n" + STRINGS.SUPPORT_CHAT
        await message.reply(text)
        await status_msg.delete()
        delete_file(file_path)
        return
    
    if response.status_code == 404:
        text: str = STRINGS.EXCEPTION_OCCURRED.format(response.json()["error"])  + "\n" + STRINGS.SUPPORT_CHAT
        await message.reply(text)
        await status_msg.delete()
        return
    elif response.status_code != 200:
        text: str = STRINGS.EXCEPTION_OCCURRED.format(response.text)  + "\n" + STRINGS.SUPPORT_CHAT
        await message.reply(text)
        await status_msg.delete()
        return
    
    await status_msg.edit(STRINGS.PARSING_RESULT)
    
    end_time: float = time() - start_time
    time_taken: str = "{:.2f}".format(end_time)
    
    response_json: Dict[str, str] = response.json()
    
    # Replaces `telegra.ph` with `te.legra.ph` in the URL due to blocking of `telegra.ph` in certain regions.
    bounty_poster_url: str = response_json["url"].replace("telegra.ph", "te.legra.ph")
    bounty_prize: str = "{:,}".format(response_json["prize"])
    
    caption: str = STRINGS.RESULT_CAPTION.format(
        bounty_prize=bounty_prize,
        image_link=bounty_poster_url,
        time_taken=time_taken
        )
    buttons: List[List[InlineKeyboardButton]] = [
        [InlineKeyboardButton(STRINGS.IMAGE_LINK, url=bounty_poster_url)]
        ]
    await message.reply_photo(
        photo=bounty_poster_url,
        caption=caption,
        reply_markup=InlineKeyboardMarkup(buttons)
        )
    await status_msg.delete()
    highest_bounty: Optional[int]
    _: Optional[str]
    highest_bounty, _ = DB.get_highest_bounty(sender.id)
    if not highest_bounty:
        DB.set_highest_bounty(sender.id, response_json["prize"], response_json["url"])
    elif response_json["prize"] > highest_bounty:
        DB.set_highest_bounty(sender.id, response_json["prize"], bounty_poster_url)
        text: str = STRINGS.NEW_RECORD.format(
            old_highest_bounty="{:,}".format(highest_bounty),
            new_highest_bounty=bounty_prize
            )
        await message.reply(text)

@pbot.on_message(filters.command("bounty_stats"))
async def on_bounty_stats(client: Client, message: Message) -> None:
    if message.reply_to_message:
        sender: Union[User, Chat] = message.reply_to_message.from_user or message.reply_to_message.sender_chat
    else:
        sender: Union[User, Chat] = message.from_user or message.sender_chat
    
    highest_bounty: Optional[int]
    poster_link: Optional[str]
    highest_bounty, poster_link = DB.get_highest_bounty(sender.id)
    if highest_bounty:
        highest_bounty = "{:,}".format(highest_bounty)
    else:
        highest_bounty = "0"
    
    text: str = "💰 <b>Bounty Stats:</b> 📊\n"
    if isinstance(sender, Chat):
        profile_link: str = f"https://t.me/{sender.username}" if sender.username else f"tg://openmessage?chat_id={str(sender.id).replace('-100', '').replace('-', '')}"
        text += f"""
• <b>Title:</b> {sender.title}
• <b>Chat ID:</b> {sender.id}
• <b>Profile Link:</b> <a href="{profile_link}">Link</a>
        """
    else:
        profile_link: str = f"https://t.me/{sender.username}" if sender.username else f"tg://user?id={sender.id}"
        text += f"""
• <b>First name:</b> {sender.first_name}
• <b>Last name:</b> {sender.last_name}
• <b>User ID:</b> {sender.id}
• <b>Profile Link:</b> <a href="{profile_link}">Link</a>
        """
    text += f"\n• <b>Highest Bounty:</b> <code>${highest_bounty}</code>"
    if poster_link:
        text += f'\n• <b>Poster Link:</b> <a href="{poster_link}">Link</a>'
    
    await message.reply(text)

__mod_name__: str = "Bounty Poster"

__help__: str = """
💰 *Bounty Poster*

Generates a Wanted Bounty Poster with the user's name (first name & last name) or chat's title.

A random 💰 bounty prize written inside.

• Inspired from *One Piece* (Japanese Manga and Anime).

• *Usage:*
- */bounty* `<image_url>`, `<reply to media>`
- `image_url` is optional, uses current set profile picture.
- `reply to media` is optional, and can be used to set the replied message's photo or document as the profile picture in the poster.

ℹ️ *Note:* Ensure your main profile picture is an image, not a video or any other format.
"""