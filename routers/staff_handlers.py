from aiogram.types import CallbackQuery, Message
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.requests import (get_user_dict, get_available_hours, create_appointment, get_active_order_id, add_order,
                               get_orders_by_user, update_order, delete_order, get_all_masters, get_filter_appointments,
                               get_appointment, get_appointment_by_users, delete_appointment)
from bot import bot
import asyncio
from aiogram.exceptions import TelegramAPIError
from keybords import keybords as kb
from datetime import date, timedelta
import logging
from utils.time_bot import get_greeting
from aiogram.filters.command import Command
from api.car_api import decode_obd2_code


# Создаём отдельный роутер для обработки действий персонала (админов и мастеров)
router = Router()

logger = logging.getLogger(__name__)


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
    choosing_action = State()   # выбор: быстрый ответ


class MasterOrderMess(StatesGroup):
    order_send_mess = State()


class MasterTransfer(StatesGroup):
    choosing_recipient = State()  # выбор получателя


class MasterEditTotalKm(StatesGroup):
    waiting_for_update_km = State()  # Ввод нового значения total_km


class MasterEditDescription(StatesGroup):
    waiting_for_description = State()  # Ввод текста описания


REPAIR_STATUS_DISPLAY = {
    "in_work": "В работе",
    "wait": "Ожидание",
    "close": "Закрыт"
}


# ===========================
# ========= МАСТЕР ==========
# ===========================

# ЛИЧНЫЙ КАБИНЕТ МАСТЕРА

# ЗАПИСИ / ОЧЕРЕДЬ
@router.callback_query(F.data == "rec_queue")
async def handle_rec_queue(call: CallbackQuery):
    await call.message.answer(
        "📅 Выберите период для просмотра записей:",
        reply_markup=kb.appointment_period_menu()
    )
    await call.answer()


@router.callback_query(F.data.startswith("appt_period:"))
async def handle_appointment_period(call: CallbackQuery):
    period = call.data.split(":", 1)[1]
    master_id = call.from_user.id

    # Определяем фильтр
    date_filter = None
    title = ""
    if period == "today":
        date_filter = "today"
        title = "📅 Записи на сегодня"
    elif period == "month":
        date_filter = "month"
        title = "📆 Записи на этот месяц"
    elif period == "all":
        date_filter = None
        title = "📁 Все записи"
    else:
        await call.answer("❌ Неверный выбор.", show_alert=True)
        return

    appointments = await get_filter_appointments(tg_id_master=master_id, date_filter=date_filter)

    if not appointments:
        await call.answer(f"{title}\n\n❌ Нет записей.", show_alert=True)
        return

    # Удаляем сообщение с выбором периода
    await call.message.delete()

    # Отправляем КАЖДУЮ запись как ОТДЕЛЬНОЕ сообщение
    for appt in appointments:
        date_str = appt["appointment_date"].strftime("%d.%m.%Y")
        start_time = appt["appointment_time"].strftime("%H:%M")
        end_time = appt["end_time"].strftime("%H:%M")

        user_data = await get_user_dict(appt["tg_id_user"], ["user_name", "contact"])
        user_name = user_data["user_name"] if user_data else "—"
        user_contact = user_data["contact"] if user_data else "—"

        text = (
            f"🆔 <b>Запись №{appt['id']}</b>\n"
            f"👤 Клиент: {user_name}\n"
            f'📱 Телеграм: <a href="tg://user?id={appt["tg_id_user"]}">{appt["tg_id_user"]}</a>\n'
            f'📞 Сот. тел: <a href="tel:{user_contact}">{user_contact}</a>\n'
            f"📆 {date_str} | 🕗 {start_time}–{end_time}"
        )

        await call.message.answer(
            text,
            parse_mode="HTML",
            reply_markup=kb.appointment_action_menu(appt["id"], appt["tg_id_user"])
        )

    await call.answer()


