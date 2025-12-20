from aiogram.types import CallbackQuery, Message
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.requests import (get_user_dict, get_available_hours, create_appointment, get_active_order_id, add_order,
                               get_orders_by_user, update_order)
from bot import bot
from keybords import keybords as kb
from datetime import date, timedelta


# Создаём отдельный роутер для обработки действий персонала (админов и мастеров)
router = Router()


# Состояния FSM, необходимые для многошаговых сценариев персонала
class AdminReply(StatesGroup):
    waiting_for_text = State()  # ввод текста ответа


class AppointmentStates(StatesGroup):
    choosing_option = State()  # меню: сегодня / выбрать день
    choosing_day = State()     # календарь (пока не используется полностью)
    choosing_time = State()    # выбор начала времяни
    choosing_duration = State()  # выбор окончания времени приёма


class RepairOrderStates(StatesGroup):
    entering_description = State()  # ожидание текстового описания
    confirming = State()            # ожидание подтверждения


class MasterEditStates(StatesGroup):
    choosing_field = State()   # выбор поля
    editing_field = State()    # ввод значения


class MasterOrderActions(StatesGroup):
    choosing_action = State()   # выбор: быстрый ответ или текст
    waiting_for_message = State()  # ожидание текста от мастера


REPAIR_STATUS_DISPLAY = {
    "in_work": "В работе",
    "wait": "Ожидание",
    "close": "Закрыт"
}


# ===========================
# ========= МАСТЕР ==========
# ===========================

# ЛИЧНЫЙ КАБИНЕТ МАСТЕРА"

# ВЫБОР "ТЕКУЩИЕ ЗАКАЗЫ"
@router.callback_query(F.data == "my_actions_orders")
async def master_current_orders(call: CallbackQuery, state: FSMContext):
    master_id = call.from_user.id
    # Получаем активные заказы, где пользователь — мастер
    orders = await get_orders_by_user(tg_id_master=master_id, active=True)

    if not orders:
        await call.message.answer("❌ Нет активных заказов. ❌")
    else:
        for order in orders:
            date_str = order.get("date", "не указана")
            if isinstance(date_str, str) and "T" in date_str:
                date_str = date_str.split("T")[0]

            status_raw = order['repair_status']
            status_display = REPAIR_STATUS_DISPLAY.get(status_raw, status_raw)
            order_id = order['id']
            user_contact = order['user_contact']
            tg_id_user = order['tg_id_user']

            text = (
                f"🆔 ID заказа: {order_id}\n\n"
                f"👤 Клиент: {order['user_name']}\n"
                f'📱 Телеграм ID: <a href="tg://user?id={tg_id_user}">{tg_id_user}</a>\n'
                f'📞 Сот.тел: <a href="tel:{user_contact}">{user_contact}</a>\n'
                f"🚗 Марка авто: {order.get('brand_auto') or '—'}\n"
                f"📆 Год выпуска: {order.get('year_auto') or '—'}\n"
                f"ℹ️ VIN: {order.get('vin_number') or '—'}\n"
                f"🔢 Гос. номер: {order.get('gos_num') or '—'}\n"
                f"🔧 Статус: {status_display}\n"
                f"📝 Описание:\n{order.get('description') or '—'}\n\n"
                f"📅 Дата создания: {date_str}"
            )

            await call.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.master_order_action_menu([1, 2, 3, 4, 5, 6, 8], order_id, tg_id_user)
            )

    await call.answer()


