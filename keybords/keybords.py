# This Python file uses the following encoding: utf-8
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import date, datetime


authorization = InlineKeyboardButton(text='🔆 АВТОРИЗАЦИЯ 🔆', callback_data='authorization')
keyboard = InlineKeyboardMarkup(inline_keyboard=[[authorization]])

user_chat = InlineKeyboardButton(text='Показать на Яндекс Карте',
                                 url='https://yandex.ru/navi/?whatshere%5Bpoint%5D=73.305003%2C54.'
                                     '908418&whatshere%5Bzoom%5D=18&lang=ru&from=navi')
keyboard5 = InlineKeyboardMarkup(inline_keyboard=[[user_chat]])

comment_onas = [
    [InlineKeyboardButton(text='Показать отзывы наших клиентов', callback_data='comment')],
    [InlineKeyboardButton(text='Цены услуг ремонта', callback_data='price')]
]
keyboard7 = InlineKeyboardMarkup(inline_keyboard=comment_onas)


def keys_comment(master):
    create_comm = [[InlineKeyboardButton(text='📝 НАПИСАТЬ ОТЗЫВ ', callback_data='create_comment')]]
    if master:
        # Добавляем дополнительную строку кнопок
        create_comm.append([InlineKeyboardButton(text='👍 ПОСТАВИТЬ ОЦЕНКУ МАСТЕРУ', callback_data='send_rate')])
    return InlineKeyboardMarkup(inline_keyboard=create_comm)


def generate_buttons(count: int, labels: list):
    buttons = []  # Список для хранения рядов кнопок

    # Генерируем кнопки одну над другой f"{number:^10}"
    for i in range(min(count, len(labels))):
        button_row = [InlineKeyboardButton(text=labels[i][0], callback_data=f'master:{labels[i][0]}, {labels[i][1]},'
                                                                            f' {labels[i][2]}')]
        buttons.append(button_row)

    # Создаем клавиатуру с набранными кнопками
    keyboard8 = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard8


DEFAULT_HOURS = set(range(8, 24))


def generate_time_buttons(hours_set: set, user_id: int):
    sorted_hours = sorted(hours_set)
    rows = []
    current_row = []

    for hour in sorted_hours:
        label = f"{hour}:00"
        # В callback_data добавляем час И user_id
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

    return InlineKeyboardMarkup(inline_keyboard=rows)


def generate_calendar_buttons(user_id: int):
    today = date.today()
    year = today.year
    month = today.month

    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    first_day_of_month = datetime(year, month, 1)
    first_day_next_month = datetime(next_year, next_month, 1)
    days_in_month = (first_day_next_month - first_day_of_month).days

    rows = []
    weekday_headers = [
        InlineKeyboardButton(text=day, callback_data="ignore")
        for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]
    rows.append(weekday_headers)

    first_weekday = first_day_of_month.weekday()
    current_row = []

    for _ in range(first_weekday):
        current_row.append(InlineKeyboardButton(text="✖️", callback_data="ignore"))

    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)

        if current_date < today:
            btn = InlineKeyboardButton(text="✖️", callback_data="ignore")
        else:
            # В callback_data добавляем день И user_id
            btn = InlineKeyboardButton(
                text=str(day),
                callback_data=f"calendar_day:{day}:{user_id}"
            )

        current_row.append(btn)

        if (first_weekday + day) % 7 == 0 or day == days_in_month:
            while len(current_row) < 7:
                current_row.append(InlineKeyboardButton(text="✖️", callback_data="ignore"))
            rows.append(current_row)
            current_row = []

    return InlineKeyboardMarkup(inline_keyboard=rows)


# Клавиатура с оценками.
rate = [
    [InlineKeyboardButton(text='👎', callback_data=f'grade:-5'),
     InlineKeyboardButton(text='2️⃣', callback_data=f'grade:2'),
     InlineKeyboardButton(text='3️⃣', callback_data=f'grade:3'),
     InlineKeyboardButton(text='4️⃣', callback_data=f'grade:4'),
     InlineKeyboardButton(text='👍', callback_data=f'grade:5')]
]
keyboard6 = InlineKeyboardMarkup(inline_keyboard=rate)


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
        [InlineKeyboardButton(text="🔹 МОИ ЗАКАЗЫ 🔹", callback_data='my_orders')],
        [InlineKeyboardButton(text="🔹 ОЦЕНИТЬ КЛИЕНТА 🔹", callback_data='rate_client')],
        [InlineKeyboardButton(text="🔹 ИСТОРИЯ РАБОТ 🔹", callback_data='work_history')]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb_list_2)


