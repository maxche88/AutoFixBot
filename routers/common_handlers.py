"""
Модуль обработки команд и callback-запросов Telegram-бота на базе aiogram.

Содержит логику авторизации пользователей, управления личным кабинетом,
отправки сообщений техподдержке, записи на ремонт, оставления отзывов и
оценки мастеров.

Основные компоненты:
- FSM-состояния для пошаговых сценариев (регистрация, редактирование данных и т.д.)
- Валидация ввода
- Интеграция с базой данных через `database.requests`
- Использование клавиатур из `keybords.keybords`
"""

from aiogram import Router, types, F
import asyncio
from bot import bot
from aiogram.filters.command import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keybords import keybords as kb
from database.requests import (get_user_role, add_user, add_comment, add_grade, get_user_dict, update_user,
                               can_mess_true, get_orders_by_user, update_order, get_visible_comments,
                               get_filter_appointments)
from utils.time_bot import get_greeting
from utils.utils_bot import message_deleter
from config import Config
from aiogram.exceptions import TelegramAPIError
import logging
import re


logger = logging.getLogger(__name__)

router = Router()

titul_img = FSInputFile("img/titul.png")


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
    mess_step = State()  # ввод текста


class SendFeedback(StatesGroup):
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


class AppointmentResponse(StatesGroup):
    waiting_for_text = State()


class QuickQuestionToMaster(StatesGroup):
    waiting_for_custom_text = State()


class Test(StatesGroup):
    in_tg_id = State()