# НАПОМНИТЬ О ВСТРЕЧЕ
@router.callback_query(F.data.startswith("remind_mess:"))
async def handle_remind_mess(call: CallbackQuery):
    parts = call.data.split(":")
    appointment_id = int(parts[1])
    client_tg_id = int(parts[2])
    master_tg_id = call.from_user.id

    # Показываем алерт
    await call.answer("✅ Напоминание отправлено!")

    # Получаем имя мастера
    user_data = await get_user_dict(master_tg_id, ["user_name"])
    master_name = user_data["user_name"] if user_data else "—"

    greeting = await get_greeting()
    app = await get_appointment(appointment_id)

    if not app:
        await call.answer(f"❌ Нет записей.", show_alert=True)
        return

    date_str = app.appointment_date.strftime("%d.%m.%Y")
    time_str = app.appointment_time.strftime("%H:%M")

    # Отправляем клиенту
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"💬 Сообщение от мастера\n"
             f"📱 tg_id: {master_tg_id}\n"
             f"👤 Имя: {master_name} \n\n"
             f"{greeting} Вы записаны на приём!\n"
             f"📆 Дата: {date_str}\n"
             f"🕑 Время: {time_str}\n\n"
             f"Для удобства нажмите вариант ответа или введите текстом.",
        reply_markup=kb.user_answer_app(master_tg_id)
    )

    await call.answer()


# ПЕРЕНЕСТИ ВСТРЕЧУ


# УДАЛИТЬ ЗАПИСЬ
@router.callback_query(F.data.startswith("del_app:"))
async def delete_appointment_handler(call: CallbackQuery):
    try:
        appointment_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID записи.", show_alert=True)
        return

    # Удаляем запись
    success = await delete_appointment(appointment_id)

    if success:
        await call.answer("✅ Запись удалена.", show_alert=True)
        # Удаляем сообщение с записью
        await call.message.delete()
    else:
        await call.answer("❌ Запись не найдена или уже удалена.", show_alert=True)


# ВЫБОР "ТЕКУЩИЕ ЗАКАЗЫ"
@router.callback_query(F.data == "my_actions_orders")
async def master_current_orders(call: CallbackQuery):
    master_id = call.from_user.id
    # Получаем активные заказы, между пользователем и мастером
    orders = await get_orders_by_user(tg_id_master=master_id, active=True)

    if not orders:
        await call.answer("❌ У вас нет активных заказов.", show_alert=True)
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
                f"🚗 Марка авто: {order['brand_auto']}\n"
                f"⚙️ Модель авто: {order['model_auto']}\n"
                f"📆 Год выпуска: {order['year_auto']}\n"
                f"🛞 Пробег авто: {order['total_km']} km\n"
                f"ℹ️ VIN: {order['vin_number']}\n"
                f"🔢 Гос. номер: {order['gos_num']}\n"
                f"🔧 Статус: {status_display}\n"
                f"📝 Описание:\n{order['description']}\n\n"
                f"📅 Дата создания: {date_str}"
            )

            await call.message.answer(
                text,
                parse_mode="HTML",
                reply_markup=kb.master_order_action_menu([1, 2, 9, 3, 4, 5, 6, 7, 10, 8], order_id, tg_id_user)
            )

    await call.answer()


# ВЫБОР ВЫПОЛНЕНО
# Роутер: обрабатывает complied_order:order_id:client_tg_id
@router.callback_query(F.data.startswith("comp_odr:"))
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
    user_data = await get_user_dict(master_tg_id, ["user_name"])
    master_name = user_data["user_name"]

    # Обновляем заказ: статус = wait, complied = True
    await update_order(
        order_id=order_id,
        repair_status="wait",
        complied=True
    )

    # Отправляем клиенту
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"💬 Ответ от мастера\n"
             f"📱 tg_id: {master_tg_id}\n"
             f"👤 Имя: {master_name} \n\n"
             f"✅ Можете принимать работу и забирать автомобиль! 🔑\n\n",
        reply_markup=kb.get_accept_work_keyboard(order_id, master_tg_id)  # Кнопка "Принять работу"
    )

    await call.message.answer("✅ Сообщение «Можете забирать» отправлено клиенту.")
    await state.clear()
    await call.message.delete()
    await call.answer()


