import asyncio
import re
from datetime import datetime

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
            'user_id': user.id,
            'username': '@' + user.username if user.username else '-',
            'bio': user.bio,
            'channel': user.personal_channel.invite_link if
            user.personal_channel.invite_link else 'https://t.me/' + user.personal_channel.username if
            user.personal_channel.username else '-'
        }
    if user.bio:
        link = find_telegram_link_strict(user.bio)
        if link:
            return {
                'user_id': user.id,
                'username': '@' + user.username if user.username else '-',
                'bio': user.bio,
                'channel': link
            }
    return None


progress_messages = {}


async def send_progress_update(bot: Bot, user_id: int, current: int, total: int, found_count: int):
    """Отправляет/обновляет сообщение о прогрессе проверки пользователей"""
    try:
        percentage = (current / total) * 100 if total > 0 else 0

        message = (
            f"🔍 **Проверка пользователей на блоги**\n"
            f"✅ Проверено: {current}/{total} ({percentage:.1f}%)\n"
            f"📊 Найдено с блогами: {found_count}\n"
            f"⏱️ Актуально на: {datetime.now().strftime('%H:%M:%S')}"
        )

        # Если сообщение уже существует - редактируем, иначе создаем новое
        if user_id in progress_messages:
            try:
                await bot.edit_message_text(
                    chat_id=user_id,
                    message_id=progress_messages[user_id],
                    text=message
                )
            except:
                # Если редактирование не удалось, отправляем новое сообщение
                msg = await bot.send_message(chat_id=user_id, text=message)
                progress_messages[user_id] = msg.message_id
        else:
            msg = await bot.send_message(chat_id=user_id, text=message)
            progress_messages[user_id] = msg.message_id

    except Exception as e:
        print(f"Ошибка отправки прогресса: {e}")


async def collect_users_base(account: str, bot: Bot, user_id: int, channel: str | int, user_ids: list[int]) -> list[
                                                                                                                   str] | None:
    """Сбор базы пользователей (без детального прогресса)"""
    users = []
    try:
        app = Client(account, api_id=api_id, api_hash=api_hash)
    except Exception as err:
        print(err)
        await bot.send_message(
            chat_id=user_id,
            text='❗️Сессия вашего аккаунта слетела, пожалуйста удалите и добавьте в бота данный аккаунт повторно'
        )
        return None

    async with app:
        chat = await app.get_chat(channel)
        if chat.type == ChatType.CHANNEL:
            channel = chat.linked_chat.id if chat.linked_chat else None
            print(channel)
        if not channel:
            return None

        new_users = []
        members = app.get_chat_members(channel)

        try:
            # Отправляем уведомление о начале сбора
            await bot.send_message(
                chat_id=user_id,
                text="🔄 Начинаю сбор базы пользователей с канала..."
            )

            async for user in members:
                if user.user.username and not user.user.is_bot and not user.user.is_contact and not user.user.verification_status.is_fake:
                    if user.user.username not in users and user.user.id not in user_ids:
                        new_users.append(user.user.username)

            if len(new_users) > 30:
                users.extend(new_users)
            else:
                attempts = 0
                max_attempts = 5

                while attempts < max_attempts:
                    try:
                        async for message in app.get_chat_history(channel, limit=10000):
                            user = message.from_user
                            if user and (
                                    not user.is_bot and not user.verification_status.is_fake) and user.username and user.username not in users:
                                if user.username not in new_users and user.id not in user_ids:
                                    new_users.append(user.username)
                        # Если дошли до этой точки - успешно собрали историю
                        break

                    except FloodWait as e:
                        wait_time = e.value
                        attempts += 1
                        if attempts < max_attempts:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"⏳ Получена ошибка FloodWait. Жду {wait_time} секунд перед повторной попыткой {attempts}/{max_attempts}..."
                            )
                            await asyncio.sleep(wait_time + 1)  # +1 секунда для надежности
                        else:
                            await bot.send_message(
                                chat_id=user_id,
                                text=f"❌ Не удалось собрать историю сообщений после {max_attempts} попыток. Продолжаю с тем, что удалось собрать."
                            )
                    except Exception as e:
                        print(f"Ошибка при сборе истории: {e}")
                        break

                users.extend(new_users)

        except Exception as err:
            print(err, err.args, err.__traceback__)

    # Уведомление о завершении сбора
    await bot.send_message(
        chat_id=user_id,
        text=f"✅ Сбор базы завершен! Найдено пользователей: {len(users)}\n"
             f"🕒 Приступаю к проверке на наличие блогов..."
    )

    return users if users else None


async def filter_user_base(account: str, channel: str | int, user_id: int, bot: Bot, users: list[dict]):
    """Основная функция фильтрации с прогресс-отчетами"""
    user_ids = [user.get('id') for user in users]
    base = await collect_users_base(account, bot, user_id, channel, user_ids)
    if not base:
        return None

    await asyncio.sleep(2)
    filtered_users = []

    try:
        app = Client(account, api_id=api_id, api_hash=api_hash)
        await app.start()
    except Exception as err:
        print(err)
        return None

    total_users = len(base)
    processed = 0
    found_count = 0

    # Начальное сообщение о начале проверки
    await send_progress_update(bot, user_id, 0, total_users, 0)

    for i, username in enumerate(base):
        try:
            new_user = await _check_personal_channel(app, username)
            if new_user:
                filtered_users.append(new_user)
                found_count += 1

            processed += 1

            # Обновляем прогресс:
            # - Каждые 20 пользователей
            # - Каждые 10% прогресса
            # - На последних 10 пользователях (каждого)
            # - На каждом пользователе в первых 50 (для маленьких баз)
            should_update = (
                    processed % 20 == 0 or  # Каждые 20 пользователей
                    processed <= 50 or  # Первые 50 пользователей - чаще
                    total_users - processed <= 10 or  # Последние 10 пользователей
                    processed == total_users  # Финальное обновление
            )

            if should_update:
                await send_progress_update(bot, user_id, processed, total_users, found_count)

        except FloodWait as err:
            sleep = err.value
            # Уведомляем о паузе
            await bot.send_message(
                chat_id=user_id,
                text=f"⏸️ Обнаружена пауза от Telegram: {sleep} секунд\n"
                     f"Продолжу проверку после паузы..."
            )
            await asyncio.sleep(sleep + 2)
        except Exception as e:
            print(f"Ошибка при проверке пользователя {username}: {e}")
            continue

    await app.stop()

    # Удаляем сообщение о прогрессе и отправляем финальный отчет
    try:
        if user_id in progress_messages:
            await bot.delete_message(user_id, progress_messages[user_id])
            del progress_messages[user_id]
    except:
        pass

    # Финальное сообщение с результатами
    await bot.send_message(
        chat_id=user_id,
        text=f"🎉 **Проверка завершена!**\n\n"
             f"📊 **Итоги:**\n"
             f"• Всего проверено: {total_users}\n"
             f"• Найдено с блогами: {len(filtered_users)}\n"
             f"• Эффективность: {(len(filtered_users) / total_users * 100):.1f}%\n"
             f"⏰ Завершено: {datetime.now().strftime('%H:%M:%S')}"
    )

    return filtered_users


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