# ==============================
# РЕГИСТРАЦИЯ registration
# ==============================
@router.callback_query(F.data == "registration")
async def reg_one(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс регистрации при нажатии кнопки 'Авторизация'."""
    user_id = call.from_user.id

    if await get_user_role(user_id):
        await call.answer("Вы уже авторизированы", show_alert=True)
        return

    logger.info(f"Пользователь {user_id} начал процесс регистрации.")

    auth_message_id = call.message.message_id

    # Отправляем запрос на имя
    prompt_msg = await call.message.answer("Отправьте ваше ИМЯ")

    # Инициализируем список временных сообщений
    await state.update_data(
        user_id=user_id,
        reg_message_ids=[auth_message_id, prompt_msg.message_id]
    )
    await state.set_state(Reg.user_name)
    await call.answer()


@router.message(Reg.user_name)
async def reg_two(message: Message, state: FSMContext) -> None:
    """Принимает имя и запрашивает марку авто."""
    await state.update_data(user_name=message.text[:20], date_reg=message.date)

    # Отправляем следующий запрос
    next_msg = await message.answer("Отправьте вашу марку авто (Без модели. Например: Toyota).")

    # Обновляем список сообщений
    data = await state.get_data()
    message_ids = data.get("reg_message_ids", [])
    message_ids.extend([message.message_id, next_msg.message_id])
    await state.update_data(reg_message_ids=message_ids)

    await state.set_state(Reg.brand_auto)


@router.message(Reg.brand_auto)
async def reg_three(message: Message, state: FSMContext) -> None:
    """Принимает марку авто и запрашивает номер телефона."""
    await state.update_data(brand_auto=message.text[:20])

    next_msg = await message.answer(
        "Отправьте ваш номер телефона.\n"
        "Сотовый номер должен начинаться на 7!"
    )

    data = await state.get_data()
    message_ids = data.get("reg_message_ids", [])
    message_ids.extend([message.message_id, next_msg.message_id])
    await state.update_data(reg_message_ids=message_ids)

    await state.set_state(Reg.tel)


@router.message(Reg.tel)
async def reg_four(message: Message, state: FSMContext) -> None:
    """Валидирует номер телефона."""
    user_input = message.text.strip()
    phone_pattern = re.compile(r'^7\d{10}$')

    if phone_pattern.match(user_input):
        formatted_number = f"+{user_input}"
        await state.update_data(tel=formatted_number)
        data = await state.get_data()

        caption = (
            "Убедитесь в правильности ваших данных!\n"
            "Эта информация требуется для обратной связи с вами.\n\n"
            f"Имя: {data.get('user_name')}\n"
            f"Марка авто: {data.get('brand_auto')}\n"
            f"Контактный телефон: {data.get('tel')}"
        )
        confirm_msg = await message.answer(text=caption, reply_markup=kb.check_data())

        # Добавляем текущее сообщение + подтверждение
        message_ids = data.get("reg_message_ids", [])
        message_ids.extend([message.message_id, confirm_msg.message_id])
        await state.update_data(reg_message_ids=message_ids)

        await state.set_state(Reg.check_state)
    else:
        # Ошибка отправляем уведомление, НО не выходим из состояния
        error_msg = await message.answer(
            "Пожалуйста, введите корректный номер телефона.\n"
            "Номер должен начинаться на 7 без '+'!\n"
            "Пример: 79997773366"
        )
        # Добавляем сообщение клиента + ошибку, чтобы удалить их в будущем
        data = await state.get_data()
        message_ids = data.get("reg_message_ids", [])
        message_ids.extend([message.message_id, error_msg.message_id])
        await state.update_data(reg_message_ids=message_ids)


@router.callback_query(F.data == "correct", Reg.check_state)
async def confirm_registration(call: CallbackQuery, state: FSMContext) -> None:
    """Подтверждает регистрацию и удаляет весь мусор."""
    await call.message.edit_reply_markup(reply_markup=None)

    # Получаем все ID для удаления
    data = await state.get_data()
    message_ids = data.get("reg_message_ids", [])

    # Удаляем дубликаты и None
    message_ids = list(set(msg_id for msg_id in message_ids if msg_id))

    # Удаляем ВСЕ временные сообщения через delay
    if message_ids:
        _ = asyncio.create_task(
                message_deleter(
                    bot=bot,
                    chat_id=call.message.chat.id,
                    message_ids=message_ids,
                    delay=1
                )
        )

    user_id = data.get("user_id")
    user_name = data.get("user_name")
    # Сохраняем пользователя
    new_user = {
        "tg_id": user_id,
        "user_name": user_name,
        "status": "Клиент",
        "rating": 1,
        "contact": data.get("tel"),
        "brand_auto": data.get("brand_auto"),
    }

    # Отправляем финальные сообщения
    await call.message.answer_photo(photo=titul_img)
    await call.message.answer("📁 <b>ГЛАВНОЕ МЕНЮ</b>\n\n"
                              f"<b>Поздравляем, {user_name}! Вы зарегистрированы.</b>\n"
                              "Здесь вы найдёте всё необходимое для взаимодействия с данным сервисом: "
                              "запись, ремонт, поддержка и полезная информация.\n\n"
                              "Выберите нужный раздел ниже 👇",
        reply_markup=kb.user_main_menu()
    )

    logger.info(f"Пользователь {user_id} успешно завершил регистрацию.")
    await add_user(new_user)
    await call.message.delete()
    await state.clear()


@router.callback_query(F.data == "incorrect", Reg.check_state)
async def cancel_registration(call: CallbackQuery, state: FSMContext) -> None:
    """Отменяет регистрацию но оставляет кнопку Авторизация"""
    await call.message.edit_reply_markup(reply_markup=None)

    # Возвращаем в меню авторизации
    await call.message.answer(
        "<b>Пожалуйста, пройдите быструю Регистрацию</b>",
        reply_markup=kb.auth_menu()
    )

    # Удаляем ВСЕ временные сообщения, включая fallback
    data = await state.get_data()
    message_ids = data.get("reg_message_ids", [])

    message_ids = list(set(msg_id for msg_id in message_ids if msg_id))
    if message_ids:
        _ = asyncio.create_task(
                message_deleter(
                    bot=bot,
                    chat_id=call.message.chat.id,
                    message_ids=message_ids,
                    delay=1
                )
        )

    await state.clear()


# ==============================
# ВХОД
# ==============================
@router.message(Command("start"))
async def cmd_start(message: types.Message) -> None:
    user_id = message.from_user.id
    name = message.chat.first_name
    role = await get_user_role(user_id)

    if role is None:
        await message.answer(
            f"{name}, <b>пожалуйста, пройдите быструю РЕГИСТРАЦИЮ.</b>\n"
            "Это обязательная процедура для использования сервиса!",
            reply_markup=kb.auth_menu()
        )
        return

    logger.info(f"Пользователь {user_id} ({name}) вошёл в систему с ролью: {role}")

    await message.answer_photo(photo=titul_img)

    greeting = await get_greeting()
    user_data = await get_user_dict(tg_id=user_id, fields=["user_name"])
    user_name = user_data["user_name"]

    # Формируем текст в зависимости от роли
    if role == "admin":
        text = (
            "📁 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
            f"<b>{greeting} {user_name}</b>\n"
            "Управляйте пользователями, мастерами, записями и настройками сервиса.\n\n"
            "Выберите действие ниже 👇"
        )
        reply_markup = kb.admin_menu()

    elif role == "master":
        text = (
            "📁 <b>ПАНЕЛЬ МАСТЕРА</b>\n\n"
            f"<b>{greeting} {user_name}</b>\n"
            "Принимайте заявки на ремонт, управляйте записями клиентов, "
            "отвечайте на вопросы.\n\n"
            "Выберите нужный раздел ниже 👇"
        )
        reply_markup = kb.master_menu()

    elif role == "user":
        text = (
            "📁 <b>ГЛАВНОЕ МЕНЮ</b>\n\n"
            f"<b>{greeting} {user_name}</b>\n"
            "Здесь вы найдёте всё необходимое для взаимодействия с данным сервисом: "
            "запись, ремонт, поддержка и полезная информация.\n\n"
            "Выберите нужный раздел ниже 👇"
        )
        reply_markup = kb.user_main_menu()

    else:
        text = "Добро пожаловать! Пройдите регистрацию."
        reply_markup = kb.auth_menu()

    await message.answer(text, reply_markup=reply_markup, parse_mode="HTML")


# ==============================
# ЛИЧНЫЙ КАБИНЕТ ПОЛЬЗОВАТЕЛЯ
# ==============================
@router.callback_query(F.data == "account")
async def account_menu(call: CallbackQuery) -> None:
    """Открывает главное меню личного кабинета с обновлённым текстом."""

    menu_text = (
        "📁 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n"
        "Управляйте своими заявками, записями, личными данными и общением с мастерами "
        "автосервиса — всё в одном месте.\n\n"
        "Выберите действие ниже 👇"
    )

    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.user_personal_account()
    )
    await call.answer()


@router.callback_query(F.data == "back_main_menu")
async def back_to_main_menu(call: CallbackQuery):
    """Возвращает пользователя в основное меню."""
    menu_text = (
        "📁 <b>ГЛАВНОЕ МЕНЮ</b>\n\n"
        "Здесь вы найдёте всё необходимое для взаимодействия с данным сервисом: "
        "запись, ремонт, поддержка и полезная информация.\n\n"
        "Выберите нужный раздел ниже 👇"
    )

    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.user_main_menu()
    )
    await call.answer()


@router.callback_query(F.data == "back_personal_account")
async def back_to_personal_account(call: CallbackQuery, state: FSMContext):
    """Возвращает пользователя из подменю 'ЗАПИСАТЬСЯ' в 'ЛИЧНЫЙ КАБИНЕТ'"""
    await state.clear()
    menu_text = (
        "📁 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n"
        "Управляйте своими заявками, записями, личными данными и общением с мастерами "
        "автосервиса — всё в одном месте.\n\n"
        "Выберите действие ниже 👇"
    )
    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.user_personal_account()  # возвращаем в подменю личный кабинет
    )
    await call.answer()


# ==============================
# ТЕКУЩИЙ РЕМОНТ
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
        await call.answer("❌ У вас нет активных заказов.", show_alert=True)
        return

    sent_message_ids = []  # Список с id сообщений, для последующего удаления

    # Отправляем каждый заказ как НОВОЕ сообщение
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
            f"🚗 Марка авто: {order.get('brand_auto')}\n"
            f"⚙️ Модель авто: {order['model_auto']}\n"
            f"🛞 Пробег км: {order.get('total_km')}\n"
            f"📆 Год выпуска: {order.get('year_auto')}\n"
            f"🔢 Гос. номер: {order.get('gos_num')}\n"
            f"🔧 Статус: {status_display}\n"
            f"📝 Описание:\n{order.get('description')}\n\n"
            f"📅 Дата создания: {date_str}"
        )

        reply_markup = None

        if is_active:
            reply_markup = kb.get_accept_work_keyboard(
                [1, 3, 4],  # Кнопка "Принять работу", "Какая цена?", "Сообщение"
                order_id=order["id"],
                master_tg_id=order["tg_id_master"]
            )

        else:
            reply_markup = kb.get_accept_work_keyboard(
                [2, 3, 4],  # Кнопка "Когда будет готово?", "Какая цена?", "Написать свой вопрос"
                master_tg_id=order["tg_id_master"]
            )

        msg = await call.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup  # Кнопка "Принять заказ" под каждым выполненным заказом
        )

        sent_message_ids.append(msg.message_id)  # Добавляем в список id сообщений

    # Отправляем кнопку "Назад" ПОД всеми заказами
    back_msg = await call.message.answer(
        "↩️ Вернуться в личный кабинет:",
        reply_markup=kb.user_back_personal_account()
    )

    sent_message_ids.append(back_msg.message_id)

    # Сохраняем ID для удаления
    await state.update_data(sent_order_messages=sent_message_ids)
    await call.answer()


# Скрывает текущие заказы, возвращает в личный кабинет
@router.callback_query(F.data == "back_to_account")
async def back_to_account_from_orders(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    message_ids = data.get("sent_order_messages", [])

    if message_ids:
        # Удаляем все временные сообщения (заказы + кнопка "Назад")
        for msg_id in message_ids:
            await call.bot.delete_message(
                chat_id=call.message.chat.id,
                message_id=msg_id
            )

    await state.clear()
    await call.answer()


# ==============================
# БЫСТРЫЕ ОТВЕТЫ
# ==============================
QUICK_MESSAGE_TEMPLATES = {
    "question_price": "💰 Какая цена?",
    "question_time": "💬 Когда будет готово?",
    "app_ok": "✅ Клиент подтвердил запись: «Приеду вовремя».",
    "app_no": "❌ Клиент отменил запись: «Не сможет приехать».",
    "app_trans": "🔄 Клиент хочет перенести запись."
}


@router.callback_query(F.data.startswith("quick_mess:"))
async def quick_mess(call: CallbackQuery):
    parts = call.data.split(":", 3)
    if len(parts) != 3:
        await call.answer("❌ Некорректный формат быстрого сообщения.", show_alert=True)
        return

    action = parts[1]
    try:
        tg_id = int(parts[2])
    except ValueError:
        await call.answer("❌ Некорректный ID получателя.", show_alert=True)
        return

    user_tg_id = call.from_user.id
    user_data = await get_user_dict(tg_id=user_tg_id, fields=["user_name"])
    user_name = user_data.get("user_name")

    # Получаем текст вопроса из словаря
    question_text = QUICK_MESSAGE_TEMPLATES.get(action)
    if not question_text:
        await call.answer("❌ Неизвестный тип быстрого сообщения.", show_alert=True)
        return

    text_for_master = (
        "🔔 СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ\n"
        f"👤 Имя: {user_name}\n"
        f"📱 Телеграм: {user_tg_id}\n\n"
        f"💬 {question_text}"
    )

    await bot.send_message(chat_id=tg_id,
                           text=text_for_master,
                           reply_markup=kb.common_menu([4]))

    await call.answer("✅ Ваш запрос на перенос записи отправлен мастеру!", show_alert=True)


# ==============================
# ПРИНЯТЬ РАБОТУ
# ==============================
@router.callback_query(F.data.startswith("accept_work:"))
async def handle_accept_work(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) < 3:
        await call.answer("❌ Неверный формат", show_alert=True)
        return

    try:
        order_id = int(parts[1])
        master_tg_id = int(parts[2])
    except (ValueError, IndexError) as e:
        logger.error(f"Ошибка данных в callback: {e}")
        await call.answer("❌ Ошибка данных", show_alert=True)
        return

    data = await state.get_data()
    sent_order_messages = data.get("sent_order_messages", [])

    if isinstance(sent_order_messages, list) and sent_order_messages:
        # Клиент из "Текущий ремонт"
        # Удаляем ВСЕ сообщения, включая call.message
        for msg_id in sent_order_messages:
            try:
                await call.bot.delete_message(call.message.chat.id, msg_id)
            except TelegramAPIError:
                pass
    else:
        # Клиент из уведомления мастера
        # Удаляем ТОЛЬКО call.message
        try:
            await call.message.delete()
        except TelegramAPIError:
            pass

    # Сохраняем данные и отправляем оценку
    await state.update_data(order_id=order_id, master_tg_id=master_tg_id)
    grade_msg = await call.message.answer(
        "Пожалуйста, оцените работу мастера!",
        reply_markup=kb.rating_keyboard()
    )
    await state.update_data(grade_message_id=grade_msg.message_id)
    await state.set_state(AcceptWork.waiting_for_grade)
    await call.answer()


@router.callback_query(AcceptWork.waiting_for_grade, F.data.startswith("grade:"))
async def process_grade(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    try:
        grade = int(call.data.split(":", 1)[1])
        if grade not in (1, 2, 3, 4, 5):
            raise ValueError
    except (ValueError, IndexError) as e:
        logger.error(f"Не удалось поставить оценку мастеру: {e}")
        await call.answer("❌ Выберите оценку от 1 до 5", show_alert=True)
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    master_tg_id = data.get("master_tg_id")
    grade_msg_id = data.get("grade_message_id")

    if not order_id or not master_tg_id:
        await call.answer("❌ Ошибка сессии. Попробуйте снова.", show_alert=True)
        await state.clear()
        return

    # Обновляем заказ и ставим оценку
    success = await update_order(order_id=order_id, repair_status="close")
    if success:
        await add_grade(master_tg_id, grade)
        await add_grade(user_id, 5)  # Клиент тоже поднимает свой рейтинг на 5 принимая заказ

    # Показываем ТОЛЬКО alert
    await call.answer("Спасибо, что выбрали наше СТО! 🙏", show_alert=True)

    # УДАЛЯЕМ сообщение с оценкой
    if grade_msg_id:
        await call.bot.delete_message(call.message.chat.id, grade_msg_id)

    # Очищаем состояние
    await state.clear()


# ==============================
# МОИ ЗАПИСИ appointment
# ==============================
# показываем тип записи
@router.callback_query(F.data == "appointment")
async def start_booking(call: CallbackQuery):
    user_id = call.from_user.id

    # Проверяем, есть ли у пользователя активная запись
    appointments = await get_filter_appointments(tg_id_user=user_id)
    if appointments:
        # Берём первую
        appt = appointments[0]
        master_tg_id = appt["tg_id_master"]

        # Получаем данные мастера
        master_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name", "contact"])
        master_name = master_data["user_name"] if master_data else "—"
        master_contact = master_data["contact"] if master_data else "—"

        # Форматируем дату и время
        date_str = appt["appointment_date"].strftime("%d.%m.%Y")
        start_time = appt["appointment_time"].strftime("%H:%M")
        end_time = appt["end_time"].strftime("%H:%M")

        text = (
            f"🆔 <b>Запись №{appt['id']}</b>\n\n"
            f"👤 Имя мастера: {master_name}\n"
            f'📱 Телеграм: <a href="tg://user?id={master_tg_id}">{master_tg_id}</a>\n'
            f'📞 Сот. тел: <a href="tel:{master_contact}">{master_contact}</a>\n'
            f"📆 {date_str} | 🕗 {start_time}–{end_time}\n\n"
            "❗ У вас уже есть активная запись.\n"
            "Вы не можете создать новую, пока не завершите текущую."
        )

        await call.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=kb.master_menu_app([21, 22, 16, 18], master_tg_id)
        )

        await call.answer()
        return

    # Если ЗАПИСЕЙ НЕТ — показываем меню выбора услуги
    menu_text = (
        "📁 <b>ЗАПИСАТЬСЯ</b>\n\n"
        "Выберите тип необходимых работ, чтобы мы могли предложить вам подходящее время и назначить "
        "ответственного мастера.\n\n"
        "Нажмите на нужный вариант ниже 👇"
    )
    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.user_reg_repairs()
    )
    await call.answer()


SERVICE_NAMES = {
    "repair": "Ремонт",
    "maintenance": "Тех. обслуживание",
    "diagnostics": "Диагностика"
}


# Обработчик выбора услуги
@router.callback_query(F.data.startswith("service:"))
async def handle_service_choice(call: CallbackQuery, state: FSMContext):
    service_key = call.data.split(":", 1)[1]

    if service_key not in SERVICE_NAMES:
        await call.answer("❌ Недопустимый выбор", show_alert=True)
        return

    service_name = SERVICE_NAMES[service_key]
    user_id = call.from_user.id

    # Запрашиваем все нужные поля
    user_data = await get_user_dict(
        tg_id=user_id,
        fields=["user_name", "rating", "brand_auto", "model_auto", "year_auto", "contact", "total_km", "vin_number", "gos_num"]
    )

    if not user_data:
        logger.error(f"Не удалось загрузить данные для пользователя {user_id} при выборе услуги.")
        await call.message.answer("❌ Не удалось загрузить ваши данные. Обратитесь в поддержку.")
        await state.clear()
        return

    # Определяем обязательные поля (те, что не могут быть "-" или пустыми)
    required_fields = {
        "user_name": "Имя",
        "brand_auto": "Марка авто",
        "model_auto": "Модель авто",
        "year_auto": "Год выпуска",
        "contact": "Контактный номер",
        "gos_num": "Гос. номер"
    }

    # Проверяем, заполнены ли все обязательные поля (и не равны "-")
    missing_fields = []
    for field_key, field_label in required_fields.items():
        value = user_data.get(field_key, "").strip()
        if not value or value == "-":
            missing_fields.append(field_label)

    # Формируем базовый текст с данными
    preview_text = (
        f"📋 Ваши данные:\n\n"
        f"👤 Имя: {user_data.get('user_name', '-')}\n"
        f"📞 Сот.тел: {user_data.get('contact', '-')}\n"
        f"🚗 Марка авто: {user_data.get('brand_auto', '-')}\n"
        f"⚙️ Модель авто: {user_data.get('model_auto', '-')}\n"
        f"📆 Год выпуска: {user_data.get('year_auto', '-')}\n"
        f"🛞 Пробег: {user_data.get('total_km', '-')}\n"
        f"ℹ️ VIN: {user_data.get('vin_number', '-')}\n"
        f"🔢 Гос. номер: {user_data.get('gos_num', '-')}\n"
        f"🔧 Тип услуги: {service_name}\n\n"
    )

    if missing_fields:
        # Есть незаполненные поля НЕ ПОКАЗЫВАЕМ кнопку "Записаться"
        preview_text += (
            "❗ <b>Некоторые обязательные поля не заполнены:</b>\n"
            + "\n".join(f"• {field}" for field in missing_fields) +
            "\n\n"
            "🔹 Чтобы записаться на приём, сначала заполните профиль:\n"
            "<b>ЛИЧНЫЙ КАБИНЕТ → МОИ ДАННЫЕ → ИЗМЕНИТЬ ДАННЫЕ</b>"
        )
        # Показываем ТОЛЬКО кнопку "Назад"
        await call.message.answer(
            preview_text,
            parse_mode="HTML",
            reply_markup=kb.common_menu([6])
        )

    else:
        # Все поля заполнены — ПОКАЗЫВАЕМ подтверждение и кнопку "Записаться"
        preview_text += (
            "Если всё верно — нажмите «Записаться».\n"
            "Мастер свяжется с вами, чтобы уточнить удобное время."
        )

        await call.message.answer(
            preview_text,
            reply_markup=kb.common_menu([19, 6])  # "Записаться" + "Назад"
        )

        await state.update_data(
            chosen_service=service_name,
            user_data=user_data
        )
        await state.set_state(Booking.confirming_data)

    await call.answer()


# Обработчик "Подтвердить"
@router.callback_query(Booking.confirming_data, F.data == "confirm_booking")
async def confirm_booking(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    service_name = data.get("chosen_service")
    user_data = data.get("user_data")
    user_id = call.from_user.id

    if not user_data:
        await call.message.answer("❌ Ошибка при загрузке данных.")
        await state.clear()
        await call.answer()
        return

    contact = user_data["contact"]
    formatted_request = (
        "🔔 <b>Новая заявка на запись!</b>\n\n"
        f"👤 Имя: {user_data['user_name']}\n"
        f'📱 Телеграм ID: <a href="tg://user?id={user_id}">{user_id}</a>\n'
        f'📞 Сот.тел: <a href="tel:{contact}">{contact}</a>\n'
        f"⭐️ Рейтинг: {user_data['rating']}\n"
        f"🚗 Марка авто: {user_data['brand_auto']}\n"
        f"⚙️ Модель авто: {user_data['model_auto']}\n"
        f"📆 Год выпуска: {user_data['year_auto']}\n"
        f"🛞 Пробег км: {user_data['total_km']}\n"
        f"⚙️ Тип услуги: {service_name}\n\n"
        "Если готовы принять — свяжитесь с клиентом и уточните время."
    )

    # Получаем всех мастеров и админов с can_mess=True
    master_ids = await can_mess_true()  # возвращает список tg_id
    # Отправляем на все полученые tg_id
    for master_id in master_ids:
        await bot.send_message(
            chat_id=master_id,
            text=formatted_request,
            parse_mode="HTML",
            reply_markup=kb.master_menu_app([1, 2, 3, 9, 4, 5, 8], user_id=user_id)
        )

    await call.answer("✅ Заявка отправлена! Мастер свяжется с вами в ближайшее время.", show_alert=True)
    await state.clear()
    await call.message.delete()


# !!!!!!!!!!!!!!!!!!!!!!!!!
# ==============================
# ОТВЕТ ТЕКСТОМ КЛИЕНТА НА СООБЩЕНИЕ (НАПОМИНАНИЕ)
# ==============================

@router.callback_query(F.data.startswith("answer_app:"))
async def handle_client_text_response_only(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки «✏️ ВВЕСТИ ТЕКСТОМ» из формы напоминания о встрече.
    Формат: answer_app:<master_tg_id>
    Переводит клиента в состояние ввода текста.
    """
    parts = call.data.split(":", 1)  # ['answer_app', '123456789']
    if len(parts) != 2:
        await call.answer("❌ Некорректный формат данных.", show_alert=True)
        return

    print(int(parts[1]))

    try:
        master_tg_id = int(parts[1])
    except (ValueError, TypeError):
        await call.answer("❌ Некорректный ID мастера.", show_alert=True)
        return

    # Сохраняем данные для последующей отправки
    await state.update_data(
        master_tg_id=master_tg_id,
        chat_id=call.message.chat.id,
    )

    # Запрашиваем текстовое сообщение
    prompt_msg = await call.message.answer("✏️ Пожалуйста, введите ваше сообщение мастеру:")
    await state.set_state(AppointmentResponse.waiting_for_text)
    await state.update_data(message_ids=[prompt_msg.message_id])
    await call.answer()


@router.message(AppointmentResponse.waiting_for_text)
async def handle_custom_text_response(message: Message, state: FSMContext):
    """Принимает текст от клиента и отправляет его мастеру."""
    user_text = message.text
    if not user_text or not user_text.strip():
        error_msg = await message.answer("📝 Сообщение не может быть пустым. Пожалуйста, введите текст:")
        data = await state.get_data()
        message_ids = data.get("message_ids", [])
        message_ids.extend([message.message_id, error_msg.message_id])
        await state.update_data(message_ids=message_ids)
        return

    data = await state.get_data()
    master_tg_id = data.get("master_tg_id")
    chat_id = data.get("chat_id")
    message_ids = data.get("message_ids", [])

    # Добавляем сообщение пользователя
    message_ids.append(message.message_id)

    # Проверка и приведение master_tg_id
    try:
        master_tg_id = int(master_tg_id)
    except (ValueError, TypeError):
        await message.answer("❌ Ошибка: получатель не указан.")
        await state.clear()
        return

    # Формируем сообщение для мастера
    client_name = message.from_user.full_name
    client_tg_id = message.from_user.id
    msg_for_master = (
        f"🔔 СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ\n"
        f"👤 Имя: {client_name}\n"
        f"📱 Телеграм: {client_tg_id}\n\n"
        f"💬 {user_text}"
    )

    # Отправляем мастеру
    try:
        await bot.send_message(chat_id=master_tg_id,
                               text=msg_for_master,
                               reply_markup=kb.common_menu([4]))

    except TelegramAPIError as e:
        logger.error(f"Не удалось отправить сообщение от клиента {client_tg_id} мастеру {master_tg_id}: {e}")

    # Подтверждение клиенту
    success_msg = await message.answer("✅ Сообщение отправлено!")
    message_ids.append(success_msg.message_id)

    # Запускаем отложенное удаление всех сообщений (запрос + ввод + подтверждение)
    _ = asyncio.create_task(
        message_deleter(
            bot=bot,
            chat_id=chat_id,
            message_ids=message_ids
        )
    )

    await state.clear()


@router.callback_query(F.data.startswith("transfer_entry:"))
async def handle_transfer_entry_request(call: CallbackQuery):
    """
    Обрабатывает нажатие кнопки 'Перенести запись'.
    Отправляет мастеру быстрое сообщение от клиента.
    """
    parts = call.data.split(":", 1)
    if len(parts) != 2:
        await call.answer("❌ Некорректный формат данных.", show_alert=True)
        return

    try:
        master_tg_id = int(parts[1])
    except ValueError:
        await call.answer("❌ Некорректный ID мастера.", show_alert=True)
        return

    # Получаем данные клиента
    client_tg_id = call.from_user.id
    client_data = await get_user_dict(tg_id=client_tg_id, fields=["user_name"])
    client_name = client_data["user_name"]

    # Формируем сообщение для мастера
    message_for_master = (
        f"♻️ <b>Запрос на перенос записи</b>\n"
        f"👤 Имя: {client_name}\n"
        f"📱 tg_id: {client_tg_id}\n\n"
        f"«Здравствуйте, приехать не могу — нужно перенести запись!»"
    )

    # Отправляем мастеру
    try:
        await bot.send_message(chat_id=master_tg_id, text=message_for_master, parse_mode="HTML")
    except TelegramAPIError as e:
        logger.error(f"Не удалось отправить запрос на перенос записи {client_tg_id} мастеру {master_tg_id}: {e}")

    # Уведомляем клиента
    await call.answer("✅ Ваш запрос на перенос записи отправлен мастеру!", show_alert=True)

    # Удаляем сообщение с кнопкой (как в других обработчиках)
    try:
        await call.message.delete()
    except TelegramAPIError:
        pass


# ==============================
# ЗАДАТЬ ВОПРОС ВСЕМ МАСТЕРАМ
# ==============================
@router.callback_query(F.data == "send_message_all")
async def initiate_support_message_to_all(call: CallbackQuery, state: FSMContext):
    """
    Начинает процесс отправки сообщения всем активным мастерам (can_mess=True).
    """
    user_id = call.from_user.id
    user_data = await get_user_dict(tg_id=user_id, fields=["user_name"])
    if not user_data:
        await call.answer("❌ Ошибка: не удалось загрузить ваш профиль.", show_alert=True)
        return

    user_name = user_data["user_name"]
    menu_text = (
        "📁 <b>ЗАДАТЬ ВОПРОС</b>\n\n"
        f"{user_name}, опишите ваш вопрос максимально подробно — это поможет мастерам быстрее понять суть и дать "
        f"точный ответ.\n\n"
        "⚠️ Просим соблюдать уважительный тон и воздерживаться от нецензурной лексики.\n\n"
        "Введите ваше сообщение ниже в поле ввода чата и отправьте."
    )

    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.user_return_to_profile()
    )
    await state.set_state(Mess.mess_step)
    await call.answer()