# ВЫБОР "Отправить сообщение"
@router.callback_query(F.data.startswith("ord_mess:"))
async def request_custom_message(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки 'Отправить сообщение' из меню заказа.
    Запрашивает текст сообщения у мастера.
    """
    try:
        # Извлекаем order_id из callback_data
        client_tg_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    master_tg_id = call.from_user.id

    # Сохраняем данные в FSM
    await state.update_data(
        client_tg_id=client_tg_id,
        master_tg_id=master_tg_id
    )

    await call.message.answer("✍️ Введите сообщение для клиента:")
    await state.set_state(MasterOrderMess.order_send_mess)
    await call.answer()


# РОУТЕР ловит текст от мастера и отправляет клиенту
@router.message(MasterOrderMess.order_send_mess)
async def send_custom_message_to_client(message: Message, state: FSMContext):
    data = await state.get_data()
    client_tg_id = data["client_tg_id"]
    master_tg_id = data["master_tg_id"]

    user_data = await get_user_dict(master_tg_id, ["user_name"])
    master_name = user_data["user_name"]

    # Отправляем сообщение клиенту
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"💬 Сообщение от мастера\n\n"
             f"👤 Имя: {master_name} \n"
             f"📱 Телеграм: {master_tg_id}\n\n"
             f"{message.text}",
        reply_markup=kb.action_buttons_orders_menu_new([8, 10], master_tg_id)
    )

    await message.answer("✅ Ваше сообщение отправлено клиенту.")
    await state.clear()


# === ОБНОВИТЬ ПРОБЕГ КМ ===
@router.callback_query(F.data.startswith("up_km:"))
async def edit_status(call: CallbackQuery, state: FSMContext):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    await state.update_data(order_id=order_id)

    # Отправляем инфо. текст и сохраняем его ID
    prompt_msg = await call.message.answer(
        "📋 Обновление пробега авто.\n\n✍️ Введите реальный пробег в чат:"
    )

    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(MasterEditTotalKm.waiting_for_update_km)


@router.message(MasterEditTotalKm.waiting_for_update_km)
async def process_new_total_km(message: Message, state: FSMContext):
    new_total_km = message.text.strip()

    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except TelegramAPIError:
        pass

    if not new_total_km:
        # Удаляем старый запрос (если есть)
        data = await state.get_data()
        old_prompt_id = data.get("prompt_message_id")
        if old_prompt_id:
            try:
                await message.bot.delete_message(message.chat.id, old_prompt_id)
            except TelegramAPIError:
                pass

        # Отправляем новый запрос
        prompt_msg = await message.answer("❌ Пробег не может быть пустым. Введите снова:")
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    prompt_msg_id = data.get("prompt_message_id")

    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден.")
        await state.clear()
        return

    success = await update_order(order_id=order_id, total_km=new_total_km)

    # Удаляем запрос ("Введите описание")
    if prompt_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_msg_id)
        except TelegramAPIError:
            pass

    # Подтверждение
    confirm = await message.answer("✅ Пробег обновлен!" if success else "❌ Ошибка обновления.")

    await asyncio.sleep(2)

    try:
        await confirm.delete()
    except TelegramAPIError:
        pass

    await state.clear()


# === ИЗМЕНИТЬ СТАТУС ===
@router.callback_query(F.data.startswith("ed_st:"))
async def edit_status(call: CallbackQuery):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    # Обновляем статус заказа
    await update_order(
        order_id=order_id,
        repair_status="wait"
    )

    await call.answer(f"✅ Статус изменён на wait!")


# === ИЗМЕНИТЬ ОПИСАНИЕ ===
@router.callback_query(F.data.startswith("ed_des:"))
async def edit_description(call: CallbackQuery, state: FSMContext):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    await state.update_data(order_id=order_id)

    # Отправляем НОВОЕ СООБЩЕНИЕ и сохраняем его ID
    prompt_msg = await call.message.answer(
        "📋 Редактирование описания\n\n✍️ Введите новое описание заказа в чат:"
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)

    await state.set_state(MasterEditDescription.waiting_for_description)
    await call.answer()


@router.message(MasterEditDescription.waiting_for_description)
async def process_new_description(message: Message, state: FSMContext):
    new_description = message.text.strip()

    # Удаляем сообщение пользователя сразу
    try:
        await message.delete()
    except TelegramAPIError:
        pass

    if not new_description:
        # Удаляем старый запрос (если есть)
        data = await state.get_data()
        old_prompt_id = data.get("prompt_message_id")
        if old_prompt_id:
            try:
                await message.bot.delete_message(message.chat.id, old_prompt_id)
            except TelegramAPIError:
                pass

        # Отправляем новый запрос
        prompt_msg = await message.answer("❌ Описание не может быть пустым. Введите снова:")
        await state.update_data(prompt_message_id=prompt_msg.message_id)
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    prompt_msg_id = data.get("prompt_message_id")

    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден.")
        await state.clear()
        return

    success = await update_order(order_id=order_id, description=new_description)

    # Удаляем запрос ("Введите описание")
    if prompt_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_msg_id)
        except TelegramAPIError:
            pass

    # Подтверждение
    confirm = await message.answer("✅ Описание обновлено!" if success else "❌ Ошибка обновления.")

    await asyncio.sleep(2)

    try:
        await confirm.delete()
    except TelegramAPIError:
        pass

    await state.clear()


# === ЗАКРЫТЬ ЗАКАЗ ===
@router.callback_query(F.data.startswith("cl_odr:"))
async def close_order(call: CallbackQuery):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    # Обновляем статус заказа на "close"
    success = await update_order(order_id=order_id, repair_status="close", complied=True)

    if success:
        await call.answer("✅ Заказ успешно закрыт!", show_alert=True)
    else:
        await call.answer("❌ Не удалось закрыть заказ.", show_alert=True)


# === ПЕРЕДАТЬ ЗАКАЗ ===
@router.callback_query(F.data.startswith("tr_odr:"))
async def start_transfer_order(call: CallbackQuery, state: FSMContext):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    current_master_id = call.from_user.id

    # Получаем список мастеров (без текущего)
    masters = await get_all_masters(exclude_tg_id=current_master_id)
    if not masters:
        await call.answer("❌ Нет доступных мастеров для передачи.", show_alert=True)
        await state.clear()
        return

    # Сохраняем данные мастеров в состоянии (чтобы не дёргать БД при выборе)
    await state.update_data(
        order_id=order_id,
        current_master_id=current_master_id,
        available_masters=masters  # сохраняем список
    )

    # Генерируем клавиатуру
    keyboard = kb.transfer_master_keyboard(masters)
    await call.message.answer(
        "👤 Выберите мастера, которому передать заказ:",
        reply_markup=keyboard
    )
    await state.set_state(MasterTransfer.choosing_recipient)
    await call.answer()


# УДАЛИТЬ ЗАКАЗ delete_order
@router.callback_query(F.data.startswith("del_odr:"))
async def handle_delete_order(call: CallbackQuery):
    try:
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    # Удаляем заказ из БД
    success = await delete_order(order_id)

    if not success:
        await call.answer("❌ Заказ не найден или уже удалён.", show_alert=True)
        return

    # Показываем подтверждение
    await call.answer("✅ Заказ успешно удалён.", show_alert=True)

    # Удаляем сообщение с кнопкой "Удалить заказ"
    try:
        await call.message.delete()
    except TelegramAPIError as e:
        logger.debug(f"Не удалось удалить сообщение при удалении заказа {order_id}: {e}")


# ВОЗВРАТ В ТЕКУЩИЙ resume_order
@router.callback_query(F.data.startswith("res_odr:"))
async def handle_resume_order(call: CallbackQuery):
    try:
        # Извлекаем order_id из callback_data
        order_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID заказа.", show_alert=True)
        return

    # Обновляем заказ: возвращаем в работу
    success = await update_order(
        order_id=order_id,
        repair_status="in_work",
        complied=False
    )

    if not success:
        await call.answer("❌ Не удалось обновить заказ. Возможно, он не найден.", show_alert=True)
        return

    # Отправляем подтверждение
    await call.answer("✅ Заказ возвращён в работу.", show_alert=True)


@router.callback_query(MasterTransfer.choosing_recipient, F.data.startswith("select_master:"))
async def select_recipient_master(call: CallbackQuery, state: FSMContext):
    try:
        new_master_tg_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID мастера.", show_alert=True)
        return

    data = await state.get_data()
    order_id = data.get("order_id")
    available_masters = data.get("available_masters", [])

    # Находим выбранного мастера по tg_id
    selected_master = None

    for master in available_masters:
        if master["tg_id"] == new_master_tg_id:
            selected_master = master
            break

    if not selected_master:
        await call.answer("❌ Выбранный мастер недоступен.", show_alert=True)
        return

    # Обновляем заказ
    success = await update_order(
        order_id=order_id,
        tg_id_master=selected_master["tg_id"],
        master_name=selected_master["user_name"],
        master_contact=selected_master["contact"]
    )

    if not success:
        await call.message.answer("❌ Не удалось обновить заказ.")
        await state.clear()
        await call.answer()
        return

    # Удаляем клавиатуру и показываем подтверждение
    await call.answer("✅ Заказ успешно передан другому мастеру!", show_alert=True)
    await call.message.delete()
    await state.clear()


# ===========================
# ВЗАИМОДЕЙСТВИЕ С КЛИЕНТОМ
# ===========================


# === ОЖИДАНИЕ ===
@router.callback_query(F.data.startswith("await:"))
async def handle_await_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])

    response_text = "⌚️ В данный момент занят. Отвечу, как только освобожусь!"
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Ожидание» отправлен пользователю.")
    await call.answer()


# === ОТКАЗ ===
@router.callback_query(F.data.startswith("refuse:"))
async def handle_refuse_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    response_text = f"😔 Извините, но к сожалению не сможем помочь с этой проблемой."
    await bot.send_message(chat_id=user_id, text=response_text)
    await call.message.answer("✅ Ответ «Отказ» отправлен пользователю.")
    await call.answer()


# === ЗВОНИТЕ ===
@router.callback_query(F.data.startswith("call:"))
async def handle_call_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    master_tg_id = call.from_user.id

    user_data = await get_user_dict(master_tg_id, ["user_name", "contact"])
    master_name = user_data["user_name"] if user_data else "—"
    master_contact = user_data["contact"] if user_data else "—"

    response_text = (f'🔔 Звоните по номеру!\n'
                     f'👤 Имя: {master_name}\n'
                     f'📞 Сот. тел.: <a href="tel:{master_contact}">{master_contact}</a>')

    await bot.send_message(chat_id=user_id, text=response_text, parse_mode="HTML")
    await call.message.answer("✅ Ответ «Звоните» отправлен пользователю.")
    await call.answer()


# === УТОЧНИТЬ УДОБНОЕ ВРЕМЯ ===
@router.callback_query(F.data.startswith("check_time:"))
async def handle_check_time_action(call: CallbackQuery):

    # Извлекаем tg_id клиента
    client_tg_id = int(call.data.split(":", 1)[1])
    master_tg_id = call.from_user.id

    user_data = await get_user_dict(master_tg_id, ["user_name"])
    master_name = user_data["user_name"] if user_data else "—"
    greeting = await get_greeting()

    # Отправляем клиенту сообщение с уточнением
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"💬 Ответ от мастера:\n"
             f"📱 tg_id: {master_tg_id}\n"
             f"👤 Имя: {master_name} \n\n"
             f"{greeting} Напишите удобную дату и время для того чтобы я вас записал!",
        reply_markup=kb.action_buttons_orders_menu_new([8, 10], master_tg_id)
    )

    # Подтверждаем мастеру
    await call.message.answer("✅ Уточняющий вопрос по времени отправлен клиенту.")
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

    user_data = await get_user_dict(user_id, ["user_name"])
    user_name = user_data["user_name"] if user_data else "—"

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
    master_tg_id = call.from_user.id

    # Записываем в БД
    await create_appointment(user_id, master_tg_id, selected_date, start_hour, end_hour)

    # Отправляем пользователю
    start_str = f"{int(start_hour)}:{'30' if start_hour % 1 else '00'}"
    end_str = f"{int(end_hour)}:{'30' if end_hour % 1 else '00'}"

    # Присваиваем переменным полученое имя и номер тел.
    user_data = await get_user_dict(master_tg_id, ["user_name", "contact"])
    master_name = user_data["user_name"] if user_data else "—"
    tel = user_data["contact"] if user_data else "—"

    await bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ Запись подтверждена!\n\n"
            f"👤 Имя мастера: {master_name}\n"
            f"📱 Телеграм: {master_tg_id}\n"
            f"📞 Сот. тел.: {tel}\n"
            f"📅 Дата: {selected_date.strftime('%d.%m.%Y')}\n"
            f"🕒 Время: {start_str}–{end_str}\n\n"
            f"После прибытия и осмотра вашего авто, ТОЛЬКО ПО ПРОСЬБЕ МАСТЕРА нажмите кнопку 'ЗАЯВКА НА РЕМОНТ'."
        ),
        reply_markup=kb.action_buttons_orders_menu_new([7, 11], master_tg_id)
    )

    await call.message.delete()
    await call.message.answer("✅ Форма отправлена пользователю!")
    await state.clear()
    await call.answer()


# === СООБЩЕНИЕ НА ВОПРОС ПОЛЬЗОВАТЕЛЯ (state 1) ===
# Извлекаем tg_id пользователя из callback_data и переходит в режим ожидания текста ответа.
@router.callback_query(F.data.startswith("replay_mess:"))
async def custom_reply_to_user(call: CallbackQuery, state: FSMContext):
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
    master_tg_id = message.chat.id

    # Безопасная проверка: если ID отсутствует — выходим
    if not user_id:
        await message.answer("Ошибка: пользователь не найден.")
        await state.clear()
        return

    # Запрашиваем имя пользователя из базы данных
    user_data = await get_user_dict(master_tg_id, ["user_name"])
    master_name = user_data["user_name"] if user_data else "—"

    # Отправляем сообщение пользователю с кнопкой для обратной связи
    await bot.send_message(
        chat_id=user_id,
        text=f"💬 Ответ от мастера:\n"
             f"📱 tg_id: {master_tg_id}\n"
             f"👤 Имя: {master_name} \n\n"
             f"{message.text}",
        reply_markup=kb.action_buttons_orders_menu_new([8, 10], master_tg_id)
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
    if len(parts) != 3:
        await call.answer("❌ Некорректный формат данных", show_alert=True)
        return

    action = parts[1]
    client_tg_id = int(parts[2])
    master_tg_id = call.from_user.id

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
            reply_markup=kb.action_buttons_orders_menu_new([6, 9], client_tg_id)
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

    await state.update_data(description=text)
    await message.answer(
        f"Описание работ: {text}",
        reply_markup=kb.action_buttons_orders_menu_new([6, 9], client_tg_id),
    )
    await state.set_state(RepairOrderStates.confirming)


@router.callback_query(RepairOrderStates.confirming, F.data.startswith("create_order:"))
async def create_repair_order(call: CallbackQuery, state: FSMContext):
    """
    Создаёт заказ в базе данных после подтверждения мастера.
    Проверяет существование пользователей и отсутствие активного заказа.
    """
    parts = call.data.split(":")
    if len(parts) != 2:
        return

    try:
        client_tg_id = int(parts[1])
    except ValueError:
        return

    master_tg_id = call.from_user.id
    data = await state.get_data()
    description = data.get("description", "Без описания")

    # Получаем только нужные поля для клиента и мастера
    client_fields = ["user_name", "contact", "brand_auto", "model_auto", "gos_num", "year_auto", "vin_number"]
    master_fields = ["user_name", "contact"]

    client_data = await get_user_dict(client_tg_id, client_fields)
    master_data = await get_user_dict(master_tg_id, master_fields)
    # Получаем запись для последующего удаления
    app_data = await get_appointment_by_users(client_tg_id, master_tg_id)
    app_id = app_data.id
    app_date = app_data.appointment_date
    app_time = app_data.appointment_time

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
        "model_auto": client_data["model_auto"],
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
             f"⚙️ Модель авто: {client_data['model_auto']}\n"
             f"📆 Год: {client_data['year_auto']}\n"
             f"🔢 Гос номер: {client_data['gos_num']}\n"
             f"👤 Имя мастера: {master_data['user_name']}\n"
             f"📞 Сот. тел.: {master_data['contact']}\n"
             f"📄 Описание работ: {description}\n"
             f"🔧 Статус: 'В работе'\n\n"
             f"Вы можете скрыть это сообщение. Ваш заказ на ремонт будет отображаться в "
             f"ЛИЧНЫЙ КАБИНЕТ -> ТЕКУЩИЙ РЕМОНТ",
        reply_markup=kb.login_menu([4])
    )

    # Удаляем запись, так как она стала не актульной - поскольку клиент приехал
    app_id = await delete_appointment(app_id)

    res_text = f"✅ Запись {app_date} {app_time} удалена!" if app_id else "❌ Запись не найдена!"

    await call.message.edit_reply_markup(reply_markup=None)
    await call.answer(f"✅ Вы приняли в ремонт автомобиль. Заявка на ремонт создана!\n"
                      f"{res_text}")
    await state.clear()


# РОУТЕР слушает кнопку назад, очищает состояния и удаляет сообщение
@router.callback_query(F.data == "cancel")
async def cancel_quick_action(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await call.answer()


# ==============================
# API
# ==============================
@router.message(Command("dtc"))
async def cmd_dtc(message: Message):
    """
    Команда: /dtc <код>
    Пример: /dtc P0300
    """
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "🔤 Укажите код ошибки после команды.\n"
            "Пример: <code>/dtc P0001</code>",
            parse_mode="HTML"
        )
        return

    code = parts[1].strip().upper()

    # Простая валидация формата
    if not (len(code) >= 4 and code[0] in "PBCU" and code[1:].replace("X", "").isalnum()):
        await message.answer(
            "❌ Некорректный формат кода.\n"
            "Код должен начинаться с P/B/C/U и содержать 4–5 символов.\n"
            "Примеры: <code>P0300</code>, <code>P3455</code>, <code>U1122</code>",
            parse_mode="HTML"
        )
        return

    result = await decode_obd2_code(code)
    if not result:
        await message.answer(f"🔍 Код <b>{code}</b> не найден в базе.", parse_mode="HTML")
        return

    # Форматируем ответ
    definition = result["definition"]
    causes = result["cause"]

    causes_text = "\n".join(f"• {cause}" for cause in causes) if causes else "Причины не указаны."

    response = (
        f"✅ <b>Код:</b> {result['code']}\n"
        f"📝 <b>Описание:</b> {definition}\n\n"
        f"🔧 <b>Возможные причины:</b>\n{causes_text}"
    )

    await message.answer(response, parse_mode="HTML")

    # # Сохраняем в историю (для /history)
    # from database.requests import save_search_history
    # await save_search_history(
    #     tg_id=message.from_user.id,
    #     query=code,
    #     result=response,
    #     mode="dtc"
    # )




