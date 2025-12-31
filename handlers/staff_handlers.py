from aiogram.types import CallbackQuery, Message
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database.requests import (get_user_dict, get_available_hours, create_appointment, get_active_order_id, add_order,
                               get_orders_by_user, update_order, delete_order, get_all_masters, get_filter_appointments,
                               get_appointment, get_appointment_by_users, delete_appointment, save_api_dtc_record,
                               update_user, save_manual_diagnostic_record, get_diagnostics_by_filter, delete_user,
                               get_api_dtc_history, get_user_dict_by_id, update_user_by_id, has_active_appointment,
                               get_user_statistics, get_appointment_statistics, get_order_statistics,
                               get_all_active_user_ids, get_top_clients_statistics, get_top_masters_statistics)
from utils.profile_render import render_master_profile
from bot import bot
import asyncio
from aiogram.exceptions import TelegramAPIError
from keybords import keybords as kb
from datetime import date, timedelta
import logging
from utils.time_bot import get_greeting
from utils.utils_bot import message_deleter
from api.car_api import decode_obd2_code
import json


# Создаём отдельный роутер для обработки действий персонала (админов и мастеров)
router = Router()

logger = logging.getLogger(__name__)
api_logger = logging.getLogger("api")


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
    choosing_action = State()  # выбор: быстрый ответ


class MasterOrderMess(StatesGroup):
    order_send_mess = State()  # Ввод текста сообщения


class MasterTransfer(StatesGroup):
    choosing_recipient = State()  # выбор получателя


class MasterEditTotalKm(StatesGroup):
    waiting_for_update_km = State()  # Ввод нового значения total_km


class MasterEditDescription(StatesGroup):
    waiting_for_description = State()  # Ввод текста описания


class MasterDtcMode(StatesGroup):
    in_dtc = State()                # для API
    manual_select_order = State()   # выбор заказа
    manual_input_dtc = State()      # ввод DTC-кода


class EditProfile(StatesGroup):
    """Состояния для редактирования личных данных мастера."""
    edit_profile_master = State()


class MasterManagement(StatesGroup):
    edit_status = State()  # редактирование должности мастера
    edit_rating = State()  # редактирование рейтинга мастера
    confirm_delete = State()


class UserManagement(StatesGroup):
    entering_uid = State()
    viewing_user = State()


REPAIR_STATUS_DISPLAY = {
    "in_work": "В работе",
    "wait": "Ожидание",
    "close": "Закрыт"
}