@router.message(Mess.mess_step)
async def save_and_send_support_message_to_all(message: Message, state: FSMContext) -> None:
    """Отправляет сообщение всем мастерам с can_mess=True."""
    if not message.text or not message.text.strip():
        await message.answer("❌ Пожалуйста, введите непустое сообщение.")
        return

    user_tg_id = message.from_user.id
    user_data = await get_user_dict(
        tg_id=user_tg_id,
        fields=["user_name", "rating", "brand_auto", "model_auto", "year_auto", "contact", "total_km"]
    )

    if not user_data:
        await message.answer("❌ Ошибка профиля. Попробуйте позже.")
        await state.clear()
        return

    # Получаем всех мастеров, которым разрешено получать сообщения
    master_ids = await can_mess_true()

    contact = user_data['contact']
    formatted_message = (
        f"🔔 СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ\n\n"
        f"👤 Имя: {user_data['user_name']}\n"
        f"⭐️ Рейтинг: {user_data['rating']}\n"
        f"🚗 Марка авто: {user_data['brand_auto']}\n"
        f"⚙️ Модель авто: {user_data['model_auto']}\n"
        f"📆 Год выпуска: {user_data['year_auto']}\n"
        f"🛞 Пробег км: {user_data['total_km']}\n"
        f'📱 Телеграм ID: <a href="tg://user?id={user_tg_id}">{user_tg_id}</a>\n'
        f'📞 Контакт: <a href="tel:{contact}">{contact}</a>\n'
        f"💬 Сообщение:\n\n{message.text[:100]}"
    )

    # Отправка всем мастерам
    send_count = 0
    for master_id in master_ids:
        try:
            await bot.send_message(
                chat_id=master_id,
                text=formatted_message,
                parse_mode="HTML",
                reply_markup=kb.master_menu_app([1, 2, 3, 9, 4, 5, 8], user_id=user_tg_id)
            )
            send_count += 1
        except TelegramAPIError as e:
            logger.error(f"Не удалось отправить сообщение мастеру {master_id}: {e}")

    # Подтверждение клиенту
    if send_count == 0:
        success_msg = await message.answer("❌ Не удалось доставить сообщение.")
    else:
        success_msg = await message.answer("✅ Ваше сообщение отправлено!\nОжидайте ответа.")

    # Удаляем сообщения через отложенный вызов
    message_ids_to_delete = [message.message_id, success_msg.message_id]
    _ = asyncio.create_task(
        message_deleter(
            bot=bot,
            chat_id=message.chat.id,
            message_ids=message_ids_to_delete,
        )
    )
    await state.clear()


