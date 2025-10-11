from aiogram.fsm.state import State, StatesGroup

# Обычная группа состояний


class startSG(StatesGroup):
    start = State()

    choose_account = State()

    accounts = State()
    del_account = State()
    del_account_confirm =State()
    get_name = State()
    add_account = State()
    kod_send = State()
    get_password = State()

    collect_base = State()
    my_channels = State()
    choose_get_type = State()


class adminSG(StatesGroup):
    start = State()
    get_mail = State()
    get_time = State()
    get_keyboard = State()
    confirm_mail = State()
    deeplink_menu = State()
    deeplink_del = State()
    admin_menu = State()
    admin_del = State()
    admin_add = State()
