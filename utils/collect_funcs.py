import asyncio
import re

from aiogram import Bot
from pyrogram import Client
from pyrogram.enums import ChatType
from pyrogram.errors import FloodWait

from config_data.config import Config, load_config


config: Config = load_config()

api_id = config.user_bot.api_id
api_hash = config.user_bot.api_hash


def find_telegram_link_strict(text):
    """
    Находит первую валидную Telegram-ссылку в тексте с учетом правил Telegram.
    Возвращает строку с ссылкой или None, если ссылок нет.
    """
    # Для ссылок t.me/...
    link_pattern = r'(?:https?://)?t\.me/[a-zA-Z0-9_]{1,}'

    # Для username с валидацией
    username_pattern = r'@[a-zA-Z][a-zA-Z0-9_]{4,31}(?<!_)'

    pattern = f'{link_pattern}|{username_pattern}'

    match = re.search(pattern, text)

    if match:
        link = match.group()
        cleaned = re.sub(r'[.,)!?]*$', '', link)

        if cleaned.startswith('@'):
            # Дополнительная проверка на двойные подчеркивания
            if '__' not in cleaned[1:]:
                cleaned = f"t.me/{cleaned[1:]}"
            else:
                return None  # Невалидный username

        return cleaned

    return None


async def _check_personal_channel(app: Client, username: str) -> dict | None:
    await asyncio.sleep(0.5)
    user = await app.get_chat(username)
    await asyncio.sleep(1)
    if user.personal_channel:
        return {
            'username': '@' + user.username,
            'bio': user.bio,
            'channel': user.personal_channel.invite_link if
            user.personal_channel.invite_link else 'https://t.me/' + user.personal_channel.username if
            user.personal_channel.username else '-'
        }
    if user.bio:
        link = find_telegram_link_strict(user.bio)
        if link:
            return {
                'username': '@' + user.username,
                'bio': user.bio,
                'channel': link
            }
    return None


async def collect_users_base(account: str, bot: Bot, user_id: int, channel: str | int) -> list[str] | None:
    users = []
    try:
        app = Client(account, api_id=api_id, api_hash=api_hash)
    except Exception as err:
        print(err)
        await bot.send_message(
            chat_id=user_id,
            text='❗️Сессия вашего аккаунта слетела, пожалуйста удалите и добавьте в бота данный аккаунт повторно'
        )
        return
    async with app:
        chat = await app.get_chat(channel)
        if chat.type == ChatType.CHANNEL:
            channel = chat.linked_chat.id if chat.linked_chat else None
        if not channel:
            return None
        new_users = []
        members = app.get_chat_members(channel)
        try:
            async for user in members:
                if user.user.username and not user.user.is_bot and not user.user.is_contact and not user.user.verification_status.is_fake:
                    if user.user.username not in users:
                        new_users.append(user.user.username)
            if len(new_users) > 30:
                users.extend(new_users)
            else:
                async for message in app.get_chat_history(channel, limit=10000):
                    user = message.from_user
                    if user and (not user.is_bot and not user.verification_status.is_fake) and user.username and user.username not in users:
                        if user.username not in new_users:
                            new_users.append(user.username)
                users.extend(new_users)
        except Exception as err:
            print(err, err.args, err.__traceback__)

    return users if users else None


async def filter_user_base(account: str, channel: str | int, user_id: int, bot: Bot):
    base = await collect_users_base(account, bot, user_id, channel)
    if not base:
        return None
    await asyncio.sleep(2)
    users = []
    try:
        app = Client(account, api_id=api_id, api_hash=api_hash)
        await app.start()
    except Exception as err:
        print(err)
        return
    for user in base:
        try:
            new_user = await _check_personal_channel(app, user)
            if new_user:
                users.append(new_user)
        except FloodWait as err:
            sleep = err.value
            await asyncio.sleep(sleep + 2)
    await app.stop()
    return users


async def get_channels(account: str, bot: Bot, user_id: int):
    try:
        app = Client(account, api_id=api_id, api_hash=api_hash)
    except Exception as err:
        print(err)
        await bot.send_message(
            chat_id=user_id,
            text='❗️Сессия вашего аккаунта слетела, пожалуйста удалите и добавьте в бота данный аккаунт повторно'
        )
        return
    async with app:
        dialogs = []
        async for dialog in app.get_dialogs():
            if dialog.chat.type not in [ChatType.BOT, ChatType.PRIVATE]:
                dialogs.append(
                    (
                        dialog.chat.title,
                        dialog.chat.id
                    )
                )
        return dialogs
