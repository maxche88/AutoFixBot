import os
from database.models import User
from sqlalchemy import select
from database.engine import async_session
from config import config


# Создаёт администратора при запуске, если его ещё нет в БД. Берёт tg_id из переменной окружения ADMIN_ID.
async def init_admin_user():
    admin_id_str = config.ADMIN_ID
    if not admin_id_str:
        return

    try:
        admin_tg_id = int(admin_id_str)
    except ValueError:
        return

    async with async_session() as session:
        # Проверяем, существует ли пользователь с таким tg_id
        existing = await session.execute(
            select(User).where(User.tg_id == admin_tg_id)
        )

        if existing.scalar_one_or_none():
            return

        # Создаём админа
        new_admin = User(
            tg_id=admin_tg_id,
            user_name="Администратор",
            role="admin",
            can_messages=True,
            rating=1000,
            contact="-",
            brand_auto="-"
        )
        session.add(new_admin)
        await session.commit()
        print(f"Администратор с tg_id={admin_tg_id} успешно создан!")