def user_menu():
    kb_list_3 = [
        [InlineKeyboardButton(text="🔹 ЛИЧНЫЙ КАБИНЕТ 🔹", callback_data='account')],
        [InlineKeyboardButton(text="🔹 ИНФОРМАЦИЯ 🔹", callback_data='o_nas')],
        [InlineKeyboardButton(text="🔹 ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ 🔹", callback_data='FAQ')],
        [InlineKeyboardButton(text="️🔹 ️КОНТАКТЫ. АДРЕС СТО 🔹", callback_data='get_person')]
    ]

    return InlineKeyboardMarkup(inline_keyboard=kb_list_3)


def login_menu(index: list):
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 РЕМОНТ 🔹", callback_data='car_repair'),
        2: InlineKeyboardButton(text="🔹 ТЕХНИЧЕСКОЕ ОБСЛУЖИВАНИЕ 🔹", callback_data='#'),
        3: InlineKeyboardButton(text="🔹 ДИАГНОСТИКА 🔹", callback_data='#'),
        5: InlineKeyboardButton(text="🔹 ПРОДОЛЖИТЬ 🔹", callback_data='car_rep_next'),
        6: InlineKeyboardButton(text="🔺 ОТМЕНА 🔺", callback_data='cancel'),
        7: InlineKeyboardButton(text="🔹 ВСТАТЬ В ОЧЕРЕДЬ 🔹", callback_data='in_stack'),
        8: InlineKeyboardButton(text="🔹 ЗАПИСАТЬСЯ НА РЕМОНТ 🔹", callback_data='create_rec'),
        9: InlineKeyboardButton(text="🔹 ЗАДАТЬ ВОПРОС 🔹", callback_data='send_message'),
        10: InlineKeyboardButton(text="🔹 ОСТАВИТЬ ОТЗЫВ 🔹", callback_data='send'),
        11: InlineKeyboardButton(text="🔹 МОИ ДАННЫЕ 🔹", callback_data='login'),
        12: InlineKeyboardButton(text="🔹 ИЗМЕНИТЬ ДАННЫЕ 🔹", callback_data='edit_menu'),
        13: InlineKeyboardButton(text="🔹 ИМЯ 🔹", callback_data='edit:user_name'),
        14: InlineKeyboardButton(text="🔹 МАРКА АВТО 🔹", callback_data='edit:brand_auto'),
        15: InlineKeyboardButton(text="🔹 ГОД ВЫПУСКА 🔹", callback_data='edit:year_auto'),
        16: InlineKeyboardButton(text="🔹 ВИН НОМЕР 🔹", callback_data='edit:vin_number'),
        17: InlineKeyboardButton(text="🔹 КОНТАКТНЫЙ НОМЕР 🔹", callback_data='edit:contact'),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]

    keyboard9 = InlineKeyboardMarkup(inline_keyboard=inline_buttons)
    return keyboard9


def mess_menu(index: list, user_id: int):
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 ОЖИДАНИЕ 🔹", callback_data=f'mess:await:{user_id}'),
        2: InlineKeyboardButton(text="🔹 ОТКАЗ 🔹", callback_data=f'mess:refuse:{user_id}'),
        3: InlineKeyboardButton(text="🔹 ЗВОНИТЕ 🔹", callback_data=f'mess:call:{user_id}'),
        4: InlineKeyboardButton(text="🔹 НАЗНАЧИТЬ ВРЕМЯ 🔹", callback_data=f'mess:time:{user_id}'),
        5: InlineKeyboardButton(text="🔹 ОТВЕТИТЬ 🔹", callback_data=f'replay_mess:{user_id}'),
        6: InlineKeyboardButton(text="🔹 НА СЕГОДНЯ 🔹", callback_data=f'time:today:{user_id}'),
        7: InlineKeyboardButton(text="🔹 ВЫБРАТЬ ДЕНЬ 🔹", callback_data=f'time:next_days:{user_id}'),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]
    return InlineKeyboardMarkup(inline_keyboard=inline_buttons)


def check_data():
    kb_list = [
        [InlineKeyboardButton(text="✅СОЗДАТЬ УЧЁТНУЮ ЗАПИСЬ", callback_data='correct')],
        [InlineKeyboardButton(text="❌ОТМЕНА", callback_data='incorrect')]
    ]
    keyboard_2 = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard_2
