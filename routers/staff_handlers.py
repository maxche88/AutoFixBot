from aiogram.types import CallbackQuery, Message
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.requests import get_user_dict, get_available_hours, create_appointment
from func.func_bot import get_greeting
from config import bot
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


# === 1. ОЖИДАНИЕ ===
@router.callback_query(F.data.startswith("await:"))
async def handle_await_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    user_dict = await get_user_dict(user_id, ("user_name",))
    user_name = user_dict[0] if user_dict else "Пользователь"
    greeting = await get_greeting()

    response_text = f"{greeting} {user_name}!\n\nВ данный момент занят. Отвечу, как только освобожусь!"
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Ожидание» отправлен пользователю.")
    await call.answer()


# === 2. ОТКАЗ ===
@router.callback_query(F.data.startswith("refuse:"))
async def handle_refuse_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    user_dict = await get_user_dict(user_id, ("user_name",))
    user_name = user_dict[0] if user_dict else "Пользователь"
    greeting = await get_greeting()

    response_text = f"{greeting} {user_name}!\n\nК сожалению, не сможем помочь с этой проблемой."
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Отказ» отправлен пользователю.")
    await call.answer()


# === 3. ЗВОНИТЕ ===
@router.callback_query(F.data.startswith("call:"))
async def handle_call_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    user_dict = await get_user_dict(user_id, ("user_name",))
    user_name = user_dict[0] if user_dict else "Пользователь"
    greeting = await get_greeting()

    response_text = f"{greeting} {user_name}!\n\nЗвоните по номеру: +79999999999"
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Звоните» отправлен пользователю.")
    await call.answer()


# === 1. НАЗНАЧИТЬ ВРЕМЯ — вход в FSM ===
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

    user_dict = await get_user_dict(user_id, ("user_name",))
    user_name = user_dict[0] if user_dict else "Пользователь"
    await state.update_data(target_user_id=user_id, user_name=user_name)

    await call.message.answer(
        "Выберите вариант записи:",
        reply_markup=kb.mess_menu([6, 7, 8], user_id=user_id)
    )
    await state.set_state(AppointmentStates.choosing_option)
    await call.answer()


# === 2. ВЫБОР "НА СЕГОДНЯ" ===
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
            reply_markup=kb.mess_menu([8], user_id=user_id)
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


# === 3. "ВЫБРАТЬ ДЕНЬ" ===
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


# === 4. ВЫБОР ДНЯ В КАЛЕНДАРЕ ===
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
            reply_markup=kb.mess_menu([8], user_id=user_id)
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

    # Проверим, не ушли ли слишком далеко в прошлое/будущее (опционально)
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


# === 5. ВЫБОР ВРЕМЕНИ И ПЕРЕХОД К ВЫБОРУ ДЛИТЕЛЬНОСТИ ===
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


# === 6. ВЫБОР ДЛИТЕЛЬНОСТИ → ЗАПИСЬ В БД ===
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

    # Записываем в БД
    await create_appointment(user_id, selected_date, start_hour, end_hour)

    # Отправляем пользователю
    start_str = f"{int(start_hour)}:{'30' if start_hour % 1 else '00'}"
    end_str = f"{int(end_hour)}:{'30' if end_hour % 1 else '00'}"

    await bot.send_message(
        chat_id=user_id,
        text=f"✅ Запись подтверждена!\n"
             f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
             f"🕒 Время: {start_str}–{end_str}"
    )

    try:
        await call.message.delete()
    except:
        pass

    await call.message.answer("✅ Запись отправлена пользователю!")
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
    # Проверяем корректность формата (ожидаем ровно 2 части)
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
    # Получаем сохранённый tg_id из состояния админа
    data = await state.get_data()
    user_id = data.get("target_user_id")

    # Безопасная проверка: если ID отсутствует — выходим
    if not user_id:
        await message.answer("Ошибка: пользователь не найден.")
        await state.clear()
        return

    # Запрашиваем имя пользователя из базы данных
    user_dict = await get_user_dict(user_id, ("user_name",))
    user_name = user_dict[0] if user_dict else "Пользователь"

    # Генерируем персональное приветствие
    greeting = await get_greeting()

    # Отправляем сообщение пользователю
    await bot.send_message(
        chat_id=user_id,
        text=f"{greeting} {user_name}\n\n{message.text}"
    )

    # Подтверждаем, что сообщение отправлено
    await message.answer("✅ Сообщение отправлено пользователю.")
    # Очищаем состояние
    await state.clear()