# ==============================
# ОСТАВИТЬ ОТЗЫВЫ ОБ СТО
# ==============================
@router.callback_query(F.data == "create_comment")
async def start_comment(call: CallbackQuery, state: FSMContext) -> None:
    """Начинает процесс оставления отзыва."""
    user_id = call.from_user.id
    user_data = await get_user_dict(tg_id=user_id, fields=["user_name"])
    user_name = user_data["user_name"]
    await state.update_data(user_name=user_name, user_id=user_id)

    menu_text = (
        "📁 <b>НАПИСАТЬ ОТЗЫВ</b>\n\n"
        f"{user_name}, поделитесь своим мнением об автосервисе — ваш отзыв поможет другим клиентам "
        "и позволит нам улучшать качество обслуживания.\n\n"
        "Напишите честно и по делу. Спасибо, что выбираете нас!"
    )

    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.user_return_to_profile()
    )
    await state.set_state(SendFeedback.send_text)
    await call.answer()


@router.message(SendFeedback.send_text)
async def save_comment_text(message: Message, state: FSMContext):
    message_ids_to_delete = [message.message_id]
    success = False
    response_msg = None

    # Проверка на пустой отзыв
    if not message.text or not message.text.strip():
        response_msg = await message.answer("❌ Отзыв не может быть пустым.")
        message_ids_to_delete.append(response_msg.message_id)
    else:
        # Получаем данные пользователя
        data = await state.get_data()
        user_id = data.get("user_id") or message.from_user.id
        user_name = data.get("user_name") or message.from_user.full_name
        review_text = message.text[:128]

        try:
            comment_id = await add_comment({
                "tg_id": user_id,
                "user_name": user_name,
                "text": review_text
            })

            success = bool(comment_id)

        except Exception:
            success = False

        if success:
            response_msg = await message.answer(
                "✅ Спасибо за ваш отзыв!\nОн будет отображаться для всех пользователей."
            )
        else:
            response_msg = await message.answer(
                "❌ Не удалось отправить отзыв. Попробуйте позже."
            )
        message_ids_to_delete.append(response_msg.message_id)

    # ЕДИНСТВЕННЫЙ вызов удаления
    _ = asyncio.create_task(
        message_deleter(
            bot=bot,
            chat_id=message.chat.id,
            message_ids=message_ids_to_delete
        )
    )

    await state.clear()