# ВЫБОР ВЫПОЛНЕНО
# Роутер: обрабатывает complied_order:order_id:client_tg_id
@router.callback_query(F.data.startswith("complied_order:"))
async def handle_complied_order(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("❌ Неверный формат", show_alert=True)
        return

    try:
        order_id = int(parts[1])
        client_tg_id = int(parts[2])
    except ValueError:
        await call.answer("❌ Некорректные ID", show_alert=True)
        return

    master_tg_id = call.from_user.id

    # Сохраняем данные в состоянии
    await state.update_data(
        order_id=order_id,
        client_tg_id=client_tg_id,
        master_tg_id=master_tg_id
    )

    # Показываем выбор действия
    await call.message.answer(
        f"ID заказа {order_id}\n"
        f" Выберите действие:",
        reply_markup=kb.quick_action_menu()
    )
    await state.set_state(MasterOrderActions.choosing_action)
    await call.answer()


# ВЫБОР: "Можете забирать"
@router.callback_query(MasterOrderActions.choosing_action, F.data == "quick:answer")
async def send_quick_pickup(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_tg_id = data["client_tg_id"]
    order_id = data["order_id"]
    master_tg_id = data["master_tg_id"]

    # Получаем имя мастера
    master_name, = await get_user_dict(master_tg_id, ("user_name",))

    # Обновляем заказ: статус = wait, complied = True
    await update_order(order_id, "wait", complied=True)

    # Отправляем клиенту
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"✅ Сообщение от {master_name}:\n\n"
             f"«Можете принимать работу и забирать автомобиль!»\n\n",
        reply_markup=kb.get_accept_work_keyboard(order_id, master_tg_id)  # Кнопка "Принять работу"
    )

    await call.message.answer("✅ Сообщение «Можете забирать» отправлено клиенту.")
    await state.clear()
    await call.message.delete()
    await call.answer()


# ВЫБОР "Отправить сообщение"
@router.callback_query(MasterOrderActions.choosing_action, F.data == "quick:text")
async def request_custom_message(call: CallbackQuery, state: FSMContext):
    await call.message.answer("✍️ Введите сообщение для клиента:")
    await state.set_state(MasterOrderActions.waiting_for_message)
    await call.answer()


# РОУТЕР ловит текст от мастера и отправляет клиенту
@router.message(MasterOrderActions.waiting_for_message)
async def send_custom_message_to_client(message: Message, state: FSMContext):
    data = await state.get_data()
    client_tg_id = data["client_tg_id"]
    order_id = data["order_id"]
    master_tg_id = data["master_tg_id"]

    master_name, = await get_user_dict(master_tg_id, ("user_name",))

    # Обновляем статус заказа
    await update_order(order_id, "wait", complied=True)

    # Отправляем сообщение клиенту
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"✅ Сообщение от {master_name}:\n\n"
             f"{message.text}\n",
        reply_markup=kb.get_accept_work_keyboard(order_id, master_tg_id)  # Кнопка "Принять работу"
    )

    await message.answer("✅ Ваше сообщение отправлено клиенту.")
    await state.clear()


# ===========================
# ВЗАИМОДЕЙСТВИЕ С КЛИЕНТОМ
# ===========================


# === ОЖИДАНИЕ ===
@router.callback_query(F.data.startswith("await:"))
async def handle_await_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])

    response_text = "В данный момент занят. Отвечу, как только освобожусь!"
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Ожидание» отправлен пользователю.")
    await call.answer()


# === ОТКАЗ ===
@router.callback_query(F.data.startswith("refuse:"))
async def handle_refuse_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    response_text = f"К сожалению, не сможем помочь с этой проблемой."
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Отказ» отправлен пользователю.")
    await call.answer()


# === ЗВОНИТЕ ===
@router.callback_query(F.data.startswith("call:"))
async def handle_call_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    master_tg_id = call.from_user.id

    master_name, master_contact = await get_user_dict(master_tg_id, ("user_name", "contact"))

    response_text = (f'Звоните по номеру!\n'
                     f'Имя: {master_name}\n'
                     f'Сот. тел.: <a href="tel:{master_contact}">{master_contact}</a>')

    await bot.send_message(chat_id=user_id, text=response_text, parse_mode="HTML")
    await call.message.answer("✅ Ответ «Звоните» отправлен пользователю.")
    await call.answer()


# === НАЗНАЧИТЬ ВРЕМЯ — вход в FSM ===
@router.callback_query(F.data.startswith("set_time:"))
async def handle_set_time_action(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":", 1)
    if len(parts) != 2:
        await call.answer("Неверный формат", show_alert=True)
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await call.answer("Некорректный ID", show_alert=True)
        return

    user_name, = await get_user_dict(user_id, ("user_name",))
    await state.update_data(target_user_id=user_id, user_name=user_name)

    await call.message.answer(
        "Выберите вариант записи:",
        reply_markup=kb.staff_menu([6, 7, 8], user_id=user_id)
    )
    await state.set_state(AppointmentStates.choosing_option)
    await call.answer()


