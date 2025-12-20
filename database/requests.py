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
from config import config


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


# ==============================
# КОММЕНТАРИИ
# ==============================
async def add_comment(data: Dict[str, Any]) -> None:
    """
    Добавляет отзыв (комментарий) от пользователя.

    :param data: Словарь с полями модели Comments (tg_id, user_name, text).
    """
    async with async_session() as session:
        comment_obj = Comments(**data)
        session.add(comment_obj)
        await session.commit()


async def get_visible_comments(mode: str = "user") -> List[Dict[str, Any]]:
    """
    Возвращает отзывы в зависимости от режима.

    :param mode:
        - "user" → только отзывы с is_visible=True (для клиентов),
        - "all"  → все отзывы без фильтрации (для модератора/админа).
    :return: Список словарей с данными отзывов.
    """
    async with async_session() as session:
        if mode == "all":
            # Модератор: все отзывы
            stmt = select(Comments).order_by(Comments.date.desc())
        elif mode == "user":
            # Пользователь: только разрешённые
            stmt = select(Comments).where(Comments.is_visible.is_(True)).order_by(Comments.date.desc())
        else:
            raise ValueError(f"Неизвестный режим: {mode}. Ожидались 'user' или 'all'.")

        result = await session.execute(stmt)
        comments = result.scalars().all()

        comment_list = []
        for c in comments:
            item = {
                "id": c.id,
                "tg_id": c.tg_id,
                "user_name": c.user_name,
                "text": c.text,
                "date": c.date.isoformat() if c.date else "не указана"
            }
            # Для модератора добавляем служебное поле
            if mode == "all":
                item["is_visible"] = c.is_visible
            comment_list.append(item)

        return comment_list


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
            "gos_num": user.gos_num,
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


async def get_available_hours(target_date: date):
    """
    Возвращает set свободных часов на указанную дату.
    Учитывает пересечение с существующими записями.
    Не поддерживает 30-минутные слоты, только 1 час.
    """
    async with async_session() as session:
        # Получаем все записи на указанную дату
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)

        stmt = select(Appointment).where(
            Appointment.appointment_date >= start_of_day,
            Appointment.appointment_date < end_of_day + timedelta(days=1)
        )
        result = await session.execute(stmt)
        appointments = result.scalars().all()

        occupied_hours = set()

        for appt in appointments:
            start_time = appt.appointment_time  # time, например 10:00
            end_time = appt.end_time            # time, например 11:30

            if not start_time or not end_time:
                continue

            # Преобразуем в datetime для удобства
            start_dt = datetime.combine(target_date, start_time)
            end_dt = datetime.combine(target_date, end_time)

            # Если запись переходит на следующий день (маловероятно, но защитимся)
            if end_dt <= start_dt:
                end_dt += timedelta(days=1)

            # Определяем, какие часы пересекаются с этим интервалом
            current_hour = start_dt.hour
            # Идём по часам, пока начало часа < end_dt
            while current_hour < 24:
                hour_start = datetime.combine(target_date, time(current_hour, 0))
                hour_end = hour_start + timedelta(hours=1)

                # Проверяем пересечение интервалов:
                # [start_dt, end_dt) пересекается с [hour_start, hour_end)
                if start_dt < hour_end and end_dt > hour_start:
                    occupied_hours.add(current_hour)
                else:
                    # Так как записи упорядочены по времени, можно выйти,
                    # но для надёжности — проверим все часы до 24
                    pass

                current_hour += 1
                if hour_start >= end_dt:
                    break

        # Возвращаем свободные часы
        all_possible_hours = config.DEFAULT_HOURS  # например, {9, 10, ..., 17}
        return all_possible_hours - occupied_hours