# ==============================
# МЕНЮ "МОИ ДАННЫЕ"
# ==============================
@router.callback_query(F.data == "login")
async def show_user_data(call: CallbackQuery) -> None:
    user_tg_id = call.from_user.id
    user_data = await get_user_dict(
        tg_id=user_tg_id,
        fields=["user_name", "brand_auto", "model_auto", "year_auto", "gos_num", "vin_number", "rating", "contact", "total_km"]
    )

    text = (
        "Ваши регистрационные данные и информация об авто:\n\n"
        f"📌 UID: {user_tg_id}\n"
        f"👤 Имя: {user_data['user_name']}\n"
        f"📞 Контактный номер: {user_data['contact']}\n"
        f"⭐ Рейтинг: {user_data['rating']}\n"
        f"🚗 Марка авто: {user_data['brand_auto']}\n"
        f"⚙️ Модель авто: {user_data['model_auto']}\n"
        f"🛞 Пробег км: {user_data['total_km']}\n"
        f"📆 Год выпуска: {user_data['year_auto']}\n"
        f"🔢 Гос. номер: {user_data['gos_num']}\n"
        f"🆔 VIN номер: {user_data['vin_number']}\n"
    )

    try:
        await call.message.edit_text(
            text=text,
            reply_markup=kb.user_edit_profile()
        )

    except Exception as e:
        # Логируем ошибку
        logger.error(f"Ошибка при загрузке данных пользователя {user_tg_id}: {e}", exc_info=True)
        await call.answer("⚠️ Не удалось загрузить данные.", show_alert=True)

    await call.answer()