@router.callback_query(AppointmentStates.choosing_option, F.data.startswith("today:"))
async def handle_today_selection(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":", 1)
    if len(parts) != 2:
        await call.answer("Неверный формат", show_alert=True)
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await call.answer("Некорректный ID", show_alert=True)
        return

    today = date.today()
    free_hours = await get_available_hours(today)  # ВОЗВРАЩАЕТ СВОБОДНЫЕ часы

    if not free_hours:  # Пустой set - нет свободного времени
        await call.message.edit_text(
            "❌ В этот день нет свободного времени для записи.",
            reply_markup=kb.staff_menu([8], user_id=user_id)
        )

        await call.answer()
        return

    # Сохраняем данные
    await state.update_data(
        target_user_id=user_id,
        selected_date=today
    )

    # Показываем выбор времени
    await call.message.edit_text(
        "На какое время записать?",
        reply_markup=kb.generate_time_buttons(free_hours, user_id)
    )
    await state.set_state(AppointmentStates.choosing_time)
    await call.answer()


# === "ВЫБРАТЬ ДЕНЬ" ===
@router.callback_query(AppointmentStates.choosing_option, F.data.startswith("next_days:"))
async def handle_next_days_selection(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":", 1)
    if len(parts) != 2:
        await call.answer("❌ Неверный формат", show_alert=True)
        return

    try:
        user_id = int(parts[1])
    except ValueError:
        await call.answer("❌ Некорректный ID", show_alert=True)
        return

    today = date.today()
    year, month = today.year, today.month

    # Получаем busy_days для текущего месяца
    first_day = date(year, month, 1)
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    last_day = date(next_year, next_month, 1)
    days_in_month = (last_day - first_day).days

    busy_days = set()
    for day in range(1, days_in_month + 1):
        check_date = date(year, month, day)
        if check_date < today:
            continue
        free_hours = await get_available_hours(check_date)
        if not free_hours:
            busy_days.add(day)

    await state.update_data(target_user_id=user_id)

    await call.message.edit_text(
        "Выберите день:",
        reply_markup=kb.generate_calendar_buttons(user_id, year, month, busy_days)
    )
    await state.set_state(AppointmentStates.choosing_day)
    await call.answer()


# === ВЫБОР ДНЯ В КАЛЕНДАРЕ ===
@router.callback_query(AppointmentStates.choosing_day, F.data.startswith("calendar_day:"))
async def handle_calendar_day(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) != 5:  # calendar_day:year:month:day:user_id
        await call.answer("❌ Ошибка формата", show_alert=True)
        return

    try:
        year = int(parts[1])
        month = int(parts[2])
        day = int(parts[3])
        user_id = int(parts[4])
    except ValueError:
        await call.answer("❌ Некорректные данные", show_alert=True)
        return

    try:
        selected_date = date(year, month, day)
    except ValueError:
        await call.answer("❌ Недопустимая дата", show_alert=True)
        return

    today = date.today()
    if selected_date < today:
        await call.answer("❌ Нельзя записаться в прошлое", show_alert=True)
        return

    free_hours = await get_available_hours(selected_date)

    if not free_hours:
        await call.message.edit_text(
            f"❌ На {selected_date.strftime('%d.%m.%Y')} нет свободного времени.",
            reply_markup=kb.staff_menu([8], user_id=user_id)
        )
        await call.answer()
        return

    await state.update_data(
        target_user_id=user_id,
        selected_date=selected_date
    )

    await call.message.edit_text(
        f"На какое время записать ({selected_date.strftime('%d.%m.%Y')})?",
        reply_markup=kb.generate_time_buttons(free_hours, user_id)
    )
    await state.set_state(AppointmentStates.choosing_time)
    await call.answer()


