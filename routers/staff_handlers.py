from aiogram.types import CallbackQuery, Message
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.requests import get_user_dict, get_occupied_hours, create_appointment
from func.func_bot import get_greeting
from config import bot
from keybords import keybords as kb
from datetime import date

# Создаём отдельный роутер для обработки действий персонала (админов и мастеров)
router = Router()


# Состояния FSM, необходимые для многошаговых сценариев персонала
class AdminReply(StatesGroup):
    waiting_for_text = State()  # ввод текста ответа


class AdminAppointment(StatesGroup):
    selecting_day = State()     # выбор дня
    # selecting_time = State()


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
# и отправляем персонализированное сообщение целевому пользователю.
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


# === НАЗНАЧИТЬ ЗАПИСЬ ===
# Обрабатывает нажатия на кнопки быстрых ответов ("Ожидание", "Отказ", "Звоните", "Назначить время").
# Все данные (действие и tg_id пользователя) передаются через callback_data.
@router.callback_query(F.data.startswith("mess:"))
async def process_support_action(call: CallbackQuery):
    # Разбираем callback_data вида "mess:action:123456789"
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("Неверный формат", show_alert=True)
        return

    # Извлекаем действие и ID пользователя
    action, user_id_str = parts[1], parts[2]
    try:
        user_id = int(user_id_str)
    except ValueError:
        await call.answer("Некорректный ID", show_alert=True)
        return

    # Получаем имя пользователя из БД для персонализации
    user_dict = await get_user_dict(user_id, ("user_name",))
    user_name = user_dict[0] if user_dict else "Пользователь"
    greeting = await get_greeting()

    # Словарь готовых шаблонов ответов
    responses = {
        "await": f"{greeting} {user_name}!\n\nВ данный момент занят. Отвечу, как только освобожусь!",
        "refuse": f"{greeting} {user_name}!\n\nК сожалению, не сможем помочь с этой проблемой.",
        "call": f"{greeting} {user_name}!\n\nЗвоните по номеру: +79999999999",
    }

    # Если действие — один из предопределённых ответов
    if action in responses:
        await bot.send_message(chat_id=user_id, text=responses[action])
        await call.message.answer("✅ Ответ отправлен пользователю.")

    # Если действие — назначение времени записи
    elif action == "time":
        # Показываем админу выбор: сегодня или другой день
        await call.message.answer(
            "Выберите вариант записи:",
            reply_markup=kb.mess_menu([6, 7], user_id=user_id)  # передаём user_id в клавиатуру
        )
    else:
        await call.answer("Неизвестное действие", show_alert=True)


# === ВЫБОР ДНЯ ЗАПИСИ ===
# Реагирует на нажатие кнопок "НА СЕГОДНЯ" или "ВЫБРАТЬ ДЕНЬ".
# Подготавливает следующий шаг: выбор конкретного времени.
@router.callback_query(F.data.startswith("time:"))
async def handle_time_selection(call: CallbackQuery, state: FSMContext):
    # Парсим callback_data: "time:today:123456789" или "time:next_days:123456789"
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("Ошибка формата", show_alert=True)
        return

    action, user_id_str = parts[1], parts[2]
    try:
        user_id = int(user_id_str)
    except ValueError:
        await call.answer("Некорректный ID", show_alert=True)
        return

    # Сценарий 1: запись на сегодня
    if action == "today":
        today = date.today()
        # Получаем список занятых часов на сегодня из БД
        occupied = await get_occupied_hours(today)
        # Отправляем клавиатуру со свободными часами, передавая user_id для последующей обработки
        await call.message.answer(
            "На какое время записать?",
            reply_markup=kb.generate_time_buttons(occupied, user_id)
        )

    # Сценарий 2: запись на будущие дни
    elif action == "next_days":
        today = date.today()
        # Показываем календарь ближайших дней
        await call.message.answer(
            f"Сегодня {today}",
            reply_markup=kb.generate_calendar_buttons(user_id)
        )
        # Сохраняем user_id во временном состоянии (на случай, если понадобится в будущем)
        await state.update_data(target_user_id=user_id)
        await state.set_state(AdminAppointment.selecting_day)


@router.callback_query(F.data.startswith("appoint:"))
async def handle_appointment_time(call: CallbackQuery):
    """
    Обрабатывает выбор времени (на сегодня или на выбранный день).
    callback_data: appoint:{hour}:{user_id}
    """
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("Ошибка формата", show_alert=True)
        return

    try:
        hour = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        await call.answer("Некорректные данные", show_alert=True)
        return

    # Дата — сегодня
    appointment_date = date.today()

    # Сохраняем запись
    await create_appointment(user_id, appointment_date, hour)

    # Отправляем уведомление пользователю
    await bot.send_message(
        chat_id=user_id,
        text=f"✅ Вы успешно записаны на приём!\n📅 Дата: {appointment_date.strftime('%d.%m.%Y')}\n"
             f"🕒 Время: {hour}:00–{hour + 1}:00"
    )

    # Подтверждаем админу
    await call.message.answer("✅ Запись подтверждена и отправлена пользователю!")
    await call.answer()


@router.callback_query(F.data.startswith("calendar_day:"))
async def handle_calendar_day(call: CallbackQuery):
    """
    Обрабатывает выбор дня из календаря.
    callback_data: calendar_day:{day}:{user_id}
    """
    parts = call.data.split(":")
    if len(parts) != 3:
        await call.answer("Ошибка формата", show_alert=True)
        return

    try:
        day = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        await call.answer("Некорректные данные", show_alert=True)
        return

    today = date.today()
    try:
        # Создаём дату: тот же месяц и год, что у today
        selected_date = today.replace(day=day)
        # Если день из следующего месяца (например, сегодня 30 декабря, а выбран 2-й),
        # то нужно аккуратно обработать — но для простоты пока так
    except ValueError:
        # Например, 31 февраля — пропускаем
        await call.answer("Недопустимая дата", show_alert=True)
        return

    # Если выбранная дата — в прошлом
    if selected_date < today:
        await call.answer("Нельзя записаться в прошлое", show_alert=True)
        return

    # Получаем занятые часы на выбранный день
    occupied = await get_occupied_hours(selected_date)

    if selected_date != today:
        await call.message.answer(
            "Запись на будущие дни пока недоступна. Выберите «На сегодня»."
        )
        return

    # Иначе — показываем время (как в сценарии "сегодня")
    await call.message.answer(
        "На какое время записать?",
        reply_markup=kb.generate_time_buttons(occupied, user_id)
    )
    await call.answer()