@router.callback_query(F.data == "admin_panel")
async def handle_admin_panel(call: CallbackQuery):
    """Открывает админ-панель с выбором раздела."""
    text = (
        "📁 <b>АДМИН ПАНЕЛЬ</b>\n\n"
        "Здесь вы можете управлять пользователями и мастерами, "
        "настраивать права доступа, а также контролировать все "
        "записи и заказы в системе."
    )

    await call.message.edit_text(
        text,
        reply_markup=kb.admin_action_menu([1, 2, 3]),
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data == "manage_masters")
async def handle_manage_masters(call: CallbackQuery):
    """Открывает список мастеров для управления."""
    masters = await get_all_masters()  # возвращает [{'tg_id', 'user_name', 'status'}, ...]

    if not masters:
        await call.answer("В системе пока нет ни одного мастера.", show_alert=True)
        return

    keyboard = kb.create_masters_management_keyboard(masters)

    await call.message.edit_text(
        "📁 <b>УПРАВЛЕНИЕ МАСТЕРАМИ</b>\n\n"
        "Выберите мастера для просмотра информации о нём и его работе. Таже вы можете отредактировать необходимые "
        "данные",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    await call.answer()


@router.callback_query(F.data.startswith("manage_master:"))
async def handle_manage_single_master(call: CallbackQuery):
    try:
        tg_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("Некорректный ID мастера", show_alert=True)
        return

    text, keyboard = await render_master_profile(tg_id)
    await call.message.edit_text(text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("master_action:"))
async def handle_master_action(call: CallbackQuery, state: FSMContext):
    data_parts = call.data.split(":")
    if len(data_parts) != 3:
        await call.answer("Некорректный формат действия", show_alert=True)
        return

    try:
        tg_id = int(data_parts[2])
        action = data_parts[1]
    except (ValueError, IndexError):
        await call.answer("Ошибка данных действия", show_alert=True)
        return

    user_data = await get_user_dict(tg_id=tg_id, fields=["user_name", "role"])
    if not user_data or user_data.get("role") != "master":
        await call.answer("Мастер не найден", show_alert=True)
        return

    master_name = user_data["user_name"]
    chat_id = call.message.chat.id
    profile_msg_id = call.message.message_id  # ID сообщения с профилем
    temp_ids = []  # только новые временные сообщения

    if action == "edit_status":
        msg = await call.message.answer(
            f"✏️ Введите новую <b>должность</b> для мастера <b>{master_name}</b>:",
            parse_mode="HTML"
        )
        temp_ids.append(msg.message_id)
        await state.set_state(MasterManagement.edit_status)
        await state.update_data(
            target_tg_id=tg_id,
            chat_id=chat_id,
            profile_msg_id=profile_msg_id,  # сохраняем для последующего обновления
            temp_message_ids=temp_ids
        )

    elif action == "edit_rating":
        msg = await call.message.answer(
            f"✏️ Введите новый <b>рейтинг</b> для мастера <b>{master_name}</b> (целое число от 0 до 1000):",
            parse_mode="HTML"
        )
        temp_ids.append(msg.message_id)
        await state.set_state(MasterManagement.edit_rating)
        await state.update_data(
            target_tg_id=tg_id,
            chat_id=chat_id,
            profile_msg_id=profile_msg_id,
            temp_message_ids=temp_ids
        )

    elif action == "delete":
        confirm_msg = await call.message.answer(
            f"⚠️ Вы уверены, что хотите <b>удалить мастера</b> <b>{master_name}</b>?\n"
            "Это действие нельзя отменить.",
            reply_markup=kb.admin_action_menu([12, 4], tg_id=tg_id),
            parse_mode="HTML"
        )
        temp_ids.append(confirm_msg.message_id)
        await state.update_data(
            target_tg_id=tg_id,
            chat_id=chat_id,
            profile_msg_id=profile_msg_id,
            temp_message_ids=temp_ids
        )

    else:
        await call.answer("Неизвестное действие", show_alert=True)

    await call.answer()


@router.message(MasterManagement.edit_status)
async def process_edit_status(message: Message, state: FSMContext):
    new_status = message.text.strip()
    if not new_status:
        msg = await message.answer("❌ Должность не может быть пустой. Попробуйте снова:")
        data = await state.get_data()
        data["temp_message_ids"].append(msg.message_id)
        await state.set_data(data)
        return

    data = await state.get_data()
    tg_id = data["target_tg_id"]
    chat_id = data["chat_id"]
    profile_msg_id = data["profile_msg_id"]
    temp_ids = data.get("temp_message_ids", [])
    temp_ids.append(message.message_id)

    success = await update_user(tg_id=tg_id, column="status", value=new_status)

    if success:
        confirm_msg = await message.answer("✅ Должность успешно обновлена!")
        temp_ids.append(confirm_msg.message_id)

        # Обновляем сообщение с профилем
        text, keyboard = await render_master_profile(tg_id)
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=profile_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            pass  # если сообщение уже удалено

    else:
        error_msg = await message.answer("❌ Не удалось обновить должность.")
        temp_ids.append(error_msg.message_id)

    if temp_ids:
            _ = asyncio.create_task(
                message_deleter(
                    bot=message.bot,
                    chat_id=chat_id,
                    message_ids=temp_ids
                )
        )

    await state.clear()


@router.message(MasterManagement.edit_rating)
async def process_edit_rating(message: Message, state: FSMContext):
    try:
        rating = int(message.text.strip())
        if rating < 0 or rating > 1000:
            raise ValueError
    except ValueError:
        msg = await message.answer("❌ Введите целое число от 0 до 1000:")
        data = await state.get_data()
        data["temp_message_ids"].append(msg.message_id)
        await state.set_data(data)
        return

    data = await state.get_data()
    tg_id = data["target_tg_id"]
    chat_id = data["chat_id"]
    profile_msg_id = data["profile_msg_id"]
    temp_ids = data.get("temp_message_ids", [])
    temp_ids.append(message.message_id)

    success = await update_user(tg_id=tg_id, column="rating", value=rating)

    if success:
        confirm_msg = await message.answer("✅ Рейтинг успешно обновлён!")
        temp_ids.append(confirm_msg.message_id)

        # Обновляем сообщение с профилем
        text, keyboard = await render_master_profile(tg_id)
        try:
            await message.bot.edit_message_text(
                chat_id=chat_id,
                message_id=profile_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except Exception:
            pass

    else:
        error_msg = await message.answer("❌ Не удалось обновить рейтинг.")
        temp_ids.append(error_msg.message_id)

    if temp_ids:
        _ = asyncio.create_task(
                message_deleter(
                    bot=message.bot,
                    chat_id=chat_id,
                    message_ids=temp_ids
                )
        )

    await state.clear()


@router.callback_query(F.data.startswith("confirm_delete_master:"))
async def confirm_delete_master(call: CallbackQuery, state: FSMContext):
    try:
        tg_id = int(call.data.split(":")[1])
    except (ValueError, IndexError):
        await call.answer("Ошибка ID", show_alert=True)
        return

    success = await delete_user(tg_id)

    data = await state.get_data()
    profile_msg_id = data.get("profile_msg_id")  # ID исходного сообщения с профилем
    chat_id = call.message.chat.id

    # Удаляем ТОЛЬКО сообщение с подтверждением (call.message) — оно больше не нужно
    try:
        await call.bot.delete_message(chat_id=chat_id, message_id=call.message.message_id)
    except:
        pass  # если уже удалено — игнорируем

    # Алерт с результатом
    if success:
        alert_text = "✅ Мастер успешно удалён."
    else:
        alert_text = "❌ Невозможно удалить."

    await call.answer(alert_text, show_alert=True)

    # Обновляем список мастеров и редактируем исходное сообщение (профиль → список)
    masters = await get_all_masters()

    if profile_msg_id:
        if not masters:
            text = (
                "📁 <b>УПРАВЛЕНИЕ МАСТЕРАМИ</b>\n\n"
                "Вы удалили последнего мастера. Теперь будете работать сами 😅\n"
                "Найдите новых рабочих или смените свою роль на мастера."
            )
            keyboard = kb.admin_action_menu([5])  # admin_panel
        else:
            text = (
                "📁 <b>УПРАВЛЕНИЕ МАСТЕРАМИ</b>\n\n"
                "Выберите мастера для просмотра информации о нём и его работе. "
                "Также вы можете отредактировать необходимые данные."
            )
            keyboard = kb.create_masters_management_keyboard(masters)

        try:
            await call.bot.edit_message_text(
                chat_id=chat_id,
                message_id=profile_msg_id,
                text=text,
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        except TelegramAPIError:
            pass

    await state.clear()


# АДМИН. УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
@router.callback_query(F.data == "manage_users")
async def handle_manage_users(call: CallbackQuery, state: FSMContext):
    """Запрашивает UID пользователя для управления."""

    prompt_msg = await call.message.answer(
        "📁 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ</b>\n\n"
        "📝 Введите <b>UID</b> пользователя (целое число из его профиля):",
        reply_markup=kb.admin_action_menu([4]),
        parse_mode="HTML"
    )
    await state.update_data(prompt_message_id=prompt_msg.message_id)
    await state.set_state(UserManagement.entering_uid)
    await call.answer()


@router.message(UserManagement.entering_uid)
async def process_user_uid_input(message: Message, state: FSMContext):
    user_input = message.text.strip()

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except TelegramAPIError:
        pass

    # Получаем ID сообщения с запросом
    data = await state.get_data()
    prompt_msg_id = data.get("prompt_message_id")

    # Валидация UID
    try:
        uid = int(user_input)
        if uid <= 0:
            raise ValueError
    except ValueError:
        # Удаляем старый запрос
        if prompt_msg_id:
            try:
                await message.bot.delete_message(message.chat.id, prompt_msg_id)
            except TelegramAPIError:
                pass
        # Отправляем новый запрос
        new_prompt = await message.answer("❌ Некорректный UID. Введите положительное целое число:")
        await state.update_data(prompt_message_id=new_prompt.message_id)
        return

    # Ищем пользователя по внутреннему ID (не tg_id!)
    user_data = await get_user_dict_by_id(uid)
    if not user_data:
        if prompt_msg_id:
            try:
                await message.bot.delete_message(message.chat.id, prompt_msg_id)
            except TelegramAPIError:
                pass
        error_msg = await message.answer("❌ Пользователь с таким UID не найден.")
        await asyncio.sleep(2)
        try:
            await error_msg.delete()
        except TelegramAPIError:
            pass
        await state.clear()
        return

    # Формируем карточку пользователя
    text = (
        f"📌 UID: {user_data['id']}\n"
        f"🆔 Telegram ID: <code>{user_data['tg_id']}</code>\n"
        f"👤 Имя: {user_data['user_name']}\n"
        f"🔸 Статус: {user_data['status']}\n"
        f"📞 Сот.тел: {user_data['contact']}\n"
        f"⭐ Рейтинг: {user_data['rating']}\n"
        f"📍 Роль: {user_data['role']}\n"
        f"🚗 Авто: {user_data['brand_auto']} {user_data['model_auto']} ({user_data['year_auto']})\n"
        f"🔢 Гос. номер: {user_data['gos_num']}\n"
        f"🆔 VIN: {user_data['vin_number']}\n"
        f"📅 Дата регистрации: {user_data['date'].strftime('%d.%m.%Y %H:%M') if user_data['date'] else '—'}"
    )

    await message.answer(text, reply_markup=kb.admin_user_manage(uid), parse_mode="HTML")

    # Очищаем состояние и удаляем запрос
    if prompt_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, prompt_msg_id)
        except TelegramAPIError:
            pass
    await state.clear()


# АДМИН. НАЗНАЧИТЬ МАСТЕРОМ ИЛИ ЗАБЛОКИРОВАТЬ
@router.callback_query(F.data.startswith("admin_user_action:"))
async def handle_admin_user_action(call: CallbackQuery):
    """
    Обрабатывает действия администратора над пользователем:
    - promote → назначить мастером
    - block → заблокировать (меняет роль на 'blocked')
    """
    parts = call.data.split(":", 2)
    if len(parts) != 3:
        await call.answer("❌ Неверный формат действия", show_alert=True)
        return

    action, uid_str = parts[1], parts[2]
    try:
        uid = int(uid_str)
    except ValueError:
        await call.answer("❌ Некорректный UID", show_alert=True)
        return

    success = False

    if action == "appoint_employ":
        # Назначаем мастером
        success = await update_user_by_id(
            uid,
            role="master",
            status="Новый рабочий",
            brand_auto="-",
            can_messages=True
        )
        message = "✅ Пользователь назначен мастером!" if success else "❌ Не удалось назначить мастера."

    elif action == "unlock":
        # Разблокируем
        success = await update_user_by_id(
            uid,
            role="user"
        )
        message = "✅ Пользователь разблокирован." if success else "❌ Не удалось разблокировать пользователя."

    elif action == "block":
        # Блокируем
        success = await update_user_by_id(
            uid,
            role="blocked"
        )
        message = "✅ Пользователь заблокирован." if success else "❌ Не удалось заблокировать пользователя."

    else:
        await call.answer("❌ Неизвестное действие", show_alert=True)
        return

    await call.answer(message, show_alert=True)

    # удалить текущее сообщение и вернуть в админ-панель:
    try:
        await call.message.delete()
    except TelegramAPIError:
        pass


# ==============================
# СТАТИСТИКА
# ==============================
@router.callback_query(F.data == "admin_stats")
async def handle_admin_stats(call: CallbackQuery):
    await call.message.edit_text(
        "📊 <b>ВЫБЕРИТЕ РАЗДЕЛ СТАТИСТИКИ</b>\n\n"
        "Здесь вы можете получить оперативную сводку по пользователям, записям и заказам в системе.",
        reply_markup=kb.admin_action_menu([14, 15, 16, 18, 19, 3]),
        parse_mode="HTML"
    )
    await call.answer()


# Обработчик: конкретный тип статистики
@router.callback_query(F.data.startswith("stat:"))
async def handle_stat_detail(call: CallbackQuery):
    stat_type = call.data.split(":", 1)[1]
    text = (f"📊 <b>СТАТИСТИКА</b>\n"
            f"Подробная аналитика по пользователям, записям и заказам: общие показатели, распределение по ролям, "
            f"динамика за день/месяц/год, топ загруженных дней и средняя производительность сервиса.\n\n")

    if stat_type == "users":
        stats = await get_user_statistics()
        text += (
            f"👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n"
            f"Всего: {stats['total']}\n"
            f"Активных: {stats['total'] - stats['blocked']}\n"
            f"Заблокировано: {stats['blocked']}\n\n"
            f"Роли:\n"
            f" • Админы: {stats['admin']}\n"
            f" • Клиенты: {stats['user']}\n"
            f" • Мастера: {stats['master']}"
        )

    elif stat_type == "appointments":
        stats = await get_appointment_statistics()
        text += (
            f"🗓️ <b>ЗАПИСИ</b>\n"
            f"Всего: {stats['total']}\n"
            f"За год: {stats['year']}\n"
            f"За месяц: {stats['month']}\n"
            f"Сегодня: {stats['today']}\n\n"
            f"Топ-3 загруженных дня:\n"
        )
        if stats["top_days"]:
            for i, (d, cnt) in enumerate(stats["top_days"], 1):
                text += f" {i}. {d.strftime('%d.%m.%Y')} — {cnt} записей\n"
        else:
            text += " Нет данных\n"

    elif stat_type == "orders":
        stats = await get_order_statistics()
        text += (
            f"🛠️ <b>ЗАКАЗЫ</b>\n"
            f"Активных: {stats['active']}\n"
            f"Закрыто всего: {stats['closed_total']}\n"
            f"За год: {stats['closed_year']}\n"
            f"За месяц: {stats['closed_month']}\n"
            f"Сегодня: {stats['closed_today']}\n"
            f"Среднее в день: {stats['avg_per_day']}"
        )

    elif stat_type == "clients":
        stats = await get_top_clients_statistics()
        clients = stats["clients"]
        if not clients:
            text += "📭 Нет клиентов с закрытыми заказами."
        else:
            text += "🏆 <b>ТОП-10 КЛИЕНТОВ</b> (по закрытым заказам):\n"
            for i, c in enumerate(clients, 1):
                text += (
                    f"\n{i}. {c['user_name']} ⭐{c['rating']}\n"
                    f"   🚗 {c['brand_auto']} {c['model_auto']} ({c['year_auto']})\n"
                    f"   📦 Закрыто заказов: {c['closed_orders']}"
                )

    elif stat_type == "masters":
        stats = await get_top_masters_statistics()
        masters = stats["masters"]
        if not masters:
            text += "📭 Нет мастеров с закрытыми заказами."
        else:
            text += "👨‍🔧 <b>МАСТЕРА</b> (по убыванию закрытых заказов):\n"
            for i, m in enumerate(masters, 1):
                text += f"\n{i}. {m['user_name']} ⭐{m['rating']} — {m['closed_orders']} заказов"

    else:
        text = "❌ Неизвестный тип статистики"

    await call.message.edit_text(
        text,
        reply_markup=kb.admin_action_menu([14, 15, 16, 18, 19, 3]),
        parse_mode="HTML"
    )
    await call.answer()


# ==============================
# АДМИН. РАССЫЛКА
# ==============================
class BroadcastState(StatesGroup):
    waiting_content = State()


@router.callback_query(F.data == "broadcast")
async def start_broadcast(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        "📢 <b>РАССЫЛКА</b>\n\n"
        "Пожалуйста, отправьте сообщение, которое хотите разослать всем пользователям.\n"
        "Поддерживаются: текст, фото, видео, документы.\n\n"
        "⚠️ Внимание: после подтверждения отмена невозможна.",
        reply_markup=kb.admin_action_menu([3])
    )
    await state.set_state(BroadcastState.waiting_content)
    await call.answer()


# Приём контента
@router.message(BroadcastState.waiting_content)
async def receive_broadcast_content(message: Message, state: FSMContext):
    # Сохраняем тип и данные сообщения
    content = {
        "type": message.content_type,
        "text": message.text or message.caption,
        "media_file_id": None
    }

    if message.content_type == "photo":
        content["media_file_id"] = message.photo[-1].file_id
    elif message.content_type in ("video", "document"):
        content["media_file_id"] = getattr(message, message.content_type).file_id

    await state.update_data(broadcast_content=content)

    # Формируем предпросмотр
    preview_text = content["text"] or "Без текста"
    await message.answer(
        f"👀 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n{preview_text}",
        reply_markup=kb.admin_action_menu([17, 4]),
        parse_mode="HTML"
    )
    # Если есть медиа — отправляем его отдельно

    media_msg = None

    if content["media_file_id"]:
        if message.content_type == "photo":
            media_msg = await message.answer_photo(content["media_file_id"], caption=preview_text)
        elif message.content_type == "video":
            media_msg = await message.answer_video(content["media_file_id"], caption=preview_text)
        elif message.content_type == "document":
            media_msg = await message.answer_document(content["media_file_id"], caption=preview_text)

    # Сохраняем ID сообщений для последующего удаления
    message_ids = [message.message_id]
    if media_msg:
        message_ids.append(media_msg.message_id)

    await state.update_data(broadcast_message_ids=message_ids)


# Подтверждение
@router.callback_query(F.data == "broadcast_confirm")
async def confirm_broadcast(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    content = data.get("broadcast_content")
    if not content:
        await call.answer("❌ Нет данных для рассылки", show_alert=True)
        return

    # Получаем ID сообщений для удаления (предпросмотр и исходное сообщение)
    mess_ids = data.get("broadcast_message_ids", [])

    # Получаем всех активных пользователей
    user_ids = await get_all_active_user_ids()

    status_msg = await call.message.edit_text("📤 Рассылка запущена... Это может занять время.")

    # Добавляем в общий список с id сообщений для удаления
    mess_ids.append(status_msg.message_id)

    success, failed = 0, 0
    for user_id in user_ids:
        try:
            if content["type"] == "text":
                await call.bot.send_message(user_id, content["text"], parse_mode="HTML")
            elif content["type"] == "photo":
                await call.bot.send_photo(user_id, content["media_file_id"], caption=content["text"])
            elif content["type"] == "video":
                await call.bot.send_video(user_id, content["media_file_id"], caption=content["text"])
            elif content["type"] == "document":
                await call.bot.send_document(user_id, content["media_file_id"], caption=content["text"])
            success += 1
        except Exception as e:
            failed += 1
            # Логируй ошибку
            logging.warning(f"Failed to send to {user_id}: {e}")

    await call.answer(
        f"✅ Рассылка завершена!\n"
        f"Успешно: {success}\n"
        f"Ошибок: {failed}",
        show_alert=True
    )

    # Удаляем все ненужные сообщения
    if mess_ids:
        _ = asyncio.create_task(message_deleter(bot=bot, chat_id=call.message.chat.id, message_ids=mess_ids))

    await state.clear()


@router.callback_query(F.data == "admin_back_main_menu")
async def back_to_main_menu(call: CallbackQuery):
    """Возвращает мастера в основное меню."""
    text = (
        "📁 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>\n\n"
        "Управляйте пользователями, мастерами, записями и настройками сервиса.\n\n"
        "Выберите действие ниже 👇"
    )

    await call.message.edit_text(
        text=text,
        reply_markup=kb.admin_menu()
    )
    await call.answer()


# ===========================
# ========= МАСТЕР ==========
# ===========================

# ЛИЧНЫЙ КАБИНЕТ МАСТЕРА
@router.callback_query(F.data == "master_account")
async def account_menu(call: CallbackQuery) -> None:
    """Открывает меню личного кабинета мастера."""

    await call.message.edit_text(
        text="📁 <b>ЛИЧНЫЙ КАБИНЕТ МАСТЕРА</b>\n\n"
             "Здесь вы можете посмотреть и изменить свои контактные данные а "
             "также настроить получение уведомлений от клиентов\n",
        reply_markup=kb.master_personal_account()
    )
    await call.answer()


@router.callback_query(F.data == "master_back_main_menu")
async def back_to_main_menu(call: CallbackQuery):
    """Возвращает мастера в основное меню."""
    menu_text = (
        "📁 <b>ГЛАВНОЕ МЕНЮ</b>\n\n"
        "Принимайте заявки на ремонт, управляйте записями клиентов, отвечайте на вопросы.\n\n"
        "Выберите нужный раздел ниже 👇"
    )

    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.master_menu()
    )
    await call.answer()


# "МОИ ДАННЫЕ" МАСТЕР
@router.callback_query(F.data == "master_login")
async def show_master_data(call: CallbackQuery) -> None:
    user_tg_id = call.from_user.id
    user_data = await get_user_dict(
        tg_id=user_tg_id,
        fields=["user_name", "rating", "contact", "role", "status", "can_messages"]
    )

    user_role = user_data["role"]

    if user_role == "master":

        can_mess = "ВКЛ" if user_data['can_messages'] else "ВЫКЛ"

        text = (
            "Здесь отображены ваши актуальные регистрационные данные, рейтинг который увеличивается "
            "и зависит от оценок клиентов. Если сообщения: Включены - вы всегда получаете рассылку новых "
            "клиентов, Выключены - получаете только адресованные вам.\n\n"
            f"👤 Имя: {user_data['user_name']}\n"
            f"📱 Телеграм: {user_tg_id}\n"
            f"📞 Контактный номер: {user_data['contact']}\n"
            f"⭐ Рейтинг: {user_data['rating']}\n"
            f"🔸 Должность: {user_data['status']}\n"
            f"✉️ Сообщения: {can_mess}\n"
        )

        await call.message.edit_text(
            text=text,
            reply_markup=kb.master_edit_profile()
        )

    else:
        await call.answer("❌ Ошибка загрузки данных!", show_alert=True)


@router.callback_query(F.data == "master_back_personal_account")
async def master_back_to_personal_account(call: CallbackQuery, state: FSMContext):
    """Возвращает мастера в 'ЛИЧНЫЙ КАБИНЕТ'"""
    await call.message.edit_text(
        text="📁 <b>ЛИЧНЫЙ КАБИНЕТ МАСТЕРА</b>\n\n"
             "Здесь вы можете посмотреть и изменить свои контактные данные а "
             "также настроить получение уведомлений от клиентов\n",
        reply_markup=kb.master_personal_account()
    )
    await state.clear()
    await call.answer()


# ==============================
# РЕДАКТИРОВАНИЕ ПРОФИЛЯ МАСТЕРА
# ==============================
@router.callback_query(F.data == "master_edit_menu")
async def master_edit_menu(call: CallbackQuery, state: FSMContext) -> None:
    """Открывает меню редактирования данных мастера с динамической кнопкой уведомлений."""
    user_id = call.from_user.id
    user_data = await get_user_dict(tg_id=user_id, fields=["can_messages"])
    if not user_data:
        await call.answer("❌ Не удалось загрузить данные профиля.", show_alert=True)
        return

    can_mess = user_data.get("can_messages", False)

    # Выбираем набор индексов в зависимости от can_mess
    if can_mess:
        menu_indx = [1, 2, 10, 4]  # "Отключить сообщения"
    else:
        menu_indx = [1, 2, 3, 4]   # "Включить сообщения"

    prompt_msg = await call.message.answer(
        "Выберите данные для изменения или дополнения:",
        reply_markup=kb.staff_menu(menu_indx)
    )
    await state.update_data(edit_message_ids=[prompt_msg.message_id])
    await call.answer()


@router.callback_query(F.data.startswith("master_edit:"))
async def start_edit_field(call: CallbackQuery, state: FSMContext) -> None:
    """Редактирование выбранного поля. Для can_messages — сразу переключаем, для остальных — запрашиваем ввод."""
    action = call.data.split(":", 1)[1]
    user_id = call.from_user.id

    # Обработка переключения can_messages
    if action == "can_mess_on":
        await update_user(user_id, "can_messages", True)
        await call.answer("✅ Уведомления включены.", show_alert=True)
        # Удаляем сообщение с меню
        try:
            await call.message.delete()
        except TelegramAPIError:
            pass

        return

    elif action == "can_mess_off":
        await update_user(user_id, "can_messages", False)
        await call.answer("✅ Уведомления отключены.", show_alert=True)
        try:
            await call.message.delete()
        except TelegramAPIError:
            pass

        return

    # Обработка текстовых полей
    field_map = {
        "user_name": "Имя",
        "contact": "Контактный номер"
    }

    if action not in field_map:
        await call.answer("❌ Неизвестное поле.", show_alert=True)
        return

    await state.update_data(data_type=action)

    input_msg = await call.message.edit_text(
        f"Введите {field_map[action]} (до 20 символов):",
        reply_markup=kb.staff_menu([4])
    )

    data = await state.get_data()
    message_ids = data.get("edit_message_ids", [])
    message_ids.append(input_msg.message_id)
    await state.update_data(edit_message_ids=message_ids)
    await state.set_state(EditProfile.edit_profile_master)
    await call.answer()


@router.message(EditProfile.edit_profile_master)
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
        await call.answer(f"❌ Нет записей.", show_alert=True)
        return

    # Удаляем сообщение с выбором периода
    await call.message.delete()

    # Отправляем КАЖДУЮ запись как ОТДЕЛЬНОЕ сообщение
    for appt in appointments:
        date_str = appt["appointment_date"].strftime("%d.%m.%Y")
        start_time = appt["appointment_time"].strftime("%H:%M")
        end_time = appt["end_time"].strftime("%H:%M")

        user_data = await get_user_dict(tg_id=appt["tg_id_user"], fields=["user_name", "contact"])
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

    # Получаем имя мастера
    user_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name"])
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
             f"👤 Имя: {master_name} \n"
             f"📱 Телеграм: {master_tg_id}\n\n"
             f"{greeting} Вы записаны на приём!\n"
             f"📆 Дата: {date_str}\n"
             f"🕑 Время: {time_str}\n\n"
             f"Для удобства нажмите вариант ответа или введите текстом.",
        reply_markup=kb.get_accept_work_keyboard([6, 7, 8, 9, 5], master_tg_id=master_tg_id)
    )

    await call.answer(f"✅ Напоминание отправлено!", show_alert=True)


# ПЕРЕНЕСТИ ВСТРЕЧУ
@router.callback_query(F.data.startswith("transfer_app:"))
async def handle_transfer_mess(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки 'Перенести встречу'.
    Перенаправляет в уже существующий FSM-поток записи (как при set_time).
    """
    try:
        user_tg_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID клиента.", show_alert=True)
        return

    # Сохраняем целевого пользователя
    user_data = await get_user_dict(tg_id=user_tg_id, fields=["user_name"])
    user_name = user_data["user_name"]

    await state.update_data(target_user_id=user_tg_id, user_name=user_name)

    await call.message.answer(
        "Выберите вариант:",
        reply_markup=kb.master_menu_app([6, 7, 8], user_id=user_tg_id)
    )

    # Переключаемся в уже существующее состояние
    await state.set_state(AppointmentStates.choosing_option)
    await call.answer()


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
        f"🆔 ID заказа: {order_id}\n",
        reply_markup=kb.quick_action_menu()
    )
    await state.set_state(MasterOrderActions.choosing_action)
    await call.answer()


# ВЫБОР: "МОЖЕТЕ ЗАБИРАТЬ"
@router.callback_query(MasterOrderActions.choosing_action, F.data == "quick:answer")
async def send_quick_pickup(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    client_tg_id = data["client_tg_id"]
    order_id = data["order_id"]
    master_tg_id = data["master_tg_id"]

    # Получаем имя мастера
    user_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name"])
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
        text=f"💬 Сообщение от мастера\n"
             f"👤 Имя: {master_name} \n"
             f"📱 Телеграм ID: {master_tg_id}\n\n"
             f"✅ Можете принимать работу и забирать автомобиль! 🔑\n\n",
        reply_markup=kb.get_accept_work_keyboard(
            [1, 3, 4, 5],  # Кнопка "Принять работу", "Какая цена?", "Сообщение", "Скрыть"
            order_id=order_id,
            master_tg_id=master_tg_id)
    )

    await call.answer("✅ Сообщение «Можете забирать» отправлено клиенту.", show_alert=True)
    await state.clear()
    await call.message.delete()


# ВЫБОР "ОТПРАВИТЬ СООБЩЕНИЕ"
@router.callback_query(F.data.startswith("send_mess:"))
async def request_custom_message(call: CallbackQuery, state: FSMContext):
    """
    Обрабатывает нажатие кнопки 'Отправить сообщение' из меню заказа.
    Запрашивает текст сообщения у мастера.
    """
    try:
        client_tg_id = int(call.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await call.answer("❌ Некорректный ID клиента.", show_alert=True)
        return

    master_tg_id = call.from_user.id

    # Сохраняем данные в FSM
    await state.update_data(
        client_tg_id=client_tg_id,
        master_tg_id=master_tg_id
    )

    # Отправляем запрос на ввод и сохраняем его ID
    prompt_msg = await call.message.answer("✍️ Введите сообщение для клиента:")
    await state.update_data(temp_message_ids=[prompt_msg.message_id])

    await state.set_state(MasterOrderMess.order_send_mess)
    await call.answer()


# РОУТЕР: ловит текст от мастера и отправляет клиенту
@router.message(MasterOrderMess.order_send_mess)
async def send_custom_message_to_client(message: Message, state: FSMContext):
    data = await state.get_data()
    client_tg_id = data["client_tg_id"]
    master_tg_id = data["master_tg_id"]

    user_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name"])
    master_name = user_data["user_name"]

    # Отправляем сообщение клиенту
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"💬 Сообщение от мастера\n\n"
             f"👤 Имя: {master_name}\n"
             f"📱 Телеграм: {master_tg_id}\n\n"
             f"{message.text}",
        reply_markup=kb.master_menu_app([17, 19], master_tg_id)
    )

    # Подтверждение мастеру
    success_msg = await message.answer("✅ Ваше сообщение отправлено клиенту.")

    # Собираем все ID сообщений для удаления
    temp_ids = data.get("temp_message_ids", [])
    temp_ids.extend([message.message_id, success_msg.message_id])

    # Удаляем дубликаты и None (на всякий случай)
    temp_ids = list(set(msg_id for msg_id in temp_ids if msg_id))

    # Запускаем отложенное удаление
    if temp_ids:
        _ = asyncio.create_task(
            message_deleter(
                bot=bot,
                chat_id=message.chat.id,
                message_ids=temp_ids
            )
        )

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

    # Удаляем сообщение пользователя
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


# УДАЛИТЬ ЗАКАЗ
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


@router.callback_query(F.data == "work_history")
async def master_closed_orders(call: CallbackQuery):
    master_id = call.from_user.id
    # Получаем ЗАКРЫТЫЕ заказы (active=False)
    orders = await get_orders_by_user(tg_id_master=master_id, active=False)

    if not orders:
        await call.answer("❌ У вас нет закрытых заказов.", show_alert=True)
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
                reply_markup=kb.master_order_action_menu([7, 8], order_id, tg_id_user)
            )

    await call.answer()


# ===========================
# ВЗАИМОДЕЙСТВИЕ С КЛИЕНТОМ
# ===========================


# === ОЖИДАНИЕ ===
@router.callback_query(F.data.startswith("await:"))
async def handle_await_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])

    response_text = "⌚️ В данный момент занят. Отвечу, как только освобожусь!"
    await bot.send_message(chat_id=user_id, text=response_text, reply_markup=kb.common_menu([4]))
    await call.answer("✅ Ответ «Ожидание» отправлен пользователю.", show_alert=True)


# === ОТКАЗ ===
@router.callback_query(F.data.startswith("refuse:"))
async def handle_refuse_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    response_text = f"😔 Извините, но к сожалению не сможем помочь с этой проблемой."
    await bot.send_message(chat_id=user_id, text=response_text, reply_markup=kb.common_menu([4]))
    await call.answer("✅ Ответ «Отказ» отправлен пользователю.", show_alert=True)


# === ЗВОНИТЕ ===
@router.callback_query(F.data.startswith("call:"))
async def handle_call_action(call: CallbackQuery):
    parts = call.data.split(":", 1)
    user_id = int(parts[1])
    master_tg_id = call.from_user.id

    user_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name", "contact"])
    master_name = user_data["user_name"]
    master_contact = user_data["contact"]

    response_text = (f'🔔 Звоните по номеру!\n'
                     f'👤 Имя: {master_name}\n'
                     f'📞 Сот. тел.: <a href="tel:{master_contact}">{master_contact}</a>')

    await bot.send_message(chat_id=user_id, text=response_text, parse_mode="HTML", reply_markup=kb.common_menu([4]))
    await call.answer("✅ Ответ «Звоните» отправлен пользователю.", show_alert=True)


# === УТОЧНИТЬ УДОБНОЕ ВРЕМЯ ===
@router.callback_query(F.data.startswith("check_time:"))
async def handle_check_time_action(call: CallbackQuery):

    # Извлекаем tg_id клиента
    client_tg_id = int(call.data.split(":", 1)[1])
    master_tg_id = call.from_user.id

    user_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name"])
    master_name = user_data["user_name"] if user_data else "—"
    greeting = await get_greeting()

    # Отправляем клиенту сообщение с уточнением
    await bot.send_message(
        chat_id=client_tg_id,
        text=f"💬 Сообщение от мастера:\n"
             f"👤 Имя: {master_name} \n"
             f"📱 Телеграм: {master_tg_id}\n\n"
             f"{greeting} Напишите удобную дату и время для того чтобы я вас записал!",
        reply_markup=kb.master_menu_app([17, 19], master_tg_id)
    )

    # Подтверждаем мастеру
    await call.answer("✅ Уточняющий вопрос по времени отправлен клиенту.", show_alert=True)


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

    if await has_active_appointment(user_id):
        await call.answer("❌ Клиент уже записан на приём.", show_alert=True)
        return

    user_data = await get_user_dict(tg_id=user_id, fields=["user_name"])
    user_name = user_data["user_name"] if user_data else "—"

    await state.update_data(target_user_id=user_id, user_name=user_name)

    await call.message.answer(
        "Выберите вариант записи:",
        reply_markup=kb.master_menu_app([6, 7, 8], user_id=user_id)
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
            reply_markup=kb.master_menu_app([8], user_id=user_id)
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
            reply_markup=kb.master_menu_app([8], user_id=user_id)
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
    user_data = await get_user_dict(tg_id=master_tg_id, fields=["user_name", "contact"])
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
        reply_markup=kb.master_menu_app([16, 8], master_tg_id)
    )

    await call.answer("✅ Форма отправлена пользователю!", show_alert=True)
    await call.message.delete()
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

    # Инициализируем список временных сообщений
    await state.update_data(
        client_tg_id=client_tg_id,
        master_tg_id=master_tg_id,
        temp_message_ids=[]
    )

    if action == "custom":
        prompt_msg = await call.message.answer("Введите описание работ (до 100 символов):")
        # Добавляем ID запроса в список
        await state.update_data(temp_message_ids=[prompt_msg.message_id])
        await state.set_state(RepairOrderStates.entering_description)
    else:
        description = TYPE_DESCRIPTIONS.get(action, "Ремонт")
        msg = await call.message.answer(
            f"Описание работ: {description}",
            reply_markup=kb.master_menu_app([15, 19], client_tg_id)
        )
        # Добавляем ID сообщения с описанием
        await state.update_data(
            description=description,
            temp_message_ids=[msg.message_id]
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
    temp_ids = data.get("temp_message_ids", [])

    # Добавляем ID сообщения пользователя
    temp_ids.append(message.message_id)

    await state.update_data(description=text)

    msg = await message.answer(
        f"Описание работ: {text}",
        reply_markup=kb.master_menu_app([15, 19], client_tg_id),
    )
    # Добавляем ID сообщения с описанием
    temp_ids.append(msg.message_id)
    await state.update_data(temp_message_ids=temp_ids)
    await state.set_state(RepairOrderStates.confirming)


@router.callback_query(RepairOrderStates.confirming, F.data.startswith("create_order:"))
async def create_repair_order(call: CallbackQuery, state: FSMContext):
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

    client_fields = ["user_name", "contact", "brand_auto", "model_auto", "gos_num", "year_auto", "vin_number"]
    master_fields = ["user_name", "contact"]

    client_data = await get_user_dict(tg_id=client_tg_id, fields=client_fields)
    master_data = await get_user_dict(tg_id=master_tg_id, fields=master_fields)

    if not client_data or not master_data:
        await call.answer("❌ Пользователь не найден", show_alert=True)
        await state.clear()
        return

    active_order_id = await get_active_order_id(client_tg_id, master_tg_id)
    if active_order_id is not None:
        await call.answer(f"❌ Уже есть активная заявка №{active_order_id}!", show_alert=True)
        await state.clear()
        return

    # Удаляем запись, если она существует
    app_data = await get_appointment_by_users(client_tg_id, master_tg_id)
    if app_data:
        await delete_appointment(app_data.id)
        res_text = (f"✅ Запись {app_data.appointment_date.strftime('%d.%m.%Y')} "
                    f"{app_data.appointment_time.strftime('%H:%M')} удалена!")
    else:
        res_text = "ℹ️ Запись не найдена."

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

    # Отправка клиенту
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
        reply_markup=kb.common_menu([4])
    )

    await call.answer(f"✅ Вы приняли в ремонт автомобиль. Заявка на ремонт создана!\n{res_text}", show_alert=True)

    # Удаляем все накопленные временные сообщения
    temp_ids = data.get("temp_message_ids", [])
    if temp_ids:
        _ = asyncio.create_task(
            message_deleter(
                bot=call.bot,
                chat_id=call.message.chat.id,
                message_ids=temp_ids
            )
        )

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
@router.callback_query(F.data == "diagnostic")
async def cmd_diagnostic(call: CallbackQuery) -> None:
    menu_text = (
        "📁 <b>ДИАГНОСТИКА</b>\n\n"
        "Расшифровка ошибок DTC через внешний API, ручное добавление DTC-кодов в базу данных, "
        "фильтрация ошибок (HIGH — из API, LOW — введённые вручную) и история запросов к API."
    )

    await call.message.edit_text(
        text=menu_text,
        reply_markup=kb.staff_menu([5, 11, 6, 7, 8])
    )

    await call.answer()


@router.callback_query(F.data == "dtc_decoding")
async def cmd_dtc(call: CallbackQuery, state: FSMContext) -> None:
    """Запрашивает у пользователя DTC-код."""
    prompt_msg = await call.message.answer(
        text="✍️ Введите DTC (Например: P0001) и отправьте:",
        reply_markup=kb.staff_menu([4])
    )
    # Инициализируем список временных сообщений
    await state.update_data(temp_message_ids=[prompt_msg.message_id])
    await state.set_state(MasterDtcMode.in_dtc)
    await call.answer()


@router.message(MasterDtcMode.in_dtc)
async def in_dtc_text(message: Message, state: FSMContext) -> None:
    """Обрабатывает введённый DTC-код."""
    user_input = message.text.strip().upper()

    # Получаем текущий список временных сообщений (приглашение)
    data = await state.get_data()
    temp_ids = data.get("temp_message_ids", [])
    temp_ids.append(message.message_id)  # добавляем сообщение пользователя

    success = False

    # ВАЛИДАЦИЯ
    if not (len(user_input) >= 4 and user_input[0] in "PBCU" and user_input[1:].replace("X", "").isalnum()):
        error_msg = await message.answer(
            "❌ Некорректный формат кода.\n"
            "Код должен начинаться с P/B/C/U и содержать 4–5 символов.\n"
            "Примеры: <code>P0300</code>, <code>P3455</code>, <code>U1122</code>",
            parse_mode="HTML"
        )
        temp_ids.append(error_msg.message_id)
    else:
        result = await decode_obd2_code(user_input)
        if not result:
            not_found_msg = await message.answer(
                f"🔍 Код <b>{user_input}</b> не найден в базе.",
                parse_mode="HTML"
            )
            temp_ids.append(not_found_msg.message_id)
            api_logger.warning(f"Пользователь {message.from_user.id} запросил несуществующий DTC-код: {user_input}")
        else:
            definition = result["definition"]
            causes = result["cause"]
            causes_text = "\n".join(f"• {cause}" for cause in causes) if causes else "Причины не указаны."
            response = (
                f"✅ <b>Код:</b> {result['code']}\n"
                f"📝 <b>Описание:</b> {definition}\n\n"
                f"🔧 <b>Возможные причины:</b>\n{causes_text}"
            )
            # ОТПРАВЛЯЕМ РЕЗУЛЬТАТ
            await message.answer(response, parse_mode="HTML", reply_markup=kb.staff_menu([4]))

            # Сохраняем в diagnostics
            await save_api_dtc_record(
                tg_id=message.from_user.id,
                code=result['code'],
                definition=definition,
                causes=causes
            )
            success = True

    # УДАЛЯЕМ ВСЕ ВРЕМЕННЫЕ СООБЩЕНИЯ
    if temp_ids:
        _ = asyncio.create_task(
            message_deleter(
                bot=message.bot,
                chat_id=message.chat.id,
                message_ids=temp_ids
            )
        )

    await state.clear()


# ==============================
# РУЧНОЙ ВВОД DTC-КОДА
# ==============================

@router.callback_query(F.data == "manual_dtc_input")
async def cmd_manual_dtc(call: CallbackQuery, state: FSMContext):
    """Начало: выбор активного заказа для ручного ввода DTC."""
    master_tg_id = call.from_user.id
    orders = await get_orders_by_user(tg_id_master=master_tg_id, active=True)
    if not orders:
        await call.answer("❌ У вас нет активных заказов.", show_alert=True)
        return

    msg = await call.message.answer(
        "Выберите заказ для добавления неисправности:",
        reply_markup=kb.generate_order_select_buttons(orders)
    )
    await state.update_data(temp_message_ids=[msg.message_id])
    await state.set_state(MasterDtcMode.manual_select_order)
    await call.answer()


@router.callback_query(MasterDtcMode.manual_select_order, F.data.startswith("select_order:"))
async def select_order_for_manual_dtc(call: CallbackQuery, state: FSMContext):
    """Выбор заказа → сразу запрашиваем ввод DTC-кода."""
    parts = call.data.split(":")
    if len(parts) != 5:
        await call.answer("❌ Ошибка данных", show_alert=True)
        return
    order_id = int(parts[1])
    brand, model, year = parts[2], parts[3], parts[4]

    await state.update_data(
        order_id=order_id,
        brand_auto=brand,
        model_auto=model,
        year_auto=year
    )

    prompt = (
        "✍️ Введите данные <b>в одном сообщении</b> в формате:\n"
        "<code>код:описание:причина1, причина2, причина3</code>\n\n"
        "Пример:\n<code>P0171:бедная смесь:Забитые форсунки, низкое давление топлива</code>"
    )
    msg = await call.message.edit_text(prompt, parse_mode="HTML")
    await state.update_data(temp_message_ids=[msg.message_id])
    await state.set_state(MasterDtcMode.manual_input_dtc)
    await call.answer()


@router.message(MasterDtcMode.manual_input_dtc)
async def handle_manual_dtc_input(message: Message, state: FSMContext):
    """Обрабатывает ввод DTC-кода и сохраняет в diagnostics как manual_dtc."""
    user_input = message.text.strip()
    data = await state.get_data()
    temp_ids = data.get("temp_message_ids", [])
    temp_ids.append(message.message_id)
    success = False

    try:
        parts = user_input.split(":", 2)
        if len(parts) != 3:
            raise ValueError("Требуется 3 части через ':'")

        code, definition, causes_str = [p.strip() for p in parts]
        if not code or not definition:
            raise ValueError("Код или описание пусты")

        # Валидация: должен быть корректный DTC-код
        if not (len(code) >= 4 and code[0].upper() in "PBCU" and code[1:].replace("X", "").isalnum()):
            raise ValueError("Некорректный формат DTC-кода")

        causes = [c.strip() for c in causes_str.split(",") if c.strip()]
        if not causes:
            raise ValueError("Укажите хотя бы одну причину")

        # Формируем JSON в едином формате (как у API)
        issue_and_causes = json.dumps({
            "code": code,
            "definition": definition,
            "causes": causes
        }, ensure_ascii=False)

        # Извлекаем данные заказа
        brand = data["brand_auto"]
        model = data["model_auto"]
        year = data["year_auto"]
        order_id = data["order_id"]

        # Сохраняем
        await save_manual_diagnostic_record(
            tg_id=message.from_user.id,
            entry_type="manual_dtc",
            issue_and_causes=issue_and_causes,
            brand_auto=brand,
            model_auto=model,
            year_auto=year,
            order_id=order_id
        )
        success = True
        api_logger.info(f"Успешно сохранён ручной DTC-код: {code} от tg_id={message.from_user.id}")

    except Exception as e:
        api_logger.warning(f"Ошибка ручного ввода DTC: {e}")
        error_msg = await message.answer(
            "❌ Неверный формат. Используйте:\n<code>P0171:описание:причина1, причина2</code>", parse_mode="HTML")
        temp_ids.append(error_msg.message_id)

    await state.clear()

    # УДАЛЯЕМ ВСЕ ВРЕМЕННЫЕ СООБЩЕНИЯ
    if temp_ids:
        _ = asyncio.create_task(
            message_deleter(
                bot=message.bot,
                chat_id=message.chat.id,
                message_ids=temp_ids
            )
        )


@router.callback_query(F.data.startswith("view_hl:"))
async def cmd_view_hl(call: CallbackQuery):
    """Показывает выбор фильтра: HIGH или LOW."""
    action = call.data.split(":", 1)[1]  # 'st' или 'bk'

    text = (
        "📈 Выберите тип фильтрации:\n"
        "🔹 <b>HIGH</b> — ошибки из внешнего API\n"
        "🔹 <b>LOW</b> — ошибки, введённые вручную\n"
    )

    if action == "st":
        # Первый вход — добавляем новое сообщение
        await call.message.answer(
            text=text,
            parse_mode="HTML",
            reply_markup=kb.staff_menu([12, 13, 4])
        )
    elif action == "bk":
        # Возврат — редактируем текущее сообщение
        await call.message.edit_text(
            text=text,
            parse_mode="HTML",
            reply_markup=kb.staff_menu([12, 13, 4])
        )
    else:
        await call.answer("❌ Неверное действие", show_alert=True)
        return

    await call.answer()


@router.callback_query(F.data.startswith("hl:"))
async def handle_hl_filter_button(call: CallbackQuery, state: FSMContext):
    filter_type = call.data.split(":", 1)[1]
    if filter_type not in ("high", "low"):
        await call.answer("❌ Неверный фильтр", show_alert=True)
        return

    try:
        records = await get_diagnostics_by_filter(filter_type)
    except Exception as e:
        api_logger.error(f"Ошибка при фильтрации кодов DTC: {e}")
        await call.answer("❌ Ошибка при загрузке данных.", show_alert=True)
        await state.clear()
        return

    # Формируем заголовок
    title = "📈 Ошибки из внешнего API (HIGH)" if filter_type == "high" else "📉 Ошибки, введённые вручную (LOW)"

    if not records:
        response_text = f"📭 Нет записей для фильтра: {title}"
    else:
        lines = [f"<b>{title}</b> (всего: {len(records)}):"]
        for item in records:
            code = item.get("code")
            desc = item.get("definition") or item.get("description", "—")
            lines.append(f"• <b>{code}</b>: {desc}")
        response_text = "\n".join(lines)

    # Редактируем исходное сообщение (с выбором HIGH/LOW)
    await call.message.edit_text(response_text, parse_mode="HTML", reply_markup=kb.staff_menu([14]))

    await state.clear()
    await call.answer()


# ==============================
# ИСТОРИЯ API ЗАПРОСОВ
# ==============================
@router.callback_query(F.data == "history_api")
async def show_api_history(call: CallbackQuery):
    """Показывает историю всех API-запросов в формате, аналогичном расшифровке DTC."""
    try:
        records = await get_api_dtc_history()
    except Exception as e:
        api_logger.error(f"Ошибка при загрузке истории API: {e}")
        await call.answer("❌ Ошибка при загрузке истории.", show_alert=True)
        return

    if not records:
        response_text = "📭 История API-запросов пуста."
        await call.message.answer(response_text)
    else:
        blocks = []
        for rec in records:
            causes_text = "\n".join(f"• {cause}" for cause in rec["causes"]) if rec["causes"] else "Причины не указаны."
            block = (
                f"✅ <b>Код:</b> {rec['code']}\n"
                f"📝 <b>Описание:</b> {rec['definition']}\n\n"
                f"🔧 <b>Возможные причины:</b>\n{causes_text}"
            )
            blocks.append(block)
        response_text = "\n------------------------------\n".join(blocks)
        await call.message.answer(response_text, parse_mode="HTML", reply_markup=kb.staff_menu([4]))

    await call.answer()