# === НАВИГАЦИЯ ПО МЕСЯЦАМ ===
@router.callback_query(AppointmentStates.choosing_day, F.data.startswith("calendar_nav:"))
async def handle_calendar_navigation(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("❌ Ошибка навигации", show_alert=True)
        return

    try:
        year = int(parts[1])
        month = int(parts[2])
        user_id = int(parts[3])
    except ValueError:
        await call.answer("❌ Некорректные данные", show_alert=True)
        return

    # Проверим, не ушли ли слишком далеко в прошлое/будущее
    today = date.today()
    target_date = date(year, month, 1)
    if target_date < today.replace(day=1) - timedelta(days=30):
        await call.answer("❌ Навигация в далёкое прошлое запрещена", show_alert=True)
        return
    if target_date > today.replace(year=today.year + 1):
        await call.answer("❌ Навигация далее одного года запрещена", show_alert=True)
        return

    # Получаем busy_days для выбранного месяца
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1

    first_day = date(year, month, 1)
    last_day = date(next_year, next_month, 1)
    days_in_month = (last_day - first_day).days

    busy_days = set()
    for day in range(1, days_in_month + 1):
        check_date = date(year, month, day)
        # Не проверяем прошлое — в календаре оно и так неактивно
        free_hours = await get_available_hours(check_date)
        if not free_hours:
            busy_days.add(day)

    await call.message.edit_text(
        "Выберите день:",
        reply_markup=kb.generate_calendar_buttons(user_id, year, month, busy_days)
    )
    await call.answer()


# === ВЫБОР ВРЕМЕНИ И ПЕРЕХОД К ВЫБОРУ ДЛИТЕЛЬНОСТИ ===
@router.callback_query(AppointmentStates.choosing_time, F.data.startswith("appoint:"))
async def handle_appointment_time(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("Ошибка формата", show_alert=True)
        await state.clear()
        return

    try:
        start_hour = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        await call.answer("Некорректные данные", show_alert=True)
        await state.clear()
        return

    data = await state.get_data()
    selected_date = data.get("selected_date")
    target_user_id = data.get("target_user_id")

    if selected_date is None or target_user_id != user_id:
        await call.answer("Ошибка состояния", show_alert=True)
        await state.clear()
        return

    # Сохраняем начало
    await state.update_data(start_hour=start_hour)

    # Показываем выбор длительности
    await call.message.edit_text(
        "На какую длительность записать?",
        reply_markup=kb.generate_duration_buttons(user_id)
    )
    await state.set_state(AppointmentStates.choosing_duration)
    await call.answer()


# === ВЫБОР ДЛИТЕЛЬНОСТИ ===
@router.callback_query(AppointmentStates.choosing_duration, F.data.startswith("duration:"))
async def handle_duration_selection(call: CallbackQuery, state: FSMContext):
    parts = call.data.split(":")

    if len(parts) != 3:
        await call.answer("Ошибка формата", show_alert=True)
        await state.clear()
        return

    try:
        duration_hours = float(parts[1])
        user_id = int(parts[2])
    except ValueError:
        await call.answer("Некорректные данные", show_alert=True)
        await state.clear()
        return

    data = await state.get_data()
    selected_date = data.get("selected_date")
    target_user_id = data.get("target_user_id")
    start_hour = data.get("start_hour")

    if not all([selected_date, target_user_id == user_id, start_hour is not None]):
        await call.answer("Ошибка состояния", show_alert=True)
        await state.clear()
        return

    # Рассчитываем конец
    end_hour = start_hour + duration_hours

    # Получаем tg_id мастера
    master_id = call.message.chat.id

    # Записываем в БД
    await create_appointment(user_id, master_id, selected_date, start_hour, end_hour)

    # Отправляем пользователю
    start_str = f"{int(start_hour)}:{'30' if start_hour % 1 else '00'}"
    end_str = f"{int(end_hour)}:{'30' if end_hour % 1 else '00'}"

    # Присваиваем переменным полученое имя и номер тел.
    master_name, tel = await get_user_dict(tg_id=master_id, fields=('user_name', 'contact'))

    await bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ Запись подтверждена!\n"
            f"👤 Имя мастера: {master_name}\n"
            f"📱 Телеграм: {master_id}\n"
            f"📞 Сот. тел.: {tel}\n"
            f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"🕒 Время: {start_str}–{end_str}\n\n"
            f"После осмотра вашего авто, по просьбе мастера вы можете нажать на кнопку расположенную ниже."
        ),
        reply_markup=kb.action_buttons_orders_menu([7], user_id, master_id)
    )

    await call.message.delete()
    await call.message.answer("✅ Форма отправлена пользователю!")
    await state.clear()
    await call.answer()


