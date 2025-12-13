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
        # Добавляем дополнительную строку кнопок для администратора
        create_comm.append([InlineKeyboardButton(text='👍 ПОСТАВИТЬ ОЦЕНКУ МАСТЕРУ', callback_data='send_rate')])
    keyboard4 = InlineKeyboardMarkup(inline_keyboard=create_comm)
    return keyboard4


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


def generate_time_buttons(hours_set: set):
    # Сортируем входящее множество часов
    sorted_hours = sorted(hours_set)

    # Начинаем формировать кнопки
    rows = []  # Список строк
    current_row = []  # Текущая строка кнопок

    for hour in sorted_hours:
        # Создаем кнопку с текстом в формате "HH:00"
        label = f"{hour}:00"
        button = InlineKeyboardButton(text=label, callback_data=f"time:{hour}")
        current_row.append(button)

        # Переход на следующую строку, если набралось 3 кнопки
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []

    # Проверяем наличие последней непустой строки
    if current_row:
        rows.append(current_row)

    # Создаем и возвращаем разметку клавиатуры
    keyboard19 = InlineKeyboardMarkup(inline_keyboard=rows)
    return keyboard19


def generate_calendar_buttons():
    today = date.today()
    year = today.year
    month = today.month

    # Определяем количество дней в месяце
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

    # --- Заголовок с днями недели ---
    weekday_headers = [
        InlineKeyboardButton(text=day, callback_data="ignore") for day in ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    ]
    rows.append(weekday_headers)

    # --- Генерация строк с числами ---
    first_weekday = first_day_of_month.weekday()  # 0=ПН ... 6=ВС
    current_row = []

    # Добавляем пустые кнопки перед первым днём
    for _ in range(first_weekday):
        current_row.append(InlineKeyboardButton(text="✖️", callback_data="ignore"))

    # Проходим по всем числам месяца
    for day in range(1, days_in_month + 1):
        current_date = date(year, month, day)

        if current_date < today:
            btn = InlineKeyboardButton(text="✖️", callback_data="ignore")
        else:
            btn = InlineKeyboardButton(text=str(day), callback_data=f"day:{day}")

        current_row.append(btn)

        # Переход на следующую строку при достижении воскресенья или конца месяца
        if (first_weekday + day) % 7 == 0 or day == days_in_month:
            # Если строка короче 7 элементов — дополняем до 7 эмодзи
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


def send_text():
    kb_list2 = [
        [InlineKeyboardButton(text="🔹 ЛИЧНЫЙ КАБИНЕТ 🔹", callback_data='account')],
        [InlineKeyboardButton(text="🔹 ИНФОРМАЦИЯ 🔹", callback_data='o_nas')],
        [InlineKeyboardButton(text="🔹 ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ 🔹", callback_data='FAQ')],
        [InlineKeyboardButton(text="️🔹 ️КОНТАКТЫ. АДРЕС СТО 🔹", callback_data='get_person')]
    ]

    keyboard_3 = InlineKeyboardMarkup(inline_keyboard=kb_list2)
    return keyboard_3


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


def mess_menu(index: list):
    buttons_dict = {
        1: InlineKeyboardButton(text="🔹 ОЖИДАНИЕ 🔹", callback_data='mess:await'),
        2: InlineKeyboardButton(text="🔹 ОТКАЗ 🔹", callback_data='mess:refuse'),
        3: InlineKeyboardButton(text="🔹 ЗВОНИТЕ 🔹", callback_data='mess:call'),
        4: InlineKeyboardButton(text="🔹 НАЗНАЧИТЬ ВРЕМЯ 🔹", callback_data='mess:time'),
        5: InlineKeyboardButton(text="🔹 ОТВЕТИТЬ 🔹", callback_data='replay_mess'),
        6: InlineKeyboardButton(text="🔹 НА СЕГОДНЯ 🔹", callback_data='time:today'),
        7: InlineKeyboardButton(text="🔹 ВЫБРАТЬ ДЕНЬ 🔹", callback_data='time:next_days'),
    }

    inline_buttons = [[buttons_dict[idx]] for idx in index if idx in buttons_dict]

    keyboard10 = InlineKeyboardMarkup(inline_keyboard=inline_buttons)
    return keyboard10


def check_data():
    kb_list = [
        [InlineKeyboardButton(text="✅СОЗДАТЬ УЧЁТНУЮ ЗАПИСЬ", callback_data='correct')],
        [InlineKeyboardButton(text="❌ОТМЕНА", callback_data='incorrect')]
    ]
    keyboard_2 = InlineKeyboardMarkup(inline_keyboard=kb_list)
    return keyboard_2
