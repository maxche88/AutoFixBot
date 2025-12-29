# This Python file uses the following encoding: utf-8
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict
from datetime import date, datetime
from config import Config


# ==============================
# АВТОРИЗАЦИЯ РЕГИСТРАЦИЯ
# ==============================
def auth_menu():
    kb_list = [
        [InlineKeyboardButton(text='🔆 Регистрация 🔆', callback_data='registration')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def check_data():
    kb_list = [
        [InlineKeyboardButton(text="✅СОЗДАТЬ УЧЁТНУЮ ЗАПИСЬ", callback_data='correct')],
        [InlineKeyboardButton(text="🔺 ОТМЕНА 🔺", callback_data='incorrect')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# ==============================
# КЛИЕНТ
# ==============================


# КЛИЕНТ. ГЛАВНОЕ МЕНЮ
def user_main_menu():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ЛИЧНЫЙ КАБИНЕТ 🔹", callback_data='account')],
        [InlineKeyboardButton(text="🔹 ИНФОРМАЦИЯ 🔹", callback_data='o_nas')],
        [InlineKeyboardButton(text="🔹 ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ 🔹", callback_data='faq')],
        [InlineKeyboardButton(text="️🔹 ️КОНТАКТЫ. АДРЕС СТО 🔹", callback_data='get_person')]
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ЛИЧНЫЙ КАБИНЕТ
def user_personal_account():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ТЕКУЩИЙ РЕМОНТ 🔹", callback_data='info_rem')],
        [InlineKeyboardButton(text="🔹 ЗАПИСЬ НА РЕМОНТ 🔹", callback_data='appointment')],
        [InlineKeyboardButton(text="🔹 ЗАДАТЬ ВОПРОС 🔹", callback_data='send_message_all')],
        [InlineKeyboardButton(text="🔹 НАПИСАТЬ ОТЗЫВ 🔹", callback_data='create_comment')],
        [InlineKeyboardButton(text="🔹 МОИ ДАННЫЕ 🔹", callback_data='login')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_main_menu')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ВОЗВРАЩАЕТСЯ В ЛИЧНЫЙ КАБ ИЗ ТЕКУЩИХ ЗАКАЗОВ
def user_back_personal_account() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="back_to_account")]
    ])


# КЛИЕНТ. ВОЗВРАЩАЕТСЯ В ЛИЧНЫЙ КАБ ИЗ ЗАДАТЬ ВОПРОС
def user_return_to_profile():
    kb_list = [
        [InlineKeyboardButton(text="🔺 Отмена 🔺", callback_data='back_personal_account')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ЗАПИСАТЬСЯ НА ДИАГНОСТИКА/РЕМОНТ/ТО
def user_reg_repairs():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ДИАГНОСТИКА 🔹", callback_data='service:diagnostics')],
        [InlineKeyboardButton(text="🔹 РЕМОНТ 🔹", callback_data='service:repair')],
        [InlineKeyboardButton(text="🔹 ТЕХ. ОБСЛУЖИВАНИЕ 🔹", callback_data='service:maintenance')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_personal_account')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ИЗМЕНИТЬ ЛИЧНЫЕ ДАННЫЕ
def user_edit_profile():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ИЗМЕНИТЬ ДАННЫЕ 🔹", callback_data='edit_menu')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_personal_account')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ПРИНЯТЬ РАБОТУ
def get_accept_work_keyboard(index: list, order_id: int = None, master_tg_id: int = None) -> InlineKeyboardMarkup:
    """
    Передаёт и ID заказа, и tg_id мастера.
    """
    buttons_dict = {
        1: InlineKeyboardButton(text="✅ Принять работу", callback_data=f"accept_work:{order_id}:{master_tg_id}"),
        2: InlineKeyboardButton(text="🕦 Когда будет готово?", callback_data=f"quick_mess:question_time:{master_tg_id}"),
        3: InlineKeyboardButton(text="💰 Какая цена?", callback_data=f"quick_mess:question_price:{master_tg_id}"),
        4: InlineKeyboardButton(text="💬 Написать свой вопрос", callback_data=f"send_answer:{master_tg_id}"),
        5: InlineKeyboardButton(text="🔺 Cкрыть 🔺", callback_data="cancel"),
        6: InlineKeyboardButton(text="✅ ПРИЕДУ ВОВРЕМЯ", callback_data=f"quick_mess:app_ok:{master_tg_id}"),
        7: InlineKeyboardButton(text="❌ НЕ СМОГУ ПРИЕХАТЬ", callback_data=f"quick_mess:app_no:{master_tg_id}"),
        8: InlineKeyboardButton(text="🔄 ХОЧУ ПЕРЕНЕСТИ ЗАПИСЬ", callback_data=f"quick_mess:app_trans:{master_tg_id}"),
        9: InlineKeyboardButton(text="✏️ ВВЕСТИ ТЕКСТОМ", callback_data=f"answer_app:{master_tg_id}"),

    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


# КЛИЕНТ.
def common_menu(index: list):
    buttons_dict = {
        5: InlineKeyboardButton(text="🔹 ПРОДОЛЖИТЬ 🔹", callback_data='car_rep_next'),
        4: InlineKeyboardButton(text="🔺 Cкрыть 🔺", callback_data="cancel"),
        6: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='cancel'),
        7: InlineKeyboardButton(text="🔹 МОДЕЛЬ АВТО 🔹", callback_data='edit:model_auto'),
        13: InlineKeyboardButton(text="🔹 КОНТАКТНЫЙ НОМЕР 🔹", callback_data='edit:contact'),
        14: InlineKeyboardButton(text="🔹 МАРКА АВТО 🔹", callback_data='edit:brand_auto'),
        15: InlineKeyboardButton(text="🔹 ГОД ВЫПУСКА 🔹", callback_data='edit:year_auto'),
        16: InlineKeyboardButton(text="🔹 ВИН НОМЕР 🔹", callback_data='edit:vin_number'),
        17: InlineKeyboardButton(text="🔹 ИМЯ 🔹", callback_data='edit:user_name'),
        18: InlineKeyboardButton(text="🔹 ГОС. НОМЕР 🔹", callback_data='edit:gos_num'),
        19: InlineKeyboardButton(text="🔹 Записаться 🔹", callback_data="confirm_booking"),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]

    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


# КЛИЕНТ. КОНТАКТЫ И АДРЕСА
def location_menu():
    kb_list = [
        [InlineKeyboardButton(
            text='Показать на Яндекс Карте',
            url=Config.SERVICE_LOCATION_URL
        )],
        [InlineKeyboardButton(
            text='🔺 Скрыть 🔺',
            callback_data='cancel'
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ИНФОРМАЦИЯ
def user_info_menu():
    kb_list = [
        [InlineKeyboardButton(text='Показать отзывы наших клиентов', callback_data='comment')],
        [InlineKeyboardButton(text='Цены услуг ремонта', callback_data='price')],
        [InlineKeyboardButton(text='🔺 Скрыть 🔺', callback_data='cancel')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# КЛИЕНТ. ВЫБОР ОЦЕНКИ ДЛЯ МАСТЕРА
def rating_keyboard():
    """
    Возвращает inline-клавиатуру с кнопками оценки от 1 до 5.
    Каждая кнопка отправляет callback_data вида 'grade:N'.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1 ⭐", callback_data="grade:1"),
            InlineKeyboardButton(text="2 ⭐", callback_data="grade:2"),
            InlineKeyboardButton(text="3 ⭐", callback_data="grade:3"),
            InlineKeyboardButton(text="4 ⭐", callback_data="grade:4"),
            InlineKeyboardButton(text="5 ⭐", callback_data="grade:5"),
        ]
    ])


# ==============================
# АДМИН
# ==============================


# АДМИН. ГЛАВНОЕ МЕНЮ
def admin_menu():
    kb_list_1 = [
        [InlineKeyboardButton(text="🔹 АДМИН-ПАНЕЛЬ 🔹", callback_data='admin_panel')],
        [InlineKeyboardButton(text="🔹 СТАТИСТИКА 🔹", callback_data='admin_stats')],
        [InlineKeyboardButton(text="🔹 РАССЫЛКА 🔹", callback_data='broadcast')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_1)


def admin_user_manage(uid: int) -> InlineKeyboardMarkup:
    kb_list_1 = [
        [InlineKeyboardButton(text="🔹 НАЗНАЧИТЬ МАСТЕРОМ", callback_data=f"admin_user_action:promote:{uid}")],
        [InlineKeyboardButton(text="🔹 ЗАБЛОКИРОВАТЬ", callback_data=f"admin_user_action:block:{uid}")],
        [InlineKeyboardButton(text="🔺 Назад", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_1)


def admin_action_menu(index: list, order_id: int = None, tg_id: int = None) -> InlineKeyboardMarkup:
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ 🔹", callback_data="manage_users"),
        2: InlineKeyboardButton(text="🔹 УПРАВЛЕНИЕ МАСТЕРАМИ 🔹", callback_data='manage_masters'),
        3: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='admin_back_main_menu'),
        4: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='cancel'),
        5: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='admin_panel'),
        # УПРАВЛЕНИЕ МАСТЕРАМИ
        6: InlineKeyboardButton(text="✏️ Изменить должность", callback_data=f"master_action:edit_status:{tg_id}"),
        7: InlineKeyboardButton(text="⭐️ Изменить рейтинг", callback_data=f"master_action:edit_rating:{tg_id}"),
        8: InlineKeyboardButton(text="🗑️ Удалить мастера", callback_data=f"master_action:delete:{tg_id}"),
        9: InlineKeyboardButton(text="📅 Посмотреть записи", callback_data=f"master_app:{tg_id}"),
        10: InlineKeyboardButton(text="✅ Активные заказы", callback_data=f"master_order_active:{tg_id}"),
        13: InlineKeyboardButton(text="🚫 Закрытые заказы", callback_data=f"master_order_close:{tg_id}"),
        11: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="manage_masters"),
        # ПОДТВЕРЖДЕНИЕ УДАЛЕНИЯ МАСТЕРА
        12: InlineKeyboardButton(text="❌ Да, удалить", callback_data=f"confirm_delete_master:{tg_id}"),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


def create_masters_management_keyboard(masters: List[Dict[str, str | int]]) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для управления мастерами.
    Каждая кнопка: "Имя (Должность)", callback_data = manage_master:<tg_id>
    В конце — кнопка "Назад" в админ-панель.

    :param masters: Список словарей с ключами 'user_name', 'status', 'tg_id'
    :return: InlineKeyboardMarkup
    """
    buttons = []
    for master in masters:
        status = master.get("status")
        display_name = f"{master['user_name']} ({status})"
        buttons.append([
            InlineKeyboardButton(
                text=display_name,
                callback_data=f"manage_master:{master['tg_id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="admin_panel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==============================
# МАСТЕР
# ==============================


# МАСТЕР. ГЛАВНОЕ МЕНЮ
def master_menu():
    kb_list_2 = [
        [InlineKeyboardButton(text="🔹 ЛИЧНЫЙ КАБИНЕТ МАСТЕРА 🔹", callback_data='master_account')],
        [InlineKeyboardButton(text="🔹 ЗАПИСИ / ОЧЕРЕДЬ 🔹", callback_data='rec_queue')],
        [InlineKeyboardButton(text="🔹 ТЕКУЩИЕ ЗАКАЗЫ 🔹", callback_data='my_actions_orders')],
        [InlineKeyboardButton(text="🔹 ЗАКРЫТЫЕ ЗАКАЗЫ 🔹", callback_data='work_history')],
        [InlineKeyboardButton(text="🔹 ДИАГНОСТИКА DTC 🔹", callback_data='diagnostic')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_2)


# МАСТЕР. ЛИЧНЫЙ КАБИНЕТ МАСТЕРА
def master_personal_account():
    kb_list_7 = [
        [InlineKeyboardButton(text="🔹 МОИ ДАННЫЕ 🔹", callback_data='master_login')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='master_back_main_menu')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_7)


# МАСТЕР. МОИ ДАННЫЕ
def master_edit_profile():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ИЗМЕНИТЬ ДАННЫЕ 🔹", callback_data='master_edit_menu')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='master_back_personal_account')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# МАСТЕР. ФИЛЬТР ОТОБРАЖЕНИЯ ТЕКУЩИХ ЗАПИСИЕЙ
def appointment_period_menu() -> InlineKeyboardMarkup:
    kb_list_5 = [
        [InlineKeyboardButton(text="📅 На сегодня", callback_data="appt_period:today")],
        [InlineKeyboardButton(text="📆 На месяц", callback_data="appt_period:month")],
        [InlineKeyboardButton(text="📁 Все записи", callback_data="appt_period:all")],
        [InlineKeyboardButton(text="🔺 Назад", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_5)


# МАСТЕР. ФОРМА ТЕКУЩАЯ ЗАПИСЬ
def appointment_action_menu(appointment_id: int, user_tg_id: int) -> InlineKeyboardMarkup:
    kb_list_4 = [
        [InlineKeyboardButton(text="✉️ НАПИСАТЬ КЛИЕНТУ", callback_data=f"send_mess:{user_tg_id}")],
        [InlineKeyboardButton(text="🔔 НАПОМНИТЬ О ВСТРЕЧЕ", callback_data=f"remind_mess:{appointment_id}:{user_tg_id}")],
        [InlineKeyboardButton(text="♻️ ПЕРЕНЕСТИ ВСТРЕЧУ", callback_data=f"transfer__app:{user_tg_id}")],
        [InlineKeyboardButton(text="🗑 УДАЛИТЬ ЗАПИСЬ", callback_data=f"del_app:{appointment_id}")],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data=f"cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_4)


# МАСТЕР. КЛАВИАТУРА ПОД ТЕКУЩИМИ ЗАКАЗОМИ
def master_order_action_menu(index: list, order_id: int = None, tg_id: int = None) -> InlineKeyboardMarkup:
    """
    Клавиатура для действий с конкретным заказом.

    :param index: Список ключей кнопок для отображения (например, [1, 2, 4]).
    :param order_id: ID заказа в базе данных.
    :param tg_id: (опционально) Telegram ID пользователя — используется в кнопках 1 и 5.
    :return: InlineKeyboardMarkupg
    """
    buttons_dict = {
        1: InlineKeyboardButton(text="🏁 ВЫПОЛНЕНО", callback_data=f"comp_odr:{order_id}:{tg_id}"),
        2: InlineKeyboardButton(text="🕑 СТАТУС WAIT", callback_data=f"ed_st:{order_id}"),
        9: InlineKeyboardButton(text="⚙️ УКАЗАТЬ ПРОБЕГ", callback_data=f"up_km:{order_id}"),
        3: InlineKeyboardButton(text="✏️ ИЗМЕНИТЬ ОПИСАНИЕ", callback_data=f"ed_des:{order_id}"),
        4: InlineKeyboardButton(text="🚫 ЗАКРЫТЬ ЗАКАЗ", callback_data=f"cl_odr:{order_id}"),
        5: InlineKeyboardButton(text="🤝 ПЕРЕДАТЬ ЗАКАЗ", callback_data=f"tr_odr:{order_id}"),
        6: InlineKeyboardButton(text="🗑 УДАЛИТЬ ЗАКАЗ", callback_data=f"del_odr:{order_id}"),
        7: InlineKeyboardButton(text="♻️ ВОЗВРАТ В ТЕКУЩИЙ", callback_data=f"res_odr:{order_id}"),
        8: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel"),
        10: InlineKeyboardButton(text="💬 Отправить сообщение", callback_data=f"send_mess:{tg_id}")
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


# МАСТЕР. ПЕРЕДАТЬ ЗАКАЗ ДРУГОМУ МАСТЕРУ
def transfer_master_keyboard(masters: List[Dict[str, str | int]]) -> InlineKeyboardMarkup:
    """
    Генерирует клавиатуру для выбора мастера при передаче заказа.

    :param masters: Список мастеров в формате:
        [{"tg_id": 123, "user_name": "Иван", "contact": "+7..."}, ...]
    :return: InlineKeyboardMarkup с кнопками выбора и отмены
    """
    buttons = []
    for master in masters:
        btn = InlineKeyboardButton(
            text=str(master["user_name"]),
            callback_data=f"select_master:{master['tg_id']}"
        )
        buttons.append([btn])

    # Кнопка отмены
    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# МАСТЕР. ВЫПОЛНЕНО
def quick_action_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ МОЖЕТЕ ЗАБИРАТЬ", callback_data="quick:answer")],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel")]
    ])


# МАСТЕР (ГЕНЕРАТОР КНОПОК)
def staff_menu(index: list):
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 ИМЯ 🔹", callback_data='master_edit:user_name'),
        2: InlineKeyboardButton(text="🔹 КОНТАКТНЫЙ НОМЕР 🔹", callback_data='master_edit:contact'),
        3: InlineKeyboardButton(text="🔹 ВКЛЮЧИТЬ СООБЩЕНИЯ 🔹", callback_data='master_edit:can_mess_on'),
        10: InlineKeyboardButton(text="🔹 ОТКЛЮЧИТЬ СООБЩЕНИЯ 🔹", callback_data='master_edit:can_mess_off'),
        4: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='cancel'),
        5: InlineKeyboardButton(text="🔹 РАСШИФРОВКА DTC КОДОВ API 🔹", callback_data='dtc_decoding'),
        11: InlineKeyboardButton(text="🔹 ВВЕСТИ ВРУЧНУЮ 🔹", callback_data="manual_dtc_input"),
        6: InlineKeyboardButton(text="🔹 HIGH/LOW ФИЛЬТР 🔹", callback_data='view_hl:st'),
        7: InlineKeyboardButton(text="🔹 ИСТОРИЯ API 🔹", callback_data='history_api'),
        8: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='master_back_main_menu'),
        9: InlineKeyboardButton(text="🔹 ПРОДОЛЖИТЬ 🔹", callback_data='car_rep_next'),
        12: InlineKeyboardButton(text="🔹 HIGH 🔹", callback_data='hl:high'),
        13: InlineKeyboardButton(text="🔹 LOW 🔹", callback_data='hl:low'),
        14: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='view_hl:bk'),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]

    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


# МАСТЕР (ГЕНЕРАТОР КНОПОК)
def master_menu_app(index: list, user_id: int):
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 ОЖИДАНИЕ 🔹", callback_data=f'await:{user_id}'),
        2: InlineKeyboardButton(text="🔹 ОТКАЗ 🔹", callback_data=f'refuse:{user_id}'),
        3: InlineKeyboardButton(text="🔹 ЗВОНИТЕ 🔹", callback_data=f'call:{user_id}'),
        4: InlineKeyboardButton(text="💬 ОТВЕТИТЬ ТЕКСТОМ", callback_data=f'send_mess:{user_id}'),  # staff
        5: InlineKeyboardButton(text="📆 НАЗНАЧИТЬ ВРЕМЯ", callback_data=f'set_time:{user_id}'),
        6: InlineKeyboardButton(text="🔹 НА СЕГОДНЯ 🔹", callback_data=f'today:{user_id}'),
        7: InlineKeyboardButton(text="🔹 ВЫБРАТЬ ДЕНЬ 🔹", callback_data=f'next_days:{user_id}'),
        8: InlineKeyboardButton(text="🔺 Cкрыть 🔺", callback_data="cancel"),
        9: InlineKeyboardButton(text="🔹 УДОБНОЕ ВРЕМЯ? 🔹", callback_data=f'check_time:{user_id}'),
        10: InlineKeyboardButton(text="🔹 ДИАГНОСТИКА 🔹", callback_data=f"repair_type:diagnostic:{user_id}"),
        11: InlineKeyboardButton(text="🔹 РЕМОНТ 🔹", callback_data=f"repair_type:repair:{user_id}"),
        12: InlineKeyboardButton(text="🔹 ДИАГНОСТИКА И РЕМОНТ 🔹", callback_data=f"repair_type:diag_repair:{user_id}"),
        13: InlineKeyboardButton(text="🔹 ТЕХ. ОБСЛУЖИВАНИЕ 🔹", callback_data=f"repair_type:to:{user_id}"),
        14: InlineKeyboardButton(text="🔹 ВВЕСТИ ТЕКСТОМ 🔹", callback_data=f"repair_type:custom:{user_id}"),
        15: InlineKeyboardButton(text="✅ Создать заявку на ремонт", callback_data=f"create_order:{user_id}"),
        16: InlineKeyboardButton(text="🔸 ЗАЯВКА НА РЕМОНТ 🔸", callback_data=f"send_repair_req:{user_id}"),
        17: InlineKeyboardButton(text="🔹 Ответить 🔹", callback_data=f"send_answer:{user_id}"),
        18: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="back_personal_account"),
        19: InlineKeyboardButton(text="🔺 Закрыть 🔺", callback_data="cancel"),
        21: InlineKeyboardButton(text="♻️ ПЕРЕНЕСТИ ЗАПИСЬ", callback_data=f"quick_mess:app_trans:{user_id}"),
        22: InlineKeyboardButton(text="💬 НАПИСАТЬ МАСТЕРУ", callback_data=f"send_answer:{user_id}"),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


# МАСТЕР. КЛАВИАТУРЫ ДАТЫ И ВРЕМЕНИ
def generate_calendar_buttons(user_id: int, year: int, month: int, busy_days: set = None):
    """
    Генерирует календарь для указанного года и месяца.

    :param user_id: ID пользователя
    :param year: год (например, 2025)
    :param month: месяц (1–12)
    :param busy_days: множество дней без свободного времени
    """
    if busy_days is None:
        busy_days = set()

    today = date.today()

    # Определяем следующий и предыдущий месяц
    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    # Заголовок: "Июнь 2025"
    month_names = [
        "", "Янв", "Фев", "Мар", "Апр", "Май", "Июн",
        "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"
    ]
    header_text = f"{month_names[month]} {year}"

    # Кнопки навигации
    prev_button = InlineKeyboardButton(
        text="◄",
        callback_data=f"calendar_nav:{prev_year}:{prev_month}:{user_id}"
    )
    header_button = InlineKeyboardButton(
        text=header_text,
        callback_data="ignore"
    )
    next_button = InlineKeyboardButton(
        text="►",
        callback_data=f"calendar_nav:{next_year}:{next_month}:{user_id}"
    )

    rows = [[prev_button, header_button, next_button]]

    # Дни недели
    weekday_headers = [
        InlineKeyboardButton(text=day, callback_data="ignore")
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]
    rows.append(weekday_headers)

    # Генерация дней
    first_day_of_month = datetime(year, month, 1)
    first_day_next_month = datetime(next_year, next_month, 1)
    days_in_month = (first_day_next_month - first_day_of_month).days

    first_weekday = first_day_of_month.weekday()  # 0 = понедельник
    current_row = []

    # Пустые ячейки в начале
    for _ in range(first_weekday):
        current_row.append(InlineKeyboardButton(text="✖️", callback_data="ignore"))

    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)

        if current_date < today:
            btn = InlineKeyboardButton(text="✖️", callback_data="ignore")
        elif day in busy_days:
            btn = InlineKeyboardButton(text="🔴", callback_data="ignore")
        else:
            btn = InlineKeyboardButton(
                text=str(day),
                callback_data=f"calendar_day:{year}:{month}:{day}:{user_id}"
            )

        current_row.append(btn)

        if (first_weekday + day) % 7 == 0 or day == days_in_month:
            while len(current_row) < 7:
                current_row.append(InlineKeyboardButton(text="✖️", callback_data="ignore"))
            rows.append(current_row)
            current_row = []

    # Кнопка "Назад"
    rows.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def generate_time_buttons(hours_set: set, user_id: int):
    """
    Функция генерирует клавиатуру с кнопками, свободное время для записи.

    param: hours_set: set, user_id: int
    return: InlineKeyboardMarkup
    """
    sorted_hours = sorted(hours_set)
    rows = []
    current_row = []

    for hour in sorted_hours:
        label = f"{hour}:00"
        # В callback_data добавляем час и user_id
        button = InlineKeyboardButton(
            text=label,
            callback_data=f"appoint:{hour}:{user_id}"
        )
        current_row.append(button)

        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    rows.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def generate_duration_buttons(user_id: int):
    """
    Клавиатура выбора длительности приёма.
    В callback_data: duration_in_hours (дробное число)
    """
    durations = [
        ("30 мин", "0.5"),
        ("1 час", "1.0"),
        ("1.5 часа", "1.5"),
        ("2 часа", "2.0"),
        ("2.5 часа", "2.5"),
        ("3 часа", "3.0")
    ]

    rows = []
    for label, value in durations:
        button = InlineKeyboardButton(
            text=label,
            callback_data=f"duration:{value}:{user_id}"
        )
        rows.append([button])

    rows.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def generate_order_select_buttons(orders: list[dict]) -> InlineKeyboardMarkup:
    """
    Генерирует кнопки выбора активного заказа.
    Каждая кнопка: "Марка Модель Год"
    Callback: select_order:<order_id>:<brand>:<model>:<year>
    """
    buttons = []
    for order in orders:
        brand = order.get("brand_auto", "-") or "-"
        model = order.get("model_auto", "-") or "-"
        year = order.get("year_auto", "-") or "-"
        text = f"{brand} {model} ({year})"
        callback = f"select_order:{order['id']}:{brand}:{model}:{year}"
        buttons.append([InlineKeyboardButton(text=text, callback_data=callback)])
    buttons.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