# === КНОПКА "НАЗАД" — ВЫХОД ИЗ FSM ===
@router.callback_query(F.data == "delete_msg")
async def handle_delete_msg(call: CallbackQuery, state: FSMContext):

    await call.message.delete()
    await state.clear()
    await call.answer()


# === СООБЩЕНИЕ НА ВОПРОС ПОЛЬЗОВАТЕЛЯ (state 1) ===
# Извлекаем tg_id пользователя из callback_data и переходит в режим ожидания текста ответа.
@router.callback_query(F.data.startswith("replay_mess:"))
async def custom_reply_to_user(call: CallbackQuery, state: FSMContext):
    # Разбиваем callback_data вида "replay_mess:123456789" на части
    parts = call.data.split(":")
    # Проверяем корректность формата
    if len(parts) != 2:
        await call.answer("Ошибка данных", show_alert=True)
        return

    # Извлекаем tg_id целевого пользователя
    user_id = int(parts[1])
    await state.update_data(target_user_id=user_id)
    # Запрашиваем у админа текст ответа
    await call.message.answer("Введите сообщение и отправьте!")
    # Устанавливаем состояние ожидания текста
    await state.set_state(AdminReply.waiting_for_text)


# === СООБЩЕНИЕ НА ВОПРОС ПОЛЬЗОВАТЕЛЯ (state 2) ===
# После того как админ ввёл текст, бот получает его, находит имя пользователя в БД
# и отправляет персонализированное сообщение пользователю.
@router.message(AdminReply.waiting_for_text)
async def send_custom_reply(message: Message, state: FSMContext):
    # Получаем сохранённый tg_id из состояния мастера
    data = await state.get_data()
    user_id = data.get("target_user_id")
    master_id = message.chat.id

    # Безопасная проверка: если ID отсутствует — выходим
    if not user_id:
        await message.answer("Ошибка: пользователь не найден.")
        await state.clear()
        return

    # Запрашиваем имя пользователя из базы данных
    master_name, = await get_user_dict(master_id, ("user_name",))

    # Отправляем сообщение пользователю с кнопкой для обратной связи
    await bot.send_message(
        chat_id=user_id,
        text=f"{master_name}:\n{message.text}",
        reply_markup=kb.action_buttons_orders_menu([8], user_id, master_id)
    )

    # Подтверждаем, что сообщение отправлено
    await message.answer("✅ Сообщение отправлено пользователю.")
    # Очищаем состояние
    await state.clear()


# === СОЗДАНИЕ ЗАКАЗА ===

# Типы работ для быстрого выбора
TYPE_DESCRIPTIONS = {
    "diagnostic": "Диагностика",
    "repair": "Ремонт",
    "diag_repair": "Диагностика и ремонт",
    "to": "Техническое обслуживание"
}


@router.callback_query(F.data.startswith("repair_type:"))
async def start_repair_order_process(call: CallbackQuery, state: FSMContext):
    """
    Запускает FSM создания заказа после выбора типа работ.
    Если выбран "ВВЕСТИ ТЕКСТОМ" — переходит к вводу описания.
    Иначе — подставляет быстрое описание и показывает кнопку создания заказа.
    """
    parts = call.data.split(":")
    if len(parts) != 4:
        await call.answer("❌ Некорректный формат данных", show_alert=True)
        return

    action = parts[1]
    client_tg_id = int(parts[2])
    master_tg_id = int(parts[3])

    await state.update_data(
        client_tg_id=client_tg_id,
        master_tg_id=master_tg_id
    )

    if action == "custom":
        await call.message.answer("Введите описание работ (до 100 символов):")
        await state.set_state(RepairOrderStates.entering_description)
    else:
        description = TYPE_DESCRIPTIONS.get(action, "Ремонт")
        await state.update_data(description=description)
        await call.message.answer(
            f"Описание работ: {description}",
            reply_markup=kb.action_buttons_orders_menu([6, 9], client_tg_id, master_tg_id)
        )
        await state.set_state(RepairOrderStates.confirming)

    await call.answer()


