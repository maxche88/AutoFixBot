"""
Модуль работы с базой данных: CRUD-операции и бизнес-логика.

Использует асинхронный движок SQLAlchemy.
Все функции асинхронные и работают через session-обёртку.
"""

from database.models import User, Comments, Orders, Appointment
from database.engine import async_session
from sqlalchemy import update, select, delete
from datetime import datetime, timedelta, date, time
from typing import Optional, Union, Tuple, List, Dict, Any
from config import DEFAULT_HOURS


def connection(func):
    """
    Декоратор для автоматического управления сессией базы данных.

    Оборачивает функцию, открывает асинхронную сессию,
    передаёт её первым аргументом и автоматически закрывает после выполнения.
    """
    async def wrapper(*args, **kwargs):
        async with async_session() as session:
            return await func(session, *args, **kwargs)
    return wrapper


@connection
async def set_user(session, tg_id: int) -> None:
    """
    Создаёт минимальную запись пользователя, если он ещё не существует.
    Используется при первом взаимодействии с ботом, до полной регистрации.
    """
    existing_user = await session.scalar(select(User).where(User.tg_id == tg_id))
    if not existing_user:
        session.add(User(tg_id=tg_id))
        await session.commit()


async def get_user_role(user_id: int) -> Optional[str]:
    """
    Возвращает роль пользователя по его Telegram ID.

    :param user_id: Telegram ID пользователя.
    :return: Строка роли ('user', 'master', 'admin') или None, если пользователь не найден.
    """
    async with async_session() as session:
        result = await session.execute(select(User.role).where(User.tg_id == user_id))
        return result.scalar()


async def add_user(data: Dict[str, Any]) -> None:
    """
    Добавляет нового пользователя в базу данных.

    :param data: Словарь с полями модели User (например, tg_id, user_name, contact и т.д.).
    """
    async with async_session() as session:
        user_obj = User(**data)
        session.add(user_obj)
        await session.commit()


async def add_comment(data: Dict[str, Any]) -> None:
    """
    Добавляет отзыв (комментарий) от пользователя.

    :param data: Словарь с полями модели Comments (tg_id, user_name, text).
    """
    async with async_session() as session:
        comment_obj = Comments(**data)
        session.add(comment_obj)
        await session.commit()


async def add_grade(user_id: int, rate: int) -> None:
    """
    Увеличивает рейтинг пользователя (мастера) на указанное значение.

    :param user_id: Telegram ID мастера.
    :param rate: Число, на которое увеличивается рейтинг (обычно 1–5).
    """
    async with async_session() as session:
        stmt = update(User).where(User.tg_id == user_id).values(rating=User.rating + rate)
        await session.execute(stmt)
        await session.commit()


async def all_orders_by_user(tg_id_user: int) -> List[Dict[str, Any]]:
    """
    Возвращает список активных заказов пользователя.

    :param tg_id_user: Telegram ID клиента.
    :return: Список словарей с полями: id, tg_id_master, master_name, repair_status, complied.
    """
    async with async_session() as session:
        stmt = select(
            Orders.id,
            Orders.tg_id_master,
            Orders.master_name,
            Orders.repair_status,
            Orders.complied
        ).where(Orders.tg_id_user == tg_id_user)

        result = await session.execute(stmt)
        return [
            {
                "id": row.id,
                "tg_id_master": row.tg_id_master,
                "master_name": row.master_name,
                "repair_status": row.repair_status,
                "complied": row.complied
            }
            for row in result.all()
        ]


async def load_order(tg_id_user: int) -> Optional[Orders]:
    """
    Возвращает первый (единственный актуальный) заказ пользователя.
    Предполагается, что у пользователя одновременно может быть только один активный заказ.
    """
    async with async_session() as session:
        stmt = select(Orders).where(Orders.tg_id_user == tg_id_user)
        result = await session.execute(stmt)
        return result.scalars().first()


async def count_and_name_gen(orders_list: List[Dict[str, Any]]) -> Tuple[int, List[Tuple[str, int, int]]]:
    """
    Преобразует список заказов в данные для генерации кнопок с именами мастеров.

    :param orders_list: Список заказов, возвращённый из all_orders_by_user.
    :return: Кортеж: (количество, список кортежей (имя_мастера, tg_id_мастера, id_заказа)).
    """
    count = len(orders_list)
    master_data = [
        (order["master_name"], order["tg_id_master"], order["id"])
        for order in orders_list
    ]
    return count, master_data


