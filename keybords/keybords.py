# This Python file uses the following encoding: utf-8
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import List, Dict
from datetime import date, datetime
from config import config


def auth_menu():
    kb_list = [
        [InlineKeyboardButton(text='🔆 АВТОРИЗАЦИЯ 🔆', callback_data='authorization')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def location_menu():
    kb_list = [
        [InlineKeyboardButton(
            text='Показать на Яндекс Карте',
            url=config.SERVICE_LOCATION_URL
        )],
        [InlineKeyboardButton(
            text='🔺 Скрыть 🔺',
            callback_data='cancel'
        )]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def comment_menu():
    kb_list = [
        [InlineKeyboardButton(text='Показать отзывы наших клиентов', callback_data='comment')],
        [InlineKeyboardButton(text='Цены услуг ремонта', callback_data='price')],
        [InlineKeyboardButton(text='🔺 Скрыть 🔺', callback_data='cancel')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


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
    rows.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="delete_msg")])

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

    rows.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="delete_msg")])

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

    rows.append([InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="delete_msg")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def admin_menu():
    kb_list_1 = [
        [InlineKeyboardButton(text="🔹 АДМИН-ПАНЕЛЬ 🔹", callback_data='admin_panel')],
        [InlineKeyboardButton(text="🔹 УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ 🔹", callback_data='manage_users')],
        [InlineKeyboardButton(text="🔹 УПРАВЛЕНИЕ МАСТЕРАМИ 🔹", callback_data='manage_users')],
        [InlineKeyboardButton(text="🔹 СТАТИСТИКА 🔹", callback_data='admin_stats')],
        [InlineKeyboardButton(text="🔹 РАССЫЛКА 🔹", callback_data='broadcast')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_1)


def master_menu():
    kb_list_2 = [
        [InlineKeyboardButton(text="🔹 ЛИЧНЫЙ КАБИНЕТ МАСТЕРА 🔹", callback_data='master_cabinet')],
        [InlineKeyboardButton(text="🔹 ЗАПИСИ / ОЧЕРЕДЬ 🔹", callback_data='rec_queue')],
        [InlineKeyboardButton(text="🔹 ТЕКУЩИЕ ЗАКАЗЫ 🔹", callback_data='my_actions_orders')],
        [InlineKeyboardButton(text="🔹 ЗАКРЫТЫЕ ЗАКАЗЫ 🔹", callback_data='work_history')],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_2)


def appointment_period_menu() -> InlineKeyboardMarkup:
    kb_list_5 = [
        [InlineKeyboardButton(text="📅 На сегодня", callback_data="appt_period:today")],
        [InlineKeyboardButton(text="📆 На месяц", callback_data="appt_period:month")],
        [InlineKeyboardButton(text="📁 Все записи", callback_data="appt_period:all")],
        [InlineKeyboardButton(text="🔺 Назад", callback_data="cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_5)


def appointment_action_menu(appointment_id: int, user_tg_id: int) -> InlineKeyboardMarkup:
    kb_list_4 = [
        [InlineKeyboardButton(text="✉️ Написать клиенту", callback_data=f"replay_mess:{user_tg_id}")],
        [InlineKeyboardButton(text="🗑 Удалить запись", callback_data=f"del_app:{appointment_id}")],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data=f"cancel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_4)


def master_order_action_menu(index: list, order_id: int = None, tg_id: int = None) -> InlineKeyboardMarkup:
    """
    Клавиатура для действий с конкретным заказом.

    :param index: Список ключей кнопок для отображения (например, [1, 2, 4]).
    :param order_id: ID заказа в базе данных.
    :param tg_id: (опционально) Telegram ID пользователя — используется в кнопках 1 и 5.
    :return: InlineKeyboardMarkup
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
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


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


def quick_action_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ МОЖЕТЕ ЗАБИРАТЬ", callback_data="quick:answer")],
        [InlineKeyboardButton(text="✏️ Отправить сообщение", callback_data="quick:text")],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="cancel")]
    ])


def user_main_menu():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ЛИЧНЫЙ КАБИНЕТ 🔹", callback_data='account')],
        [InlineKeyboardButton(text="🔹 ИНФОРМАЦИЯ 🔹", callback_data='o_nas')],
        [InlineKeyboardButton(text="🔹 ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ 🔹", callback_data='faq')],
        [InlineKeyboardButton(text="️🔹 ️КОНТАКТЫ. АДРЕС СТО 🔹", callback_data='get_person')]
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# ПОДМЕНЮ ЛИЧНЫЙ КАБИНЕТ
def user_personal_account():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ТЕКУЩИЙ РЕМОНТ 🔹", callback_data='info_rem')],
        [InlineKeyboardButton(text="🔹 ЗАПИСАТЬСЯ 🔹", callback_data='appointment')],
        [InlineKeyboardButton(text="🔹 ЗАДАТЬ ВОПРОС 🔹", callback_data='send_message')],
        [InlineKeyboardButton(text="🔹 НАПИСАТЬ ОТЗЫВ 🔹", callback_data='create_comment')],
        [InlineKeyboardButton(text="🔹 МОИ ДАННЫЕ 🔹", callback_data='login')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_main_menu')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# ВОЗВРАЩАЕТ В ЛИЧНЫЙ КАБ., УДАЛЯЕТ ТЕКУЩИЕ ЗАКАЗЫ
def user_back_personal_account() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="back_to_account")]
    ])


def user_return_to_profile():
    kb_list = [
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_personal_account')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# ЗАПИСАТЬСЯ НА ДИАГНОСТИКА/РЕМОНТ/ТО
def user_reg_repairs():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ДИАГНОСТИКА 🔹", callback_data='service:diagnostics')],
        [InlineKeyboardButton(text="🔹 РЕМОНТ 🔹", callback_data='service:repair')],
        [InlineKeyboardButton(text="🔹 ТЕХ. ОБСЛУЖИВАНИЕ 🔹", callback_data='service:maintenance')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_personal_account')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


# ПОДТВЕРЖДЕНИЕ ОТПРАВКИ СООБЩЕНИЯ ВСЕМ МАСТЕРАМ
def user_confirm_send_mess():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_support_msg")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_support_msg")]
    ])


# ПОДТВЕРЖДЕНИЕ ОТПРАВКИ ОТЗЫВА
def user_confirm_send_comment():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data="confirm_comment")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_comment")]
    ])


# ИЗМЕНИТЬ ЛИЧНЫЕ ДАННЫЕ
def user_edit_profile():
    kb_list = [
        [InlineKeyboardButton(text="🔹 ИЗМЕНИТЬ ДАННЫЕ 🔹", callback_data='edit_menu')],
        [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='back_personal_account')],
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list)


def login_menu(index: list):
    buttons_dict = {
        5: InlineKeyboardButton(text="🔹 ПРОДОЛЖИТЬ 🔹", callback_data='car_rep_next'),
        6: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data='cancel'),
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


def get_accept_work_keyboard(order_id: int, master_tg_id: int) -> InlineKeyboardMarkup:
    """
    Передаёт и ID заказа, и tg_id мастера.
    """
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Принять работу",
            callback_data=f"accept_work:{order_id}:{master_tg_id}"
        )]
    ])


def staff_menu(index: list, user_id: int):
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 ОЖИДАНИЕ 🔹", callback_data=f'await:{user_id}'),
        2: InlineKeyboardButton(text="🔹 ОТКАЗ 🔹", callback_data=f'refuse:{user_id}'),
        3: InlineKeyboardButton(text="🔹 ЗВОНИТЕ 🔹", callback_data=f'call:{user_id}'),
        4: InlineKeyboardButton(text="📤 ОТВЕТИТЬ ТЕКСТОМ", callback_data=f'replay_mess:{user_id}'),
        5: InlineKeyboardButton(text="📆 НАЗНАЧИТЬ ВРЕМЯ", callback_data=f'set_time:{user_id}'),
        6: InlineKeyboardButton(text="🔹 НА СЕГОДНЯ 🔹", callback_data=f'today:{user_id}'),
        7: InlineKeyboardButton(text="🔹 ВЫБРАТЬ ДЕНЬ 🔹", callback_data=f'next_days:{user_id}'),
        8: InlineKeyboardButton(text="🔺 Назад 🔺", callback_data="delete_msg"),
        9: InlineKeyboardButton(text="🔹 УДОБНОЕ ВРЕМЯ? 🔹", callback_data=f'check_time:{user_id}'),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


def action_buttons_orders_menu(index: list, client_tg_id: int, master_tg_id: int) -> InlineKeyboardMarkup:
    """
    Универсальная клавиатура для действий мастера/админа и клиента.
    Все кнопки используют client_tg_id и master_tg_id.

    :param index: Список ключей кнопок для отображения (например, [1, 2, 5]).
    :param client_tg_id: Telegram ID клиента.
    :param master_tg_id: Telegram ID мастера.
    :return: InlineKeyboardMarkup
    """
    buttons_dict = {
        # --- Кнопки выбора типа ремонта ---
        1: InlineKeyboardButton(
            text="🔹 ДИАГНОСТИКА 🔹",
            callback_data=f"repair_type:diagnostic:{client_tg_id}:{master_tg_id}"
        ),
        2: InlineKeyboardButton(
            text="🔹 РЕМОНТ 🔹",
            callback_data=f"repair_type:repair:{client_tg_id}:{master_tg_id}"
        ),
        3: InlineKeyboardButton(
            text="🔹 ДИАГНОСТИКА И РЕМОНТ 🔹",
            callback_data=f"repair_type:diag_repair:{client_tg_id}:{master_tg_id}"
        ),
        4: InlineKeyboardButton(
            text="🔹 ТЕХ. ОБСЛУЖИВАНИЕ 🔹",
            callback_data=f"repair_type:to:{client_tg_id}:{master_tg_id}"
        ),
        5: InlineKeyboardButton(
            text="🔹 ВВЕСТИ ТЕКСТОМ 🔹",
            callback_data=f"repair_type:custom:{client_tg_id}:{master_tg_id}"
        ),

        # --- Кнопки заявок и подтверждений ---
        6: InlineKeyboardButton(
            text="✅ Создать заявку на ремонт",
            callback_data=f"create_order:{client_tg_id}:{master_tg_id}"
        ),
        7: InlineKeyboardButton(
            text="🔺 ОТПРАВИТЬ ЗАЯВКУ НА РЕМОНТ 🔺",
            callback_data=f"send_repair_req:{client_tg_id}:{master_tg_id}"
        ),

        # --- Кнопка ответа на сообщение ---
        8: InlineKeyboardButton(
            text="🔹 ОТВЕТИТЬ 🔹",
            callback_data=f"send_answer:{client_tg_id}:{master_tg_id}"
        ),

        # --- Кнопка "Назад" ---
        9: InlineKeyboardButton(
            text="🔺 Назад к выбору 🔺",
            callback_data="cancel"
        ),

        # --- Кнопка "Удалить" ---
        10: InlineKeyboardButton(
            text="🔺 НЕ ОТВЕЧАТЬ 🔺",
            callback_data="cancel"
        ),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


def clear_user_chat() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧹 Очистить чат", callback_data="clean_client_chat")]
    ])


def back_button(to: str = "main") -> list:
    """Универсальная кнопка 'Назад' — возвращает строку для inline_keyboard."""
    return [InlineKeyboardButton(text="🔺 Назад 🔺", callback_data=f"back:{to}")]


def check_data():
    kb_list = [
        [InlineKeyboardButton(text="✅СОЗДАТЬ УЧЁТНУЮ ЗАПИСЬ", callback_data='correct')],
        [InlineKeyboardButton(text="🔺 ОТМЕНА 🔺", callback_data='incorrect')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list)