async def create_appointment(user_id: int, master_id: int, date_val: date, start_hour: float, end_hour: float) -> None:
    """
    Создаёт новую запись на приём.

    :param user_id: ID пользователя
    :param master_id: ID мастера который записал клиента
    :param date_val: Дата приёма (datetime.date)
    :param start_hour: Время начала в часах (например, 9.5 → 9:30)
    :param end_hour: Время окончания в часах (например, 11.0 → 11:00)
    """

    # Преобразуем дробные часы в (часы, минуты)
    def hour_to_time(h: float) -> time:
        hours = int(h)
        minutes = int(round((h - hours) * 60))
        # Защита от переполнения минут (например, 9.99 → 9:59.4 → 10:00)
        if minutes >= 60:
            hours += 1
            minutes -= 60
        if hours >= 24:
            hours = 23
            minutes = 59
        return time(hour=hours, minute=minutes)

    start_time = hour_to_time(start_hour)
    end_time = hour_to_time(end_hour)

    # 🔹 Создаём datetime для начала приёма
    appointment_datetime = datetime.combine(date_val, start_time)

    # 🔹 Сохраняем в БД
    async with async_session() as session:
        new_appointment = Appointment(
            tg_id_user=user_id,
            tg_id_master=master_id,
            appointment_date=appointment_datetime,
            appointment_time=start_time,
            end_time=end_time
        )
        session.add(new_appointment)
        await session.commit()


async def add_order(data: Dict[str, Any]) -> None:
    """
    Добавляет новый заказ в таблицу Orders.

    :param data: Словарь с полями модели Orders.
    """
    async with async_session() as session:
        order_obj = Orders(**data)
        session.add(order_obj)
        await session.commit()


async def get_active_order_id(tg_id_user: int, tg_id_master: int) -> Optional[int]:
    """
    Возвращает ID заказа со статусом 'in_work' между клиентом и мастером.
    Если такого заказа нет — возвращает None.
    """
    async with async_session() as session:
        stmt = select(Orders.id).where(
            Orders.tg_id_user == tg_id_user,
            Orders.tg_id_master == tg_id_master,
            Orders.repair_status == "in_work"
        )
        result = await session.execute(stmt)
        return result.scalar()  # Возвращает int или None


async def get_orders_by_user(
    tg_id_user: Optional[int] = None,
    tg_id_master: Optional[int] = None,
    active: bool = True
) -> List[Dict[str, Any]]:
    """
    Возвращает список заказов:
    - Если указан tg_id_user → заказы клиента.
    - Если указан tg_id_master → заказы мастера.
    - Можно указать оба.

    :param tg_id_user: Telegram ID клиента (опционально).
    :param tg_id_master: Telegram ID мастера (опционально).
    :param active:
        - True → заказы со статусом in_work/wait
        - False → только заказы со close.
    :return: Список словарей с данными заказов.
    :raises ValueError: если не указан ни tg_id_user, ни tg_id_master.
    """
    if tg_id_user is None and tg_id_master is None:
        raise ValueError("Укажите хотя бы один из параметров: tg_id_user или tg_id_master")

    async with async_session() as session:
        conditions = []

        if tg_id_user is not None:
            conditions.append(Orders.tg_id_user == tg_id_user)
        if tg_id_master is not None:
            conditions.append(Orders.tg_id_master == tg_id_master)

        if active:
            conditions.append(Orders.repair_status != "close")
        else:
            conditions.append(Orders.repair_status == "close")

        stmt = select(Orders).where(*conditions)
        result = await session.execute(stmt)
        orders = result.scalars().all()

        orders_list = []
        for order in orders:
            orders_list.append({
                "id": order.id,
                "tg_id_user": order.tg_id_user,
                "tg_id_master": order.tg_id_master,
                "user_name": order.user_name,
                "user_contact": order.user_contact,
                "master_name": order.master_name,
                "master_contact": order.master_contact,
                "repair_status": order.repair_status,
                "complied": order.complied,
                "description": order.description,
                "brand_auto": order.brand_auto,
                "year_auto": order.year_auto,
                "gos_num": order.gos_num,
                "vin_number": order.vin_number,
                "date": order.date.isoformat() if order.date else "не указана",
            })
        return orders_list


async def update_order(
        order_id: int,
        repair_status: str | None = None,
        complied: bool | None = None,
        description: str | None = None,
) -> bool:
    """
    Обновляет указанные поля заказа по его ID.
    Обновляются только те поля, которые переданы (не None).

    :return: True, если заказ найден и обновлён.
    """
    # Собираем только те поля, которые нужно обновить
    update_data = {}
    if repair_status is not None:
        update_data["repair_status"] = repair_status
    if complied is not None:
        update_data["complied"] = complied
    if description is not None:
        update_data["description"] = description

    if not update_data:
        return False  # Нечего обновлять

    async with async_session() as session:
        stmt = update(Orders).where(Orders.id == order_id).values(**update_data)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0