async def delete_order(order_id: int) -> None:
    """
    Удаляет заказ по его идентификатору.
    Используется при закрытии заказа клиентом (после оценки).
    """
    async with async_session() as session:
        stmt = delete(Orders).where(Orders.id == order_id)
        await session.execute(stmt)
        await session.commit()


async def get_user_dict(tg_id: int, fields: Optional[Tuple[str, ...]] = None) -> Union[Dict[str, Any], Tuple, None]:
    """
    Возвращает данные пользователя по его Telegram ID.

    :param tg_id: Telegram ID пользователя.
    :param fields: Необязательный кортеж имён полей (например, ('user_name', 'contact')).
                   Если указан — возвращает кортеж значений в том же порядке.
                   Если не указан — возвращает полный словарь данных.
    :return: Словарь всех полей, кортеж значений или None, если пользователь не найден.
    """
    async with async_session() as session:
        stmt = select(User).where(User.tg_id == tg_id)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            return None

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

        if fields:
            return tuple(user_dict.get(field) for field in fields)
        return user_dict


async def update_user(tg_id: int, column: str, value: Any) -> bool:
    """
    Обновляет одно поле пользователя по его Telegram ID.

    :param tg_id: Telegram ID пользователя.
    :param column: Имя колонки модели User (например, 'contact', 'brand_auto').
    :param value: Новое значение.
    :return: True при успехе, None если колонка не существует.
    """
    if not hasattr(User, column):
        return False

    async with async_session() as session:
        stmt = update(User).where(User.tg_id == tg_id).values({column: value})
        await session.execute(stmt)
        await session.commit()
        return True


async def can_mess_true() -> List[int]:
    """
    Возвращает список Telegram ID пользователей, которым разрешено получать уведомления.
    Используется для рассылки сообщений от клиентов (мастерам/админам).
    """
    async with async_session() as session:
        stmt = select(User.tg_id).where(User.can_messages.is_(True))
        result = await session.execute(stmt)
        return result.scalars().all()


async def get_occupied_hours(target_date: date) -> List[int]:
    """
    Возвращает список свободных часов на указанную дату.
    Анализирует все записи в таблице Appointment и исключает занятые часы.
    Каждая запись может занимать более одного часа (например, с 9:00 до 11:00 → заняты 9 и 10).

    :param target_date: Дата (datetime.date).
    :return: Список свободных часов (например, [9, 10, 14, 15]).
    """
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
            if not appt.appointment_time or not appt.end_time:
                continue

            # Начало и длительность записи
            start_dt = datetime.combine(target_date, appt.appointment_time)
            # Обрабатываем end_time как длительность
            end_dt = datetime.combine(target_date, appt.end_time)

            # Если запись переходит на следующий день — ограничиваем текущим днём
            if end_dt.date() > target_date:
                end_dt = datetime.combine(target_date, time(23, 59))

            # Помечаем все часы от начала до конца как занятые
            current = start_dt
            while current < end_dt:
                occupied_hours.add(current.hour)
                current += timedelta(hours=1)

        free_hours = sorted(DEFAULT_HOURS - occupied_hours)
        return free_hours


async def create_appointment(user_id: int, date_val: date, hour: int) -> None:
    """
    Создаёт новую запись на приём.
    Запись длится 1 час: с `hour:00` до `(hour+1):00`.

    :param user_id: Telegram ID пользователя (в текущей реализации не используется, но зарезервировано).
    :param date_val: Дата приёма (datetime.date).
    :param hour: Час начала (например, 9 → запись с 9:00 до 10:00).
    """
    start_time = time(hour=hour, minute=0)
    end_time = time(hour=min(hour + 1, 23), minute=0)  # Ограничение: не позже 23:00

    appointment_datetime = datetime.combine(date_val, start_time)

    async with async_session() as session:
        new_appointment = Appointment(
            appointment_date=appointment_datetime,
            appointment_time=start_time,
            end_time=end_time
        )
        session.add(new_appointment)
        await session.commit()