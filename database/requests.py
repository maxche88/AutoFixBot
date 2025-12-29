"""
Модуль работы с базой данных: CRUD-операции и бизнес-логика.

Использует асинхронный движок SQLAlchemy.
Все функции асинхронные и работают через session-обёртку.
"""

from database.models import User, Comments, Orders, Appointment, Diagnostics
from database.engine import async_session
from sqlalchemy import func, update, select, delete, and_
from datetime import datetime, timedelta, date, time
from typing import Optional, Tuple, List, Dict, Any
from config import Config, CarApiConfig
import json
import logging


db_logger = logging.getLogger("database")


def connection(func_):
    """
    Декоратор для автоматического управления сессией базы данных.
    Логирует любые исключения, возникшие в декорируемой функции.
    """
    async def wrapper(*args, **kwargs):
        try:
            async with async_session() as session:
                return await func_(session, *args, **kwargs)
        except Exception as e:
            # Логируем ошибку с указанием имени функции
            db_logger.error(
                f"Ошибка в функции '{func_.__name__}': {e}",
                exc_info=True
            )
            # Пробрасываем исключение дальше чтобы вызывающий код мог реагировать.
            raise
    return wrapper


# ==============================
# USER
# ==============================
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


@connection
async def add_user(session, data: Dict[str, Any]) -> None:
    user_obj = User(**data)
    session.add(user_obj)
    await session.commit()


@connection
async def get_user_role(session, user_id: int) -> Optional[str]:
    result = await session.execute(select(User.role).where(User.tg_id == user_id))
    return result.scalar()


@connection
async def update_user_by_id(session, uid: int, **kwargs) -> bool:
    """
    Универсально обновляет поля пользователя по его внутреннему ID (users.id).
    Примеры:
        await update_user_by_id(123, role="master")
        await update_user_by_id(123, role="blocked", status="Заблокирован")
    Возвращает True при успехе, False — если пользователь не найден.
    """
    user = await session.scalar(select(User).where(User.id == uid))
    if not user:
        return False
    for key, value in kwargs.items():
        if hasattr(user, key):
            setattr(user, key, value)
        else:
            db_logger.warning(f"Попытка обновить несуществующее поле '{key}' у пользователя {uid}")
    await session.commit()
    return True


@connection
async def get_all_masters(session, exclude_tg_id: int | None = None) -> list[dict]:
    """
    Возвращает список мастеров: [{'tg_id': ..., 'user_name': ..., 'contact': ..., 'status': ...}]
    Исключает мастера с указанным tg_id (если задан).
    """
    query = select(
        User.tg_id,
        User.user_name,
        User.contact,
        User.status
    ).where(User.role == "master")

    if exclude_tg_id is not None:
        query = query.where(User.tg_id != exclude_tg_id)

    result = await session.execute(query)
    return [
        {
            "tg_id": row.tg_id,
            "user_name": row.user_name,
            "contact": row.contact,
            "status": row.status
        }
        for row in result.fetchall()
    ]


@connection
async def get_user_dict_by_id(session, uid: int) -> Optional[Dict[str, Any]]:
    """
    Возвращает словарь с данными пользователя по его внутреннему ID (users.id).
    Если пользователь не найден — возвращает None.
    """
    result = await session.execute(select(User).where(User.id == uid))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    return {
        "id": user.id,
        "tg_id": user.tg_id,
        "user_name": user.user_name,
        "status": user.status,
        "rating": user.rating,
        "contact": user.contact,
        "brand_auto": user.brand_auto,
        "model_auto": user.model_auto,
        "year_auto": user.year_auto,
        "gos_num": user.gos_num,
        "vin_number": user.vin_number,
        "total_km": user.total_km,
        "role": user.role,
        "can_messages": user.can_messages,
        "date": user.date,
    }


