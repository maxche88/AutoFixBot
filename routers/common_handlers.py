"""
Модуль обработки команд и callback-запросов Telegram-бота на базе aiogram.

Содержит логику авторизации пользователей, управления личным кабинетом,
отправки сообщений техподдержке, записи на ремонт, оставления отзывов и
оценки мастеров.

Основные компоненты:
- FSM-состояния для пошаговых сценариев (регистрация, редактирование данных и т.д.)
- Валидация ввода (телефон и др.)
- Интеграция с базой данных через `database.requests`
- Использование клавиатур из `keybords.keybords`
"""

from aiogram import Router, types, F
from config import bot
from aiogram.filters.command import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keybords import keybords as kb
from database.requests import (get_user_role, add_user, add_comment, add_grade, all_orders_by_user,
                               count_and_name_gen, delete_order, get_user_dict, update_user, can_mess_true,
                               get_orders_by_user, update_order)
from func.func_bot import get_greeting
import re


router = Router()

titul_img = FSInputFile("img/titul.jpg")


# ==============================
# FSM-СОСТОЯНИЯ
# ==============================

class Reg(StatesGroup):
    """Состояния для процесса регистрации нового пользователя."""
    user_name = State()
    user_id = State()
    brand_auto = State()
    tel = State()
    date_reg = State()
    check_state = State()


class Edit(StatesGroup):
    """Состояния для редактирования личных данных пользователя."""
    edit_login = State()


class Mess(StatesGroup):
    """Состояния для отправки сообщения в поддержку и последующего взаимодействия."""
    mess_step = State()


class Repair(StatesGroup):
    """Состояния для создания заявки на ремонт."""
    car_repair_step1 = State()
    car_repair_step2 = State()
    car_repair_step3 = State()


class Send(StatesGroup):
    """Состояния для оставления отзыва."""
    send_text = State()


class ClientReply(StatesGroup):
    """Состояния для ответа на сообщение мастера."""
    waiting_for_reply_text = State()


class Booking(StatesGroup):
    """Состояния для записи и отправку формы всем мастерам."""
    choosing_service = State()
    confirming_data = State()


class AcceptWork(StatesGroup):
    """Состояния для подтверждения работы и поставить оценку мастеру."""
    waiting_for_grade = State()


# ==============================
# ВХОД
# ==============================
@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    """
    Обрабатывает команду /start.

    В зависимости от роли пользователя показывает разные клавиатуры:
    - user → обычное меню
    - master → меню мастера
    - admin → админ-панель
    Если пользователь не авторизован — просит пройти авторизацию.
    """
    user_id = message.from_user.id
    name = message.chat.first_name

    role = await get_user_role(user_id)

    # Если пользователь не найден в БД
    if role is None:
        await message.answer(
            f"{name} <b>Пожалуйста, пройдите быструю АВТОРИЗАЦИЮ.</b>\n"
            "Это обязательная процедура для использования сервиса!",
            reply_markup=kb.keyboard
        )
        return

    # Выбираем клавиатуру в зависимости от роли
    if role == "admin":
        reply_markup = kb.admin_menu()  # клавиатура админа
    elif role == "master":
        reply_markup = kb.master_menu()  # клавиатура мастера
    elif role == "user":
        reply_markup = kb.user_menu()  # клавиатура клиента
    else:
        # Если в БД оказалась неизвестная роль
        reply_markup = kb.keyboard

    greeting = await get_greeting()
    await message.answer_photo(
        photo=titul_img,
        caption=(
            f"<b>{greeting} {name}</b>\n\n"
            "Для удобства пользуйтесь кнопками ниже ⬇️"
        ),
        reply_markup=reply_markup
    )