# ==============================
# МАСТЕР. РЕДАКТИРОВАНИЕ ПРОФИЛЯ
# ==============================
@router.callback_query(F.data == "edit_menu")
async def edit_menu(call: CallbackQuery, state: FSMContext) -> None:
    """Открывает меню редактирования данных."""
    prompt_msg = await call.message.answer(
        "Выберите данные для изменения или дополнения:",
        reply_markup=kb.common_menu([17, 13, 14, 7, 15, 18, 16, 6])
    )
    # Новый список временных сообщений
    await state.update_data(edit_message_ids=[prompt_msg.message_id])
    await call.answer()


@router.callback_query(F.data.startswith("edit"))
async def start_edit_field(call: CallbackQuery, state: FSMContext) -> None:
    """Редактирование выбранного поля."""
    field_map = {
        "user_name": "Имя",
        "brand_auto": "Марка авто",
        "model_auto": "Модель авто",
        "year_auto": "Год выпуска",
        "gos_num": "Гос. номер",
        "vin_number": "VIN номер",
        "contact": "Контактный номер"
    }

    field_key = call.data.split(":")[1]
    await state.update_data(data_type=field_key)

    # Отправляем запрос на ввод
    input_msg = await call.message.edit_text(
        f"Введите {field_map[field_key]} (до 20 символов):",
        reply_markup=kb.common_menu([6])
    )

    # Добавляем новое сообщение в список
    data = await state.get_data()
    message_ids = data.get("edit_message_ids", [])
    message_ids.append(input_msg.message_id)
    await state.update_data(edit_message_ids=message_ids)

    await state.set_state(Edit.edit_login)
    await call.answer()


