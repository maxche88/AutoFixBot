from database.requests import get_user_dict
from keybords import keybords as kb
from aiogram.types import InlineKeyboardMarkup


async def render_master_profile(tg_id: int) -> tuple[str, InlineKeyboardMarkup]:
    """Возвращает (текст, клавиатура) для профиля мастера."""
    user_data = await get_user_dict(
        tg_id=tg_id,
        fields=["user_name", "status", "contact", "rating", "can_messages", "role", "date"]
    )
    if not user_data:
        return "❌ Мастер не найден в базе данных.", kb.admin_action_menu([4])

    name = user_data["user_name"]
    status = user_data.get("status")
    contact = user_data.get("contact")
    rating = user_data.get("rating") or 0
    can_msg = "✅ ВКЛ" if user_data.get("can_messages") else "❌ ВЫКЛ"
    role = user_data["role"]
    reg_date = user_data.get("date", "—")

    text = (
        f"👨‍🔧 <b>Профиль мастера</b>\n\n"
        f"🔹 Имя: {name}\n"
        f"🔸 Должность: {status}\n"
        f"📞 Сот.тел: {contact}\n"
        f"⭐️ Рейтинг: {rating}\n"
        f"📩 Уведомления: {can_msg}\n"
        f"🔖 Роль: {role}\n"
        f"📅 Регистрация: {reg_date}"
    )
    keyboard = kb.admin_action_menu([6, 7, 8, 9, 10, 11], tg_id=tg_id)
    return text, keyboard
