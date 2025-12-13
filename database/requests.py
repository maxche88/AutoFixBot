import os
from database.models import User, Comments, Orders, Appointment, async_session
from sqlalchemy import update, select, delete
from datetime import datetime, timedelta, date


def connection(func):
    async def wrapper(*args, **kwargs):
        async with async_session() as session:
            return await func(session, *args, **kwargs)
    return wrapper


@connection
async def set_user(session, tg_id):
    user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not user:
        session.add(User(tg_id=tg_id))
        await session.commit()


# Создаёт администратора при запуске, если его ещё нет в БД. Берёт tg_id из переменной окружения ADMIN_ID.
async def init_admin_user():
    admin_id_str = os.getenv("ADMIN_ID")
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
            rating=0,
            contact="-",
            brand_auto="-"
        )
        session.add(new_admin)
        await session.commit()
        print(f"Администратор с tg_id={admin_tg_id} успешно создан!")


# Асинхронная функция для проверки id пользователя в бд.
async def user_has_access(user_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.tg_id == user_id))
        return result.scalar() is not None


# Асинхронная функция добавления нового пользователя в бд.
async def add_user(data: dict):
    async with async_session() as session:
        user_obj = User(**data)
        session.add(user_obj)
        await session.commit()


# Асинхронная функция добавления комментария и данных об отправителе.
async def add_comment(data: dict):
    async with async_session() as session:
        comment_obj = Comments(**data)
        session.add(comment_obj)
        await session.commit()


# Функция добавляет оценку пользователю со статусом master.
async def add_grade(user_id: int, rate: int):
    async with async_session() as session:
        stmt = (update(User).where(User.tg_id == user_id).values(rating=User.rating + rate))
        await session.execute(stmt)
        await session.commit()


# Достаём данные из Orders по соответствующему id
async def all_orders_by_user(tg_id_user: int):
    async with async_session() as session:
        stmt = (
            select(
                Orders.id,
                Orders.tg_id_master,
                Orders.master_name,
                Orders.repair_status,
                Orders.complied
            ).where(Orders.tg_id_user == tg_id_user)
        )

        result = await session.execute(stmt)

        # Форматируем результат в виде списка словарей
        rows = [
            {
                "id": row.id,
                "tg_id_master": row.tg_id_master,
                "master_name": row.master_name,
                "repair_status": row.repair_status,
                "complied": row.complied
            }
            for row in result.all()
        ]

        return rows


# Достаём данные по соответствующему tg_id
async def load_order(tg_id_user: int):
    async with async_session() as session:
        stmt = select(Orders).where(Orders.tg_id_user == tg_id_user)
        result = await session.execute(stmt)
        order = result.scalars().first()
        return order


async def count_and_name_gen(lst: list) -> int and list:
    count_b = len(lst)
    res_lst_name_id = []
    for i in lst:
        item_name = i.get('master_name')
        tg_id = i.get('tg_id_master')
        master_id = i.get('id')
        res_lst_name_id.append((item_name, tg_id, master_id))
    return count_b, res_lst_name_id


# Удаление ORDER по переданному ID.
async def delete_order(order_id: int):
    async with async_session() as session:
        stmt = delete(Orders).where(Orders.id == order_id)
        await session.execute(stmt)
        await session.commit()


# Функция принимает параметр tg_id и если второго нет параметра то возвращает словарь с всеми
# ключами. Если указать второй параметр в виде кортежа со строками полей, то функция вернёт значения этих полей.
async def get_user_dict(tg_id: int, fields: tuple = None):
    async with async_session() as session:
        stmt = select(User).where(User.tg_id == tg_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

        # Формируем словарь с данными пользователя
        user_dict = {
            "id": user.id,
            "tg_id": user.tg_id,
            "user_name": user.user_name,
            "status": user.status,
            "rating": user.rating,
            "contact": user.contact,
            "brand_auto": user.brand_auto,
            "year_auto": user.year_auto,
            "vin_number": user.vin_number,
            "date": user.date.isoformat(),
        }

        # Если передали кортеж полей, выбираем конкретные значения
        if isinstance(fields, tuple):
            values = []
            for field in fields:
                value = user_dict.get(field)
                values.append(value)
            return tuple(values)
        else:
            # Если поля не указаны, возвращаем полный словарь
            return user_dict


async def update_user(tg_id: int, column: str, value):
    async with async_session() as session:
        if not hasattr(User, column):
            return None

        stmt = (
            update(User).where(User.tg_id == tg_id)
            .values({getattr(User, column): value})
        )

        await session.execute(stmt)
        await session.commit()
        return True


# Функция ищет в таблице User пользователей с can_messages True и выдаёт tg_id этого пользователя.
async def can_mess_true() -> list[int]:
    async with async_session() as session:
        stmt = select(User.tg_id).where(User.can_messages)
        result = await session.execute(stmt)
        return result.scalars().all()


DEFAULT_HOURS = set(range(8, 24))


async def get_occupied_hours(target_date: date):
    async with async_session() as session:
        start_of_day = datetime.combine(target_date, datetime.min.time())
        end_of_day = datetime.combine(target_date, datetime.max.time())

        stmt = select(Appointment).where(
            Appointment.appointment_date.between(start_of_day, end_of_day)
        )
        result = await session.execute(stmt)
        appointments = result.scalars().all()

        occupied_hours = set()

        for appt in appointments:
            start_time = appt.appointment_time  # Время записи
            duration_time = appt.end_time       # Длительность

            if not start_time or not duration_time:
                continue

            # Преобразуем начало приёма в datetime
            start_dt = datetime.combine(target_date, start_time)

            # Преобразуем длительность в timedelta
            duration = timedelta(hours=duration_time.hour, minutes=duration_time.minute)

            # Вычисляем конец приёма
            end_dt = start_dt + duration

            # Проходим по каждому часу от начала до конца
            current = start_dt
            while current < end_dt:
                occupied_hours.add(current.hour)
                current += timedelta(hours=1)

        return sorted(DEFAULT_HOURS - occupied_hours)


async def create_test_appointment():
    async with async_session() as session:
        now = datetime.now()
        appointment_date = now
        appointment_time = now.time()
        end_time = (datetime.combine(now.date(), now.time()) + timedelta(minutes=30)).time()

        new_appointment = Appointment(
            appointment_date=appointment_date,
            appointment_time=appointment_time,
            end_time=end_time
        )

        session.add(new_appointment)
        await session.commit()