@router.message(Edit.edit_login)
async def save_edited_field(message: Message, state: FSMContext) -> None:
    """Сохраняет обновлённое значение поля и удаляет временные сообщения."""
    user_id = message.from_user.id
    data = await state.get_data()
    field_name = data.get("data_type")

    if not field_name:
        await message.answer("❌ Сессия устарела. Повторите попытку.")
        await state.clear()
        return

    # Сохраняем данные в БД
    new_value = message.text[:20]
    await update_user(user_id, field_name, new_value)

    # Отправляем подтверждение
    success_msg = await message.answer("Данные успешно обновлены!")

    # Собираем все сообщения для удаления:
    message_ids = data.get("edit_message_ids", [])
    message_ids.append(message.message_id)      # сообщение пользователя с текстом
    message_ids.append(success_msg.message_id)  # "Данные успешно обновлены!"

    # Удаляем дубликаты и None
    message_ids = list(set(msg_id for msg_id in message_ids if msg_id))

    # Запускаем автоматическое удаление
    if message_ids:
        _ = asyncio.create_task(
                message_deleter(
                    bot=bot,
                    chat_id=message.chat.id,
                    message_ids=message_ids
                )
            )

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
        "▫️Гарантируем качественный и оперативный ремонт."
    )
    await call.message.answer_photo(photo=info_img, caption=caption, reply_markup=kb.user_info_menu())


# ПОКАЗАТЬ ОТЗЫВЫ КЛИЕНТОВ
@router.callback_query(F.data == "comment")
async def show_comments(call: CallbackQuery):
    comments = await get_visible_comments(mode="user")

    if not comments:
        text = "Отзывов пока нет."
    else:
        # Собираем все отзывы в один текст
        parts = []
        for c in comments:
            date_str = c['date'].split('T')[0] if 'T' in c['date'] else c['date']
            parts.append(
                f"⭐ <b>{c['user_name']}</b>:\n{c['text']}\n\n📅 {date_str}"
            )
        text = "\n\n".join(parts)

    # Отправляем одним сообщением с кнопкой "Назад"
    await call.message.answer(
        text,
        parse_mode="HTML",
        reply_markup=kb.common_menu([6])
    )
    await call.answer()


# ПОКАЗАТЬ ПРАЙС ЦЕН
@router.callback_query(F.data == "price")
async def show_price_list(call: CallbackQuery) -> None:
    """Отправляет ориентировочный прайс из файла."""
    with open("info/price.txt", "r", encoding="utf-8") as f:
        text = f.read()
    await call.message.answer(text, reply_markup=kb.common_menu([6]))
    await call.answer()


# FAQ
@router.callback_query(F.data == "faq")
async def faq_service(call: CallbackQuery) -> None:
    with open("info/FAQ.txt", "r", encoding="utf-8") as f:
        text = f.read()

    await call.message.answer(text, reply_markup=kb.common_menu([6]))
    await call.answer()


# ПОКАЗАТЬ КОНТАКТНУЮ ИНФОРМАЦИЮ
@router.callback_query(F.data == "get_person")
async def show_contacts(call: CallbackQuery) -> None:
    """Отправляет контактную информацию и карту."""
    maps_img = FSInputFile("img/maps.jpg")
    caption = (
        f"🏢 <b>СТО ЗАО Рассвет:</b> {Config.OFFICE_ADDRESS}\n\n"
        f"📞 <b>Телефон:</b> {Config.SUPPORT_PHONE}\n\n"
        f"📧 <b>Email:</b> {Config.SUPPORT_EMAIL}"
    )

    await call.message.answer_photo(photo=maps_img, caption=caption, reply_markup=kb.location_menu())


# ЗАЯВКА НА РЕМОНТ ОТ КЛИЕНТА (ДЛЯ БЫСТРОГО ВЗАИМОДЕЙСТВИЯ С МАСТЕРОМ)
@router.callback_query(F.data.startswith("send_repair_req:"))
async def handle_send_repair_request(call: CallbackQuery):
    parts = call.data.split(":")
    if len(parts) != 2:
        await call.answer("❌ Ошибка запроса", show_alert=True)
        return

    user_tg_id = call.from_user.id

    try:
        master_tg_id = int(parts[1])
    except ValueError as e:
        logger.error(f"Некорректные данные {user_tg_id} мастеру: {e}")
        await call.answer("❌ Некорректные данные", show_alert=True)
        return

    # Проверяем, что клиент существует
    user_data = await get_user_dict(tg_id=user_tg_id)

    # Отправляем мастеру сообщение с кнопкой создания заказа
    await bot.send_message(
        chat_id=master_tg_id,
        text=(
            f"🔹 ЗАЯВКА НА РЕМОНТ 🔹\n\n"
            f"👤 Имя: {user_data['user_name']}\n"
            f"📱 Телеграм: {user_data['tg_id']}\n"
            f"📞 Сот. тел.: {user_data['contact']}\n"
            f"⭐️ Рейтинг: {user_data['rating']}\n"
            f"🚗 Марка авто: {user_data['brand_auto']} \n"
            f"⚙️ Модель авто: {user_data['model_auto']}\n"
            f"🛞 Пробег км: {user_data['total_km']} \n"
            f"📆 Год выпуска: {user_data['year_auto']}\n"
            f"ℹ️ VIN: {user_data['vin_number']}\n"
            f"🔢 Гос. номер: {user_data['gos_num']}\n\n"
            "Выберите тип работ или введите текстом:"
        ),
        reply_markup=kb.master_menu_app([10, 11, 12, 13, 14, 8], user_tg_id)
    )

    # Убираем кнопку у клиента
    await call.answer("✅ Заявка отправлена мастеру!", show_alert=True)


