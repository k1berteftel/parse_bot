import os

from aiogram import Bot
from aiogram.types import CallbackQuery, User, Message, FSInputFile, InputMediaDocument
from aiogram.utils.media_group import MediaGroupBuilder
from aiogram_dialog import DialogManager, ShowMode
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.kbd import Button, Select
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput
from pyrogram import Client
from pyrogram.types import SentCode
from pyrogram.errors import PasswordHashInvalid

from utils.tables import get_xlsx_table, get_csv_table
from utils.collect_funcs import filter_user_base, get_channels
from database.action_data_class import DataInteraction
from config_data.config import load_config, Config
from states.state_groups import startSG


config: Config = load_config()


async def collect_base_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    base = dialog_manager.dialog_data.get('users')
    if not base:
        base = []
        dialog_manager.dialog_data['users'] = base
    return {'users': len(base)}


async def clean_base(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    dialog_manager.dialog_data['users'] = None
    await clb.answer('База пользователей была успешно почищена')
    await dialog_manager.switch_to(startSG.collect_base)


async def get_channel(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    try:
        text = int(text)
    except Exception as err:
        print(err)
        if 't.me' not in text:
            await msg.answer('❗️Вы ввели ссылку не в том формате, пожалуйста попробуйте снова')
            return
        try:
            text = text.split('/')[-1]
        except Exception:
            await msg.answer('❗️Вы ввели ссылку не в том формате, пожалуйста попробуйте снова')
            return
    account_id = dialog_manager.dialog_data.get('account_id')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account = await session.get_account(account_id)
    message = await msg.answer('Начался процесс сбора базы')
    users = dialog_manager.dialog_data.get('users')
    new_users = await filter_user_base(
        f'accounts/{msg.from_user.id}_{account.account_name.replace(" ", "_")}',
        text,
        msg.from_user.id,
        msg.bot
    )
    if not new_users:
        await msg.answer('❗️При сборе базы произошла какая-то ошибка пожалуйста попробуйте снова')
        await dialog_manager.switch_to(startSG.collect_base)
        return
    users.extend(new_users)
    dialog_manager.dialog_data['users'] = users
    await message.delete()
    await dialog_manager.switch_to(startSG.collect_base)


async def get_forward_message(msg: Message, widget: MessageInput, dialog_manager: DialogManager):
    if msg.forward_from_chat is None:
        await msg.answer('❗️К сожалению невозможно получить данные о канале из-за правил конфиденциальности канала')
        return
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    account = await session.get_account(account_id)
    users = dialog_manager.dialog_data.get('users')
    new_users = await filter_user_base(
        f'accounts/{msg.from_user.id}_{account.account_name.replace(" ", "_")}',
        msg.forward_from_chat.id,
        msg.from_user.id,
        msg.bot
    )
    if not new_users:
        await msg.answer('❗️При сборе базы произошла какая-то ошибка пожалуйста попробуйте снова')
        await dialog_manager.switch_to(startSG.collect_base)
        return
    users.extend(new_users)
    dialog_manager.dialog_data['users'] = users
    await dialog_manager.switch_to(startSG.collect_base)


async def my_channels_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    page = dialog_manager.dialog_data.get('chat_page')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    account = await session.get_account(account_id)
    bot: Bot = dialog_manager.middleware_data.get('bot')
    if not page:
        page = 0
        dialog_manager.dialog_data['chat_page'] = page
    dialogs = dialog_manager.dialog_data.get('chats')
    if not dialogs:
        dialogs = await get_channels(f'accounts/{event_from_user.id}_{account.account_name.replace(" ", "_")}', bot, event_from_user.id)
        dialogs = [dialogs[i:i + 20] for i in range(0, len(dialogs), 20)]
        dialog_manager.dialog_data['chats'] = dialogs
    not_first = True
    not_last = True
    if page == 0:
        not_first = False
    if page == len(dialogs) - 1:
        not_last = False
    return {
        'items': dialogs[page],
        'not_first': not_first,
        'not_last': not_last,
        'open_page': str(page + 1),
        'last_page': str(len(dialogs))
    }


async def my_channels_pager(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    page = dialog_manager.dialog_data.get('chat_page')
    if clb.data.startswith('back'):
        dialog_manager.dialog_data['chat_page'] = page - 1
    else:
        dialog_manager.dialog_data['chat_page'] = page + 1
    await dialog_manager.switch_to(startSG.my_channels)


async def my_chat_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    await clb.message.answer('Начался процесс считывания базы пользователей, пожалуйста ожидайте')
    users = dialog_manager.dialog_data.get('users')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    account = await session.get_account(account_id)
    new_users = await filter_user_base(
        f'accounts/{clb.from_user.id}_{account.account_name.replace(" ", "_")}',
        int(item_id),
        clb.from_user.id,
        clb.bot
    )
    if not new_users:
        await clb.message.answer('❗️При сборе базы произошла какая-то ошибка пожалуйста попробуйте снова')
        await dialog_manager.switch_to(startSG.collect_base)
        return
    users.extend(new_users)
    dialog_manager.dialog_data['users'] = users
    await dialog_manager.switch_to(startSG.collect_base)


async def get_type_switcher(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    users = dialog_manager.dialog_data.get('users')
    if not users:
        await clb.answer('❗️Перед тем как перейти в выгрузке соберите хотя бы минимальную базу')
        return
    await dialog_manager.switch_to(startSG.choose_get_type)


async def type_choose(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    discharge = clb.data.split('_')[0]
    users = dialog_manager.dialog_data.get('users')
    if discharge == 'text':
        text = ''
        for user in users:
            if len(text) >= 3850:
                await clb.message.answer(text)
                text = ''
            text += f'{user.get("username")} - {user.get("channel")} - \n<blockquote expandable>{user.get("bio")}</blockquote>'
        await clb.message.answer(text)
    else:
        columns = []
        for user in users:
            columns.append(
                [
                    user.get('username'),
                    user.get('channel'),
                    user.get('bio')
                ]
            )
        columns.insert(0, ['Юзернейм', 'Канал', 'Био'])
        excel_table = get_xlsx_table(columns, f'База_xlx_{clb.from_user.id}')
        csv_table = get_csv_table(columns, f'База_csv_{clb.from_user.id}')
        media_group = MediaGroupBuilder(
            media=[
                InputMediaDocument(media=FSInputFile(path=excel_table)),
                InputMediaDocument(media=FSInputFile(path=csv_table))
            ]
        )
        await clb.message.answer_media_group(media_group.build())
        try:
            os.remove(excel_table)
            os.remove(csv_table)
        except Exception:
            ...
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.start, show_mode=ShowMode.DELETE_AND_SEND)


async def choose_account_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(event_from_user.id)
    buttons = []
    for account in accounts:
        buttons.append(
            (account.account_name, account.id)
        )
    return {'items': buttons}


async def choose_account_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    dialog_manager.dialog_data.clear()
    dialog_manager.dialog_data['account_id'] = int(item_id)
    await dialog_manager.switch_to(startSG.collect_base)



async def choose_account_switcher(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(clb.from_user.id)
    if not accounts:
        await clb.answer('Перед началом сбора базы, пожалуйста добавьте аккаунт')
        return
    await dialog_manager.switch_to(startSG.choose_account)


async def accounts_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(event_from_user.id)
    text = ''
    if accounts:
        text = 'Добавленные аккаунты:\n'
        count = 1
        for account in accounts:
            text += f'\t{count} - {account.account_name}'
            count += 1
    return {'text': text}


async def del_account_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    accounts = await session.get_user_accounts(event_from_user.id)
    buttons = []
    for account in accounts:
        buttons.append(
            (account.account_name, account.id)
        )
    return {'items': buttons}


async def del_account_selector(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str):
    dialog_manager.dialog_data['account_id'] = int(item_id)
    await dialog_manager.switch_to(startSG.del_account_confirm)


async def del_account_confirm_getter(event_from_user: User, dialog_manager: DialogManager, **kwargs):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    account = await session.get_account(account_id)
    return {'name': account.account_name}


async def del_account(clb: CallbackQuery, button: Button, dialog_manager: DialogManager):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    account_id = dialog_manager.dialog_data.get('account_id')
    account = await session.get_account(account_id)
    await session.del_account(account_id)
    try:
        os.remove(f'accounts/{clb.from_user.id}_{account.account_name.replace(" ", "_")}.session')
        os.remove(f'accounts/{clb.from_user.id}_{account.account_name.replace(" ", "_")}.session-journal')
    except Exception:
        ...
    await clb.answer('Аккаунт был успешно удален')
    dialog_manager.dialog_data.clear()
    await dialog_manager.switch_to(startSG.accounts)


async def get_name(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    if text in [account.account_name for account in await session.get_user_accounts(msg.from_user.id)]:
        await msg.answer('❗️У вас уже есть аккаунт с таким названием, пожалуйста придумайте другое название')
        return
    dialog_manager.dialog_data['name'] = text
    await dialog_manager.switch_to(startSG.add_account)


async def phone_get(msg: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    print('Начало соединения')
    name = dialog_manager.dialog_data.get('name')
    client = Client(f'accounts/{msg.from_user.id}_{name.replace(" ", "_")}', config.user_bot.api_id, config.user_bot.api_hash)
    await client.connect()
    print(text, type(text))
    try:
        print('Отправка кода')
        sent_code_info: SentCode = await client.send_code(text.strip())
    except Exception as err:
        print(err)
        await msg.answer('❗️Веденный номер телефона неверен, попробуйте снова')
        return
    dialog_manager.dialog_data['client'] = client
    dialog_manager.dialog_data['phone_info'] = sent_code_info
    dialog_manager.dialog_data['phone_number'] = text
    await dialog_manager.switch_to(state=startSG.kod_send)


async def get_kod(message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    name = dialog_manager.dialog_data.get('name')
    client: Client = dialog_manager.dialog_data.get('client')
    phone_info: SentCode = dialog_manager.dialog_data.get('phone_info')
    phone = dialog_manager.dialog_data.get('phone_number')
    code = ''
    if len(text.split('-')) != 5:
        await message.answer(text='❗️Вы отправили код в неправильном формате, попробуйте вести код снова')
        return
    for number in text.split('-'):
        code += number
    print(code)
    try:
        await client.sign_in(phone, phone_info.phone_code_hash, code)
        await client.disconnect()
        await session.add_user_account(message.from_user.id, name)
        dialog_manager.dialog_data.clear()
        await dialog_manager.switch_to(state=startSG.accounts)
    except Exception as err:
        print(err)
        await dialog_manager.switch_to(state=startSG.get_password)


async def get_password(message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, text: str):
    client: Client = dialog_manager.dialog_data.get('client')
    name = dialog_manager.dialog_data.get('name')
    session: DataInteraction = dialog_manager.middleware_data.get('session')
    dialog_manager.dialog_data.clear()
    try:
        await client.check_password(text)
        await client.disconnect()
        await session.add_user_account(message.from_user.id, name)
        await message.answer(text='✅Ваш аккаунт был успешно добавлен')
        await dialog_manager.switch_to(state=startSG.accounts)
    except PasswordHashInvalid as err:
        print(err)
        await message.answer(text='❗️Введенные данные были неверны, пожалуйста попробуйте авторизоваться снова')
        await dialog_manager.switch_to(state=startSG.get_name)