@router.message(RepairOrderStates.entering_description)
async def handle_custom_description(message: Message, state: FSMContext):
    """
    Обрабатывает ввод описания работ от мастера.
    Проверяет длину (макс. 100 символов) и показывает кнопку создания заказа.
    """
    text = message.text
    if not text:
        await message.answer("Пожалуйста, введите описание.")
        return
    if len(text) > 100:
        await message.answer("Описание не должно превышать 100 символов. Попробуйте снова:")
        return

    data = await state.get_data()
    client_tg_id = data["client_tg_id"]
    master_tg_id = data["master_tg_id"]

    await state.update_data(description=text)
    await message.answer(
        f"Описание работ: {text}",
        reply_markup=kb.action_buttons_orders_menu([6, 9], client_tg_id, master_tg_id),
    )
    await state.set_state(RepairOrderStates.confirming)


@router.callback_query(RepairOrderStates.confirming, F.data.startswith("create_order:"))
async def create_repair_order(call: CallbackQuery, state: FSMContext):
    """
    Создаёт заказ в базе данных после подтверждения мастера.
    Проверяет существование пользователей и отсутствие активного заказа.
    """
    parts = call.data.split(":")
    if len(parts) != 3:
        return

    try:
        client_tg_id = int(parts[1])
        master_tg_id = int(parts[2])
    except ValueError:
        return

    data = await state.get_data()
    description = data.get("description", "Без описания")

    client_data = await get_user_dict(client_tg_id)
    master_data = await get_user_dict(master_tg_id)
    if not client_data or not master_data:
        await call.answer("❌ Пользователь не найден", show_alert=True)
        await state.clear()
        return

    active_order_id = await get_active_order_id(client_tg_id, master_tg_id)
    if active_order_id is not None:
        await call.answer(f"❌ Уже есть активная заявка №{active_order_id}!", show_alert=True)
        await state.clear()
        return

    order_data = {
        "tg_id_user": client_tg_id,
        "tg_id_master": master_tg_id,
        "user_name": client_data["user_name"],
        "user_contact": client_data["contact"],
        "master_name": master_data["user_name"],
        "master_contact": master_data["contact"],
        "repair_status": "in_work",
        "complied": False,
        "description": description,
        "brand_auto": client_data["brand_auto"],
        "gos_num": client_data["gos_num"],
        "year_auto": client_data["year_auto"],
        "vin_number": client_data["vin_number"]
    }
    await add_order(order_data)

    # Отправляем сообщение пользователю с подтверждением о принятом автомобиле в работу
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"✅ Ваш автомобиль принят в ремонт!\n\n"
             f"👤 Имя клиента: {client_data['user_name']}\n"
             f"📞 Сот. тел.: {client_data['contact']}\n"
             f"🚗 Марка авто: {client_data['brand_auto']}\n"
             f"📆 Год: {client_data['year_auto']}\n"
             f"🔢 Гос номер: {client_data['gos_num']}\n"
             f"👤 Имя мастера: {master_data['user_name']}\n"
             f"📞 Сот. тел.: {master_data['contact']}\n"
             f"📄 Описание работ: {description}\n"
             f"🔧 Статус: 'В работе'\n\n"
    )

    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("✅ Вы приняли в ремонт автомобиль. Заявка на ремонт создана!")
    await state.clear()
    await call.answer()


# РОУТЕР слушает кнопку назад, очищает состояния и удаляет сообщение
@router.callback_query(F.data == "cancel")
async def cancel_quick_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer()