# СООБЩЕНИЕ МАСТЕРУ
@router.callback_query(F.data.startswith("send_answer:"))
async def handle_send_answer_button(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")

    if len(parts) != 2:
        await call.answer("❌ Неверный формат данных", show_alert=True)
        return

    master_tg_id = int(parts[1])

    # Сохраняем master_tg_id
    await state.update_data(
        target_master_id=master_tg_id,
        master_message_id=call.message.message_id  # сообщение от мастера
    )

    # Запрашиваем ответ
    sent = await call.message.answer("✍️ Введите ваш ответ:")
    await state.update_data(client_prompt_message_id=sent.message_id)  # "Введите ответ"

    await state.set_state(ClientReply.waiting_for_reply_text)
    await call.answer()


@router.message(ClientReply.waiting_for_reply_text)
async def process_client_reply(message: Message, state: FSMContext):
    data = await state.get_data()
    master_tg_id = data.get("target_master_id")
    if not master_tg_id:
        await message.answer("❌ Ошибка: получатель не указан.")
        await state.clear()
        return

    # Получаем данные клиента
    user_tg_id = message.from_user.id
    user_data = await get_user_dict(tg_id=user_tg_id, fields=["user_name", "brand_auto", "model_auto"])

    # Отправляем ответ мастеру
    try:
        await bot.send_message(
            chat_id=master_tg_id,
            text=(
                f"🔔 СООБЩЕНИЕ ОТ ПОЛЬЗОВАТЕЛЯ\n"
                f"👤 Имя: {user_data['user_name']}\n"
                f"📱 Телеграм: {user_tg_id}\n"
                f"💬 {message.text}"
            ),
            reply_markup=kb.common_menu([4])
        )

    except TelegramAPIError as e:
        logger.error(f"Не удалось отправить сообщение от клиента {user_tg_id} мастеру {master_tg_id}: {e}")

    # Собираем ID сообщений ДЛЯ УДАЛЕНИЯ в чате клиента
    message_ids_to_delete = []

    # Сообщение-запрос "Введите ваш ответ:"
    prompt_id = data.get("client_prompt_message_id")
    if prompt_id:
        message_ids_to_delete.append(prompt_id)

    # Сообщение клиента с ответом
    message_ids_to_delete.append(message.message_id)

    # Сообщение "Отправлено"
    clean_msg = await message.answer("✅ Ваше сообщение отправлено мастеру!")
    message_ids_to_delete.append(clean_msg.message_id)

    # Запускаем удаление
    _ = asyncio.create_task(
        message_deleter(bot=bot, chat_id=message.chat.id, message_ids=message_ids_to_delete)
    )

    await state.clear()


# HELP /help
@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    user_id = message.from_user.id
    role = await get_user_role(user_id)

    if role is None:
        # Пользователь не авторизован
        text = (
            "🔹 <b>О боте</b>\n"
            "AutoFixBot — цифровой помощник автосервиса. "
            "Он позволяет записываться на приём, оставлять заявки на ремонт, "
            "общаться с мастерами, просматривать прайс и отзывы, а также управлять "
            "своими данными — всё в одном Telegram-чате.\n\n"
            "ℹ️ <b>Как пользоваться ботом?</b>\n\n"
            "1️⃣ Для начала работы нажмите кнопку <b>«Авторизация»</b> — это обязательный шаг.\n\n"
            "2️⃣ После регистрации вы сможете:\n"
            "   • Записаться на приём к мастеру\n"
            "   • Оставить заявку на ремонт\n"
            "   • Написать в поддержку\n"
            "   • Оставить отзыв\n"
            "   • Управлять своими данными\n\n"
            "💬 Все действия выполняются через кнопки — ничего писать не нужно!"
        )

        await message.answer(text, reply_markup=kb.auth_menu())
    else:
        # Авторизованный пользователь — краткая справка + главное меню
        text = (
            "ℹ️ <b>Справка по боту</b>\n\n"
            "🔹 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n"
            "<b>Текущий ремонт</b> — отображает список ваших активных заявок на ремонт. "
            "Доступна информация о статусе заказа и контактные данные назначенного мастера.\n"
            "<b>Записаться</b> — позволяет подать заявку на приём, указав тип необходимых работ: "
            "диагностика, ремонт или техническое обслуживание.\n"
            "<b>Задать вопрос</b> — вы можете отправить любой технический или организационный вопрос. "
            "Запрос получат все мастера, и тот, кто может оказать помощь, свяжется с вами напрямую.\n"
            "<b>Написать отзыв</b> — оставьте свой отзыв о работе сервиса. "
            "Все авторизованные пользователи смогут ознакомиться с вашим мнением.\n"
            "<b>Мои данные</b> — просмотр и редактирование личной информации, включая данные об автомобиле.\n\n"
            "🔹 <b>ИНФОРМАЦИЯ</b>\n"
            "Раздел содержит подробное описание автосервиса, актуальные отзывы клиентов "
            "и ориентировочный прайс-лист на основные виды работ.\n\n"
            "🔹 <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>\n"
            "Ответы на наиболее распространённые вопросы, регулярно обновляемые администрацией сервиса.\n\n"
            "🔹 <b>КОНТАКТЫ И АДРЕС СТО</b>\n"
            "Контактная информация автосервиса, а также возможность посмотреть его местоположение на карте.\n\n"
            "💡 Все действия выполняются с помощью кнопок. Просто следуйте подсказкам бота!"
        )

        # Определяем меню по роли
        if role == "admin":
            markup = kb.admin_menu()
        elif role == "master":
            markup = kb.master_menu()
        else:  # user
            markup = kb.user_main_menu()

        await message.answer(text, reply_markup=markup)


@router.callback_query(F.data == "cancel")
async def cancel_booking(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer()