@connection
async def get_user_by_tg_id(session, tg_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Получает пользователя по Telegram ID, возвращая указанные поля.
    Если `fields` не указан — возвращает все поля модели User.

    Примеры:
        # Все поля
        user = await get_user_by_tg_id(123)

        # Только нужные поля
        user = await get_user_by_tg_id(123, ["user_name", "contact", "brand_auto"])

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id: Telegram ID пользователя.
    :param fields: Список имён полей для выборки (например, ["user_name", "contact"]).
                   Если None — возвращаются все поля.
    :return: Словарь с данными пользователя или None, если не найден.
    """
    allowed_columns = set(User.__table__.columns.keys())

    if fields is not None:
        valid_fields = [f for f in fields if f in allowed_columns]
        if not valid_fields:
            return None
        columns_to_select = [User.__table__.c[field] for field in valid_fields]
    else:
        columns_to_select = list(User.__table__.columns.keys)

    stmt = select(*columns_to_select).where(User.tg_id == tg_id)
    result = await session.execute(stmt)
    row = result.fetchone()

    if row is None:
        return None

    user_dict = dict(row)
    if 'date' in user_dict and user_dict['date'] is not None:
        user_dict['date'] = user_dict['date'].isoformat()

    return user_dict


@connection
async def get_user_dict(session, tg_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Получает данные пользователя из базы по его Telegram ID.

    Функция поддерживает выборку как всех полей, так и только указанных.
    Все имена полей проверяются на существование в модели User —
    опечатки или несуществующие поля игнорируются.

    Примеры:
        # Получить все поля пользователя
        user = await get_user_dict(123456789)

        # Получить только нужные поля
        user = await get_user_dict(123456789, ["user_name", "contact", "brand_auto"])

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id: Telegram ID пользователя (уникальный идентификатор).
    :param fields: Список имён колонок для выборки (например: ["user_name", "contact"]).
                   Если None — возвращаются все поля модели User.
    :return: Словарь вида {"поле": значение, ...} или None, если пользователь не найден.
    """
    allowed_columns = set(User.__table__.columns.keys())

    if fields is not None:
        valid_fields = [f for f in fields if f in allowed_columns]
        if not valid_fields:
            return None
        columns = [getattr(User, field) for field in valid_fields]
    else:
        columns = [getattr(User, col) for col in allowed_columns]

    column_names = [col.key for col in columns]
    stmt = select(*columns).where(User.tg_id == tg_id)
    result = await session.execute(stmt)
    row = result.fetchone()

    if row is None:
        return None

    return dict(zip(column_names, row))


@connection
async def update_user(session, tg_id: int, column: str, value: Any) -> bool:
    """
    Обновляет одно поле пользователя по его Telegram ID.

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id: Telegram ID пользователя.
    :param column: Имя колонки модели User (например, 'contact', 'brand_auto').
    :param value: Новое значение.
    :return: True, если пользователь найден и поле обновлено.
    """
    if not hasattr(User, column):
        return False

    stmt = update(User).where(User.tg_id == tg_id).values({column: value})
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


@connection
async def can_mess_true(session) -> List[int]:
    """
    Возвращает список Telegram ID пользователей, которым разрешено получать уведомления.
    Используется для рассылки сообщений от клиентов (мастерам/админам).

    :param session: Асинхронная сессия SQLAlchemy.
    """
    stmt = select(User.tg_id).where(User.can_messages.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()


# РЕЙТИНГ
@connection
async def add_grade(session, user_id: int, rate: int) -> None:
    """
    Увеличивает рейтинг пользователя (мастера) на указанное значение.

    :param session: Асинхронная сессия SQLAlchemy.
    :param user_id: Telegram ID мастера.
    :param rate: Число, на которое увеличивается рейтинг.
    """
    stmt = update(User).where(User.tg_id == user_id).values(rating=User.rating + rate)
    await session.execute(stmt)
    await session.commit()


@connection
async def delete_user(session, tg_id: int) -> bool:
    """
    Безопасно удаляет пользователя по Telegram ID.
    Удаление возможно только если:
      - нет активных заказов (статус != 'close'),
      - нет записей на приём,

    :param session: Асинхронная сессия SQLAlchemy (передаётся декоратором).
    :param tg_id: Telegram ID пользователя.
    :return: True, если пользователь удалён. False — если есть зависимости или пользователь не найден.
    """
    # Проверка активных заказов (как клиент, так и мастер)
    active_orders = await session.scalar(
        select(Orders.id).where(
            (Orders.tg_id_user == tg_id) | (Orders.tg_id_master == tg_id),
            Orders.repair_status != "close"
        )
    )
    if active_orders:
        return False

    # Проверка записей на приём
    appointments = await session.scalar(
        select(Appointment.id).where(
            (Appointment.tg_id_user == tg_id) | (Appointment.tg_id_master == tg_id)
        )
    )
    if appointments:
        return False

    # Удаляем пользователя
    result = await session.execute(delete(User).where(User.tg_id == tg_id))
    await session.commit()
    return result.rowcount > 0


# ==============================
# COMMENTS
# ==============================
@connection
async def add_comment(session, data: Dict[str, Any]) -> int:
    """
    Добавляет отзыв (комментарий) от пользователя.

    :param session: Асинхронная сессия SQLAlchemy.
    :param  data: Словарь с полями модели Comments (tg_id, user_name, text).
    :return: id: int
    """
    comment_obj = Comments(**data)
    session.add(comment_obj)
    await session.commit()
    await session.refresh(comment_obj)  # обновляет объект, включая id
    return comment_obj.id


@connection
async def get_visible_comments(session, mode: str = "user") -> List[Dict[str, Any]]:
    """
    Возвращает отзывы в зависимости от режима.

    :param session: Асинхронная сессия SQLAlchemy.
    :param mode:
        - "user" → только отзывы с is_visible=True (для клиентов),
        - "all"  → все отзывы без фильтрации (для модератора/админа).
    :return: Список словарей с данными отзывов.
    """
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


# ==============================
# ORDERS
# ==============================
@connection
async def all_orders_by_user(session, tg_id_user: int) -> List[Dict[str, Any]]:
    """
    Возвращает список активных заказов пользователя.

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id_user: Telegram ID клиента.
    :return: Список словарей с полями: id, tg_id_master, master_name, repair_status, complied.
    """
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


@connection
async def load_order(session, tg_id_user: int) -> Optional[Orders]:
    """
    Возвращает первый (единственный актуальный) заказ пользователя.
    Предполагается, что у пользователя одновременно может быть только один активный заказ.

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id_user: Telegram ID клиента.
    """
    stmt = select(Orders).where(Orders.tg_id_user == tg_id_user)
    result = await session.execute(stmt)
    return result.scalars().first()


@connection
async def add_order(session, data: Dict[str, Any]) -> None:
    """
    Добавляет новый заказ в таблицу Orders.

    :param session: Асинхронная сессия SQLAlchemy (передаётся декоратором).
    :param  data: Словарь с полями модели Orders.
    """
    order_obj = Orders(**data)
    session.add(order_obj)
    await session.commit()


@connection
async def get_active_order_id(session, tg_id_user: int, tg_id_master: int) -> Optional[int]:
    """
    Возвращает ID заказа со статусом 'in_work' между клиентом и мастером.
    Если такого заказа нет — возвращает None.
    """
    stmt = select(Orders.id).where(
        Orders.tg_id_user == tg_id_user,
        Orders.tg_id_master == tg_id_master,
        Orders.repair_status == "in_work"
    )
    result = await session.execute(stmt)
    return result.scalar()  # Возвращает int или None


@connection
async def get_orders_by_user(
    session,
    tg_id_user: Optional[int] = None,
    tg_id_master: Optional[int] = None,
    order_id: Optional[int] = None,
    active: bool = True
) -> List[Dict[str, Any]]:
    """
    Возвращает список заказов:
    - Если указан order_id → возвращает список из одного заказа (или пустой).
    - Если указан tg_id_user → заказы клиента.
    - Если указан tg_id_master → заказы мастера.
    - Можно указать оба tg_id_user и tg_id_master.

    При поиске по order_id параметры tg_id_user, tg_id_master, active игнорируются.

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id_user: Telegram ID клиента (опционально).
    :param tg_id_master: Telegram ID мастера (опционально).
    :param active:
        - True → заказы со статусом in_work/wait (активные)
        - False → только закрытые (close)
    :param order_id: ID конкретного заказа (опционально).
    :return: Список словарей с данными заказов.
    :raises ValueError: если не указан ни один из фильтров.
    """
    conditions = []

    if order_id is not None:
        conditions.append(Orders.id == order_id)
    else:
        if tg_id_user is None and tg_id_master is None:
            raise ValueError("Укажите хотя бы один из параметров: tg_id_user, tg_id_master или order_id")
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
            "model_auto": order.model_auto,
            "total_km": order.total_km,
            "year_auto": order.year_auto,
            "gos_num": order.gos_num,
            "vin_number": order.vin_number,
            "date": order.date.isoformat() if order.date else "не указана",
        })
    return orders_list