# ==============================
# АВТОРИЗАЦИЯ
# ==============================
@router.callback_query(F.data == "authorization")
async def reg_one(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс регистрации при нажатии кнопки 'Авторизация'."""
    user_id = call.from_user.id

    if await get_user_role(user_id):
        await call.answer("Вы уже авторизированы", show_alert=True)
        return

    await bot.send_message(user_id, "Отправьте ваше ИМЯ")
    await state.update_data(user_id=user_id)
    await state.set_state(Reg.user_name)


@router.message(Reg.user_name)
async def reg_two(message: Message, state: FSMContext) -> None:
    """Принимает имя пользователя и запрашивает марку авто."""
    await state.update_data(user_name=message.text[:20], date_reg=message.date)
    await message.answer("<b>Отправьте вашу марку авто.</b>")
    await state.set_state(Reg.brand_auto)


@router.message(Reg.brand_auto)
async def reg_three(message: Message, state: FSMContext) -> None:
    """Принимает марку авто и запрашивает номер телефона."""
    await state.update_data(brand_auto=message.text[:20])
    await message.answer(
        "<b>Отправьте ваш номер телефона.</b>\n"
        "Сотовый номер должен начинаться на 7!"
    )
    await state.set_state(Reg.tel)


@router.message(Reg.tel)
async def reg_four(message: Message, state: FSMContext) -> None:
    """
    Валидирует номер телефона.

    Ожидается формат: 7XXXXXXXXXX (11 цифр, начинается на 7).
    При корректном номере — форматирует с '+' и переходит к подтверждению данных.
    """
    user_input = message.text.strip()

    phone_pattern = re.compile(r'^7\d{10}$')

    if phone_pattern.match(user_input):
        formatted_number = f"+{user_input}"
        await state.update_data(tel=formatted_number)
        data = await state.get_data()

        caption = (
            "<b>Убедитесь в правильности ваших данных!</b>\n"
            "Эта информация требуется для обратной связи с вами.\n\n"
            f"Имя: {data.get('user_name')}\n"
            f"Марка авто: {data.get('brand_auto')}\n"
            f"Контактный телефон: {data.get('tel')}"
        )
        await message.answer(text=caption, reply_markup=kb.check_data())
        await state.set_state(Reg.check_state)
    else:
        await message.answer(
            "Пожалуйста, введите корректный номер телефона.\n"
            "Номер должен начинаться на 7 без '+'!\n"
            "Пример: 79997773366"
        )


@router.callback_query(F.data == "correct", Reg.check_state)
async def confirm_registration(call: CallbackQuery, state: FSMContext) -> None:
    """Подтверждает регистрацию и сохраняет данные пользователя."""
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer_photo(photo=titul_img)
    await call.message.answer(
        "Поздравляем, вы авторизированы! Теперь вы можете пользоваться данным сервисом.",
        reply_markup=kb.user_menu()
    )

    data = await state.get_data()
    new_user = {
        "tg_id": data.get("user_id"),
        "user_name": data.get("user_name"),
        "status": "Клиент",
        "rating": 1,
        "contact": data.get("tel"),
        "brand_auto": data.get("brand_auto"),
    }

    await add_user(new_user)
    await state.clear()


@router.callback_query(F.data == "incorrect", Reg.check_state)
async def cancel_registration(call: CallbackQuery, state: FSMContext) -> None:
    """Отменяет регистрацию и возвращает пользователя к началу процесса."""
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        "<b>Пожалуйста, пройдите быструю Авторизацию</b>",
        reply_markup=kb.keyboard
    )
    await state.clear()


# ==============================
# ЛИЧНЫЙ КАБИНЕТ ПОЛЬЗОВАТЕЛЯ
# ==============================
@router.callback_query(F.data == "account")
async def account_menu(call: CallbackQuery) -> None:
    """Открывает главное меню личного кабинета."""
    name = call.message.chat.first_name
    await call.message.answer(
        f"<b>{name}, вы вошли в личный кабинет!</b>\n"
        "Здесь вы можете:\n"
        "— Записаться на ремонт, диагностику или ТО\n"
        "— Задать вопрос по ремонту\n"
        "— Оставить отзыв или оценить мастера\n"
        "— Изменить регистрационные данные",
        reply_markup=kb.login_menu([8, 4, 9, 10, 11])
    )


# ==============================
# ТЕКУЩИЙ РЕМОНТ info_rem
# ==============================

REPAIR_STATUS_DISPLAY = {
    "in_work": "В работе",
    "wait": "Ожидание",
    "close": "Закрыт"
}


@router.callback_query(F.data == "info_rem")
async def info_rem(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    orders = await get_orders_by_user(tg_id_user=user_id, active=True)

    if not orders:
        await call.message.answer("❌ НЕТ ЗАКАЗОВ ❌.")
    else:
        for order in orders:
            date_str = order.get("date", "не указана")
            if isinstance(date_str, str) and "T" in date_str:
                date_str = date_str.split("T")[0]

            status_raw = order['repair_status']
            status_display = REPAIR_STATUS_DISPLAY.get(status_raw, status_raw)
            is_active = (status_raw == "wait" and order.get("complied") is True)

            text = (
                "📋 <b>Активный заказ</b>\n"
                f"Результат: {'Работа выполнена' if order['complied'] else 'В работе'}\n\n"
                f"🆔 ID заказа: {order['id']}\n"
                f"👤 Мастер: {order['master_name']}\n"
                f"🚗 Марка авто: {order.get('brand_auto') or '—'}\n"
                f"📆 Год выпуска: {order.get('year_auto') or '—'}\n"
                f"🔢 Гос. номер: {order.get('gos_num') or '—'}\n"
                f"🔧 Статус: {status_display}\n"
                f"📝 Описание:\n{order.get('description') or '—'}\n\n"
                f"📅 Дата создания: {date_str}"
            )

            reply_markup = None

            if is_active:
                reply_markup = kb.get_accept_work_keyboard(
                    order_id=order["id"],
                    master_tg_id=order["tg_id_master"]
                )

            await call.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=reply_markup
            )

    await call.answer()


# ==============================
# ПРИНЯТЬ РАБОТУ
# ==============================
@router.callback_query(F.data.startswith("accept_work:"))
async def handle_accept_work(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    order_id = int(parts[1])
    master_tg_id = int(parts[2])

    # Сохраняем данные для следующего шага (оценки)
    await state.update_data(order_id=order_id, master_tg_id=master_tg_id)

    await call.message.answer(
        "⭐ Пожалуйста, оцените работу мастера (1–5) ⭐",
        reply_markup=kb.rating_keyboard()  # клавиатура с кнопками оценки
    )
    await state.set_state(AcceptWork.waiting_for_grade)
    await call.answer()


@router.callback_query(AcceptWork.waiting_for_grade, F.data.startswith("grade:"))
async def process_grade(call: CallbackQuery, state: FSMContext):
    try:
        grade = int(call.data.split(":", 1)[1])
        if grade not in (1, 2, 3, 4, 5):
            raise ValueError
    except (ValueError, IndexError):
        await call.answer("❌ Выберите оценку от 1 до 5", show_alert=True)
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    master_tg_id = data.get("master_tg_id")

    if not order_id or not master_tg_id:
        await call.message.answer("❌ Ошибка сессии. Попробуйте снова.")
        await state.clear()
        await call.answer()
        return

    # Обновляем заказ (статус → "close")
    success = await update_order(order_id, "close")
    if not success:
        await call.message.answer("❌ Не удалось обновить заказ.")
        await state.clear()
        await call.answer()
        return

    # Ставим оценку мастеру
    await add_grade(master_tg_id, grade)

    # Финальное сообщение
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer(
        "Спасибо, что выбрали наше СТО!"
    )

    await state.clear()
    await call.answer()


# ==============================
# ЗАПИСАТЬСЯ НА РЕМОНТ appointment
# ==============================
# показываем тип записи
@router.callback_query(F.data == "appointment")
async def start_booking(call: CallbackQuery, state: FSMContext):
    await call.message.answer(
        "🔧 Выберите тип работ:",
        reply_markup=kb.login_menu([3, 1, 2])
    )
    await state.set_state(Booking.choosing_service)
    await call.answer()


SERVICE_NAMES = {
    "repair": "Ремонт",
    "maintenance": "Тех. обслуживание",
    "diagnostics": "Диагностика"
}


# Обработчик выбора услуги
@router.callback_query(Booking.choosing_service, F.data.startswith("service:"))
async def handle_service_choice(call: CallbackQuery, state: FSMContext):
    service_key = call.data.split(":", 1)[1]

    if service_key not in SERVICE_NAMES:
        await call.answer("❌ Недопустимый выбор", show_alert=True)
        return

    service_name = SERVICE_NAMES[service_key]

    # Сохраняем выбранный тип услуги
    await state.update_data(chosen_service=service_name)

    # Получаем данные пользователя из БД
    user_id = call.from_user.id
    user_data = await get_user_dict(
        user_id, ("user_name", "rating", "brand_auto", "year_auto", "contact")
    )

    if not user_data:
        await call.message.answer("❌ Не удалось загрузить ваши данные. Обратитесь в поддержку.")
        await state.clear()
        await call.answer()
        return

    user_name, rating, brand_auto, year_auto, contact = user_data

    # Формируем сообщение с данными
    preview_text = (
        "📋 <b>Проверьте ваши данные:</b>\n\n"
        f"Имя: {user_name}\n"
        f"Рейтинг: {rating}\n"
        f"Марка авто: {brand_auto}\n"
        f"Год выпуска: {year_auto}\n"
        f'Контакт: <a href="tel:{contact}">{contact}</a>\n'
        f"Тип услуги: {service_name}\n\n"
        "Если всё верно — нажмите <b>«Записаться»</b>.\n"
        "Мастер свяжется с вами, чтобы уточнить удобное время."
    )

    await call.message.answer(preview_text, reply_markup=kb.login_menu([19, 6]))
    await state.set_state(Booking.confirming_data)
    await call.answer()


# Обработчик "Подтвердить" и "Отмена"
@router.callback_query(Booking.confirming_data, F.data == "confirm_booking")
async def confirm_booking(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service_name = data.get("chosen_service")
    user_id = call.from_user.id

    # Получаем данные
    user_data = await get_user_dict(
        user_id, ("user_name", "rating", "brand_auto", "year_auto", "contact")
    )
    if not user_data:
        await call.message.answer("❌ Ошибка при загрузке данных.")
        await state.clear()
        await call.answer()
        return

    user_name, rating, brand_auto, year_auto, contact = user_data

    # Формируем сообщение для мастеров
    formatted_request = (
        "🔔 <b>Новая заявка на запись!</b>\n\n"
        f"👤 Имя: {user_name}\n"
        f"⭐️ Рейтинг: {rating}\n"
        f"🚗 Марка авто: {brand_auto}\n"
        f"📆 Год выпуска: {year_auto}\n"
        f'📱 Телеграм ID: <a href="tg://user?id={user_id}">{user_id}</a>\n'
        f'📞 Сот.тел: <a href="tel:{contact}">{contact}</a>\n'
        f"⚙️ Тип услуги: {service_name}\n\n"
        "Если готовы принять — свяжитесь с клиентом и уточните время."
    )

    # Получаем всех мастеров и админов с can_mess=True
    master_ids = await can_mess_true()  # возвращает список tg_id

    # Отправляем каждому
    for master_id in master_ids:
        await bot.send_message(
            chat_id=master_id,
            text=formatted_request,
            parse_mode="HTML",
            reply_markup=kb.staff_menu([3, 4, 5], user_id=user_id)
        )

    await call.message.answer("✅ Заявка отправлена! Мастер свяжется с вами в ближайшее время.")
    await state.clear()
    await call.answer()


@router.callback_query(Booking.confirming_data, F.data == "cancel")
async def cancel_booking(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer()


# ==============================
# ЗАДАТЬ ВОПРОС
# ==============================
@router.callback_query(F.data == "send_message")
async def initiate_support_message(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс отправки сообщения всем мастерам и админам с can_mess=True."""
    name = call.message.chat.first_name
    await call.message.answer(
        f"{name}, введите ваше сообщение (до 100 символов). Соблюдайте цензуру!"
    )
    await state.set_state(Mess.mess_step)


@router.message(Mess.mess_step)
async def forward_support_message(message: Message, state: FSMContext) -> None:
    """
    Формирует и пересылает сообщение от пользователя администраторам и мастерам,
    которые могут получать уведомления (`can_mess=true`).
    """
    user_id = message.chat.id
    message_text = message.text[:100]

    user_data = await get_user_dict(
        user_id, ("user_name", "rating", "brand_auto", "year_auto", "contact")
    )

    if not user_data:
        await message.answer("❌ Произошла ошибка. Попробуйте позже.")
        await state.clear()
        return

    user_name, rating, brand_auto, year_auto, contact = user_data

    formatted_message = (
        f"👤 Имя: {user_name}\n"
        f"⭐️ Рейтинг: {rating}\n"
        f"🚗 Марка авто: {brand_auto}\n"
        f"📆 Год выпуска: {year_auto}\n"
        f'📱 Телеграм ID: <a href="tg://user?id={user_id}">{user_id}</a>\n'
        f'📞 Контакт: <a href="tel:{contact}">{contact}</a>\n'
        f"📨 Сообщение:\n{message_text}"
    )

    admin_ids = await can_mess_true()
    await state.update_data(tg_id=user_id, user_name=user_name)

    # Отправляет всем администраторам и мастерам у которых can_mess=True
    for admin_id in admin_ids:
        await bot.send_message(
            chat_id=admin_id,
            text=formatted_message,
            reply_markup=kb.staff_menu([1, 2, 3, 4, 5], user_id=user_id)
        )

    await message.answer("Ваше сообщение отправлено! Ожидайте ответа...")
    await state.clear()


# ОТВЕТ НА СООБЩЕНИЕ ОТ МАСТЕРА
@router.callback_query(F.data.startswith("send_answer:"))
async def handle_send_answer_button(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    try:
        client_tg_id = int(parts[1])
        master_tg_id = int(parts[2])
    except ValueError:
        await call.answer("❌ Некорректный ID", show_alert=True)
        return

    # Проверка: текущий пользователь — это client_tg_id?
    if call.from_user.id != client_tg_id:
        await call.answer("❌ Эта кнопка не для вас", show_alert=True)
        return

    # Сохраняем ID мастера, которому отправим ответ
    await state.update_data(target_master_id=master_tg_id)

    await call.message.answer("✍️ Введите ваш ответ:")
    await state.set_state(ClientReply.waiting_for_reply_text)
    await call.answer()  # убираем анимацию загрузки


@router.message(ClientReply.waiting_for_reply_text)
async def process_client_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    master_tg_id = data.get("target_master_id")
    if not master_tg_id:
        await message.answer("❌ Ошибка: получатель не указан.")
        await state.clear()
        return

    client_tg_id = message.from_user.id
    client_name, brand_auto = await get_user_dict(client_tg_id, ("user_name", "brand_auto"))

    await message.bot.send_message(
        chat_id=master_tg_id,
        text=(
            f"📨 Ответ от клиента\n"
            f"📱 tg_id: {client_tg_id}\n"
            f"👤 Имя: {client_name} \n"
            f"🚗 Марка авто: {brand_auto}\n\n"
            f"{message.text}"
        )
    )
    await message.answer("✅ Ваше сообщение отправлено мастеру!")

    await state.clear()


# ЗАЯВКА НА РЕМОНТ ОТ КЛИЕНТА (ДЛЯ БЫСТРОГО ВЗАИМОДЕЙСТВИЯ С МАСТЕРОМ)
@router.callback_query(F.data.startswith("send_repair_req:"))
async def handle_send_repair_request(call: CallbackQuery):
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("❌ Ошибка запроса", show_alert=True)
        return

    try:
        client_tg_id = int(parts[1])
        master_tg_id = int(parts[2])
    except ValueError:
        await call.answer("❌ Некорректные данные", show_alert=True)
        return

    # Проверяем, что клиент существует
    client_data = await get_user_dict(client_tg_id)
    if not client_data:
        await call.answer("❌ Клиент не найден", show_alert=True)
        return

    # Отправляем мастеру сообщение с кнопкой создания заказа
    await bot.send_message(
        chat_id=master_tg_id,
        text=(
            f"🔹 ЗАЯВКА НА РЕМОНТ 🔹\n\n"
            f"👤 Имя: {client_data['user_name']}\n"
            f"🚗 Марка авто: {client_data['brand_auto']} \n"
            f"📆 Год выпуска: {client_data['year_auto']}\n"
            f"ℹ️ VIN: {client_data['vin_number']}\n"
            f"🔢 Гос. номер: {client_data['gos_num']}\n"
            f"📱 Телеграм: {client_tg_id}\n"
            f"📞 Сот. тел.: {client_data['contact']}\n\n"
            f"Выберите тип работ или введите текстом:"
        ),
        reply_markup=kb.action_buttons_orders_menu([1, 2, 3, 4, 5], client_tg_id, master_tg_id)
    )

    # Убираем кнопку у клиента
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("✅ Заявка отправлена мастеру!")
    await call.answer()


# ==============================
# ОСТАВИТЬ ОТЗЫВЫ ОБ СТО
# ==============================
@router.callback_query(F.data == "create_comment")
async def start_comment(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс оставления отзыва."""
    await call.message.edit_reply_markup(reply_markup=None)
    name = call.message.chat.first_name
    await call.message.answer(f"<b>{name}, напишите свой отзыв о СТО.</b>")
    await state.set_state(Send.send_text)


@router.message(Send.send_text)
async def save_comment(message: Message, state: FSMContext) -> None:
    """Сохраняет отзыв в базу данных."""
    await state.update_data(
        mess_id=message.message_id,
        user_id=message.from_user.id,
        user_name=message.from_user.full_name,
        send_text=message.text
    )
    data = await state.get_data()

    await add_comment({
        "tg_id": data["user_id"],
        "user_name": data["user_name"],
        "text": data["send_text"]
    })

    await message.answer(f"ID отзыва: {data['mess_id']}\nСпасибо за ваш отзыв!")
    await state.clear()


# ==============================
# ПОСТАВИТЬ ОЦЕНКУ МАСТЕРУ
# ==============================


@router.callback_query(F.data == "cancel")
async def cancel_fsm(call: CallbackQuery, state: FSMContext) -> None:
    """Отменяет текущее FSM-состояние и удаляет сообщение с клавиатурой."""
    await call.message.delete()
    await state.clear()
    await call.answer()


# ==============================
# МЕНЮ "МОИ ДАННЫЕ"
# ==============================
@router.callback_query(F.data == "login")
async def show_user_data(call: CallbackQuery) -> None:
    """Показывает текущие данные пользователя из базы."""
    user_id = call.message.chat.id
    reg_user = await get_user_dict(
        user_id,
        ("user_name", "rating", "brand_auto", "year_auto", "gos_num", "vin_number", "contact")
    )

    await call.message.answer(
        "Ваши регистрационные данные и информация об авто:"
    )
    await call.message.answer(
        f"Имя: {reg_user[0]}\n"
        f"Рейтинг: {reg_user[1]}\n"
        f"Марка авто: {reg_user[2]}\n"
        f"Год выпуска: {reg_user[3]}\n"
        f"Гос. номер: {reg_user[4]}\n"
        f"VIN номер: {reg_user[5]}\n"
        f"Контактный номер: {reg_user[6]}",
        reply_markup=kb.login_menu([12])
    )


# ==============================
# РЕДАКТИРОВАНИЕ ПРОФИЛЯ
# ==============================
@router.callback_query(F.data == "edit_menu")
async def edit_menu(call: CallbackQuery) -> None:
    """Открывает меню редактирования данных."""
    await call.message.answer(
        "Выберите данные для изменения или дополнения:",
        reply_markup=kb.login_menu([13, 14, 15, 18, 16, 17])
    )


@router.callback_query(F.data.startswith("edit"))
async def start_edit_field(call: CallbackQuery, state: FSMContext) -> None:
    """Редактирование выбранного поля."""
    field_map = {
        "user_name": "Имя",
        "brand_auto": "Марка авто",
        "year_auto": "Год выпуска",
        "gos_num": "Гос. номер",
        "vin_number": "VIN номер",
        "contact": "Контактный номер"
    }

    await call.message.edit_reply_markup(reply_markup=None)
    field_key = call.data.split(":")[1]
    await state.update_data(data_type=field_key)
    await call.message.answer(
        f"Введите {field_map[field_key]} (до 20 символов):"
    )
    await state.set_state(Edit.edit_login)


@router.message(Edit.edit_login)
async def save_edited_field(message: Message, state: FSMContext) -> None:
    """Сохраняет обновлённое значение поля в базу данных."""
    user_id = message.chat.id
    data = await state.get_data()
    field_name = data["data_type"]
    new_value = message.text[:20]

    await update_user(user_id, field_name, new_value)
    await message.answer("Данные успешно обновлены!")
    await state.clear()


# ==============================
# ИНФОРМАЦИОННЫЕ КОМАНДЫ
# ==============================
@router.callback_query(F.data == "o_nas")
async def about_service(call: CallbackQuery) -> None:
    """Отправляет информацию об автомастерской."""
    info_img = FSInputFile("img/info.jpg")
    caption = (
        "▫️Спасибо, что выбрали нашу автомастерскую.\n"
        "▫️Мы работаем уже более 20 лет и предоставляем качественный ремонт "
        "отечественных и импортных авто. Огромный опыт.\n"
        "▫️Специализация: диагностика и устранение неисправностей любой сложности.\n"
        "▫️Гарантируем качественный и оперативный ремонт.\n\n"
        "<i>Если авто заводится и глохнет, троит мотор и стал\n"
        "не ярок свет!? Найдём ответ — решим проблему.\n"
        "Езжай в компанию РАССВЕТ!</i>"
    )
    await call.message.answer_photo(photo=info_img, caption=caption, reply_markup=kb.keyboard7)


# ПОКАЗАТЬ ОТЗЫВЫ КЛИЕНТОВ
@router.callback_query(F.data == "comment")
async def show_comments(call: CallbackQuery) -> None:
    """Показывает отзывы (заглушка — функционал не реализован)."""
    await call.message.answer("Вот отзывы пользователей... (в разработке)")


# ПОКАЗАТЬ ПРАЙС ЦЕН
@router.callback_query(F.data == "price")
async def show_price_list(call: CallbackQuery) -> None:
    """Отправляет ориентировочный прайс из файла."""
    await call.message.answer(
        "❗️ Прайс является ориентировочным и может отличаться от фактической цены!\n"
        "❗️ Обговаривайте стоимость с мастером перед началом работ!"
    )
    with open("info/price.txt", "r", encoding="utf-8") as f:
        await call.message.answer(f.read())


# ПОКАЗАТЬ КОНТАКТНУЮ ИНФОРМАЦИЮ
@router.callback_query(F.data == "get_person")
async def show_contacts(call: CallbackQuery) -> None:
    """Отправляет контактную информацию и карту."""
    maps_img = FSInputFile("img/maps.jpg")
    caption = (
        "🏢 <b>СТО ЗАО Рассвет:</b> г. Омск, ул. 1-я Казахстанская, 81\n\n"
        "📞 <b>Телефон:</b> +79999999999\n\n"
        "📧 <b>Email:</b> sto@mail.ru"
    )
    await call.message.answer_photo(photo=maps_img, caption=caption, reply_markup=kb.keyboard5)