@connection
async def update_order(session, order_id: int, **kwargs) -> bool:
    """
    Обновляет указанные поля заказа по его ID.
    Обновляются только те поля, которые переданы и не равны None.
    Поддерживаемые поля: все колонки модели Orders.

    Пример:
        await update_order(5, repair_status="in_work", tg_id_master=12345)
    """
    if not kwargs:
        return False

    allowed_columns = set(Orders.__table__.columns.keys())
    update_data = {
        key: value for key, value in kwargs.items()
        if key in allowed_columns and value is not None
    }

    if not update_data:
        return False

    stmt = update(Orders).where(Orders.id == order_id).values(**update_data)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


@connection
async def delete_order(session, order_id: int) -> bool:
    """
    Удаляет заказ из базы данных по ID.

    :param session: Асинхронная сессия SQLAlchemy (передаётся декоратором).
    :param order_id: int
    :return: True, если заказ был найден и удалён.
    """
    stmt = delete(Orders).where(Orders.id == order_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


# ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
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


# ==============================
# APPOINTMENT
# ==============================
@connection
async def get_available_hours(session, target_date: date):
    """
    Возвращает set свободных часов на указанную дату.
    Учитывает пересечение с существующими записями.
    Не поддерживает 30-минутные слоты, только 1 час.

    :param session: Асинхронная сессия SQLAlchemy.
    :param target_date: Дата, для которой проверяются свободные часы.
    """
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
        start_time = appt.appointment_time
        end_time = appt.end_time

        if not start_time or not end_time:
            continue

        start_dt = datetime.combine(target_date, start_time)
        end_dt = datetime.combine(target_date, end_time)

        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        current_hour = start_dt.hour
        while current_hour < 24:
            hour_start = datetime.combine(target_date, time(current_hour, 0))
            hour_end = hour_start + timedelta(hours=1)

            if start_dt < hour_end and end_dt > hour_start:
                occupied_hours.add(current_hour)

            current_hour += 1
            if hour_start >= end_dt:
                break

    all_possible_hours = Config.DEFAULT_HOURS
    return all_possible_hours - occupied_hours


@connection
async def get_appointment_by_users(session, tg_id_user: int, tg_id_master: int) -> Optional[Appointment]:
    """
    Возвращает запись на приём по Telegram ID клиента и мастера.

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id_user: Telegram ID клиента.
    :param tg_id_master: Telegram ID мастера.
    :return: Объект Appointment или None, если не найден.
    """
    stmt = select(Appointment).where(
        Appointment.tg_id_user == tg_id_user,
        Appointment.tg_id_master == tg_id_master
    )
    result = await session.execute(stmt)
    return result.scalars().first()


@connection
async def create_appointment(
        session,
        user_id: int,
        master_id: int,
        date_val: date,
        start_hour: float,
        end_hour: float
) -> None:
    """
    Создаёт новую запись на приём.
    Если уже существует запись между user_id и master_id — она удаляется перед созданием новой.

    :param session: Асинхронная сессия SQLAlchemy.
    :param user_id: Telegram ID клиента.
    :param master_id: Telegram ID мастера.
    :param date_val: Дата записи.
    :param start_hour: Начало (в часах, например 10.5 = 10:30).
    :param end_hour: Окончание (в часах).
    """
    # Удаляем существующую запись между этим клиентом и мастером
    existing = await get_appointment_by_users(user_id, master_id)
    if existing:
        await delete_appointment(existing.id)

    def hour_to_time(h: float) -> time:
        hours = int(h)
        minutes = int(round((h - hours) * 60))
        if minutes >= 60:
            hours += 1
            minutes -= 60
        if hours >= 24:
            hours = 23
            minutes = 59
        return time(hour=hours, minute=minutes)

    start_time = hour_to_time(start_hour)
    end_time = hour_to_time(end_hour)

    new_appointment = Appointment(
        tg_id_user=user_id,
        tg_id_master=master_id,
        appointment_date=date_val,
        appointment_time=start_time,
        end_time=end_time
    )
    session.add(new_appointment)
    await session.commit()


@connection
async def get_appointment(session, appointment_id: int) -> Optional[Appointment]:
    """
    Возвращает запись на приём по её уникальному идентификатору.

    :param session: Асинхронная сессия SQLAlchemy.
    :param appointment_id: ID записи.
    """
    stmt = select(Appointment).where(Appointment.id == appointment_id)
    result = await session.execute(stmt)
    return result.scalars().first()


@connection
async def get_filter_appointments(
        session,
        tg_id_master: Optional[int] = None,
        tg_id_user: Optional[int] = None,
        date_filter: Optional[str] = None  # "today", "month", or None (all)
) -> List[Dict[str, Any]]:
    """
    Получает записи с опциональной фильтрацией по дате.

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id_master: Фильтр по мастеру (опционально).
    :param tg_id_user: Фильтр по клиенту (опционально).
    :param date_filter: "today", "month" или None.
    """
    stmt = select(Appointment)

    if tg_id_master is not None:
        stmt = stmt.where(Appointment.tg_id_master == tg_id_master)
    if tg_id_user is not None:
        stmt = stmt.where(Appointment.tg_id_user == tg_id_user)

    today = datetime.utcnow().date()
    if date_filter == "today":
        stmt = stmt.where(func.date(Appointment.appointment_date) == today)
    elif date_filter == "month":
        first_day = today.replace(day=1)
        if today.month == 12:
            next_month = today.replace(year=today.year + 1, month=1, day=1)
        else:
            next_month = today.replace(month=today.month + 1, day=1)
        stmt = stmt.where(
            and_(
                Appointment.appointment_date >= first_day,
                Appointment.appointment_date < next_month
            )
        )

    stmt = stmt.order_by(Appointment.appointment_date, Appointment.appointment_time)
    result = await session.execute(stmt)
    appointments = result.scalars().all()

    return [
        {
            "id": appt.id,
            "tg_id_user": appt.tg_id_user,
            "tg_id_master": appt.tg_id_master,
            "appointment_date": appt.appointment_date,
            "appointment_time": appt.appointment_time,
            "end_time": appt.end_time,
        }
        for appt in appointments
    ]


@connection
async def delete_appointment(session, appointment_id: int) -> bool:
    """
    Удаляет запись из таблицы appointments по её ID.

    :param session: Асинхронная сессия SQLAlchemy.
    :param appointment_id: ID записи.
    :return: True, если запись существовала и была удалена.
    """
    stmt = delete(Appointment).where(Appointment.id == appointment_id)
    result = await session.execute(stmt)
    await session.commit()
    return result.rowcount > 0


# ==============================
# DIAGNOSTICS
# ==============================
@connection
async def save_manual_diagnostic_record(
    session,
    tg_id: int,
    entry_type: str,
    issue_and_causes: str,
    brand_auto: str,
    model_auto: str,
    year_auto: str,
    order_id: int | None = None
) -> None:
    """
    Сохраняет ручную запись диагностики (мастером или админом).
    Поддерживаемые типы:
      - 'manual_dtc'     — DTC-код введён вручную
      - 'symptom_manual' — текстовый симптом/описание неисправности

    Все поля авто обязательны (передаются явно).
    Поле issue_and_causes должно быть валидной JSON-строкой (может быть пустой структурой).

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id: Telegram ID пользователя, создавшего запись.
    :param entry_type: 'manual_dtc' или 'symptom_manual'.
    :param issue_and_causes: JSON-строка вида {"ключ": "...", "causes": [...]}
    :param brand_auto: Марка авто (обязательно).
    :param model_auto: Модель авто (обязательно).
    :param year_auto: Год выпуска (обязательно).
    :param order_id: ID связанного заказа (опционально).
    """
    if entry_type not in ("manual_dtc", "symptom_manual"):
        raise ValueError("entry_type must be 'manual_dtc' or 'symptom_manual'")
    if not isinstance(issue_and_causes, str):
        raise TypeError("issue_and_causes must be a JSON string")

    record = Diagnostics(
        entry_type=entry_type,
        brand_auto=brand_auto,
        model_auto=model_auto,
        year_auto=year_auto,
        issue_and_causes=issue_and_causes,
        tg_id=tg_id,
        order_id=order_id
    )
    session.add(record)
    await session.commit()


@connection
async def get_diagnostics_by_filter(session, filter_type: str) -> list[dict]:
    """
    Возвращает список записей из таблицы diagnostics в виде словарей,
    содержащих только распарсенный `issue_and_causes` (в виде dict),
    отфильтрованных по типу:
      - 'high' → entry_type = 'api_dtc'
      - 'low'  → entry_type = 'manual_dtc'

    :param session: Асинхронная сессия SQLAlchemy.
    :param filter_type: 'high' или 'low'
    :return: list[dict], где каждый dict — это содержимое issue_and_causes
    :raises ValueError: если filter_type не 'high' или 'low'
    """
    if filter_type not in ("high", "low"):
        raise ValueError("filter_type must be 'high' or 'low'")

    entry_type = "api_dtc" if filter_type == "high" else "manual_dtc"

    stmt = select(Diagnostics.issue_and_causes).where(Diagnostics.entry_type == entry_type)
    result = await session.execute(stmt)
    rows = result.scalars().all()

    parsed_list = []
    for raw_json in rows:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                parsed_list.append(parsed)
        except (json.JSONDecodeError, TypeError):
            continue

    return parsed_list


@connection
async def get_api_dtc_history(session) -> list[dict]:
    """
    Возвращает все записи с entry_type='api_dtc' из таблицы diagnostics,
    отсортированные по дате создания (от старых к новым).
    Каждый элемент — словарь с ключами: code, definition, causes, created_at.

    :param session: Асинхронная сессия SQLAlchemy.
    """
    stmt = select(
        Diagnostics.issue_and_causes,
        Diagnostics.created_at
    ).where(
        Diagnostics.entry_type == "api_dtc"
    ).order_by(Diagnostics.created_at.asc())
    result = await session.execute(stmt)
    rows = result.fetchall()

    history_list = []
    for row in rows:
        try:
            data = json.loads(row.issue_and_causes)
            if isinstance(data, dict):
                history_list.append({
                    "code": data.get("code", "—"),
                    "definition": data.get("definition", "—"),
                    "causes": data.get("causes", []),
                    "created_at": row.created_at
                })
        except (json.JSONDecodeError, TypeError):
            continue
    return history_list


@connection
async def save_api_dtc_record(
    session,
    tg_id: int,
    code: str,
    definition: str,
    causes: list[str]
) -> bool:
    """
    Сохраняет расшифровку DTC-кода из внешнего API в таблицу diagnostics.
    Работает ТОЛЬКО если CarApiConfig.USE_MOCK_API == False.
    Проверяет дубликаты по коду и типу 'api_dtc'.
    Поля авто не заполняются (остаются по умолчанию "-").

    :param session: Асинхронная сессия SQLAlchemy.
    :param tg_id: Telegram ID мастера, инициировавшего запрос.
    :param code: DTC-код (например, "P0300").
    :param definition: Описание ошибки.
    :param causes: Список возможных причин.
    :return: True — если запись создана, False — если мок включён или запись уже существует.
    """
    if CarApiConfig.USE_MOCK_API:
        return False

    existing = await session.scalar(
        select(Diagnostics).where(
            Diagnostics.entry_type == "api_dtc",
            Diagnostics.issue_and_causes.like(f'%"{code}"%')
        )
    )
    if existing:
        return False

    issue_and_causes = json.dumps({
        "code": code,
        "definition": definition,
        "causes": causes
    }, ensure_ascii=False)

    record = Diagnostics(
        entry_type="api_dtc",
        issue_and_causes=issue_and_causes,
        tg_id=tg_id,
        order_id=None
    )
    session.add(record)
    await session.commit()
    return True
