"""
Модуль работы с базой данных: CRUD-операции и бизнес-логика.

Использует асинхронный движок SQLAlchemy.
Все функции асинхронные и работают через session-обёртку.
"""

from database.models import User, Comments, Orders, Appointment, History
from database.engine import async_session
from sqlalchemy import func, update, select, delete, and_
from datetime import datetime, timedelta, date, time
from typing import Optional, Tuple, List, Dict, Any
from config import config


def connection(func_):
    """
    Декоратор для автоматического управления сессией базы данных.

    Оборачивает функцию, открывает асинхронную сессию,
    передаёт её первым аргументом и автоматически закрывает после выполнения.
    """
    async def wrapper(*args, **kwargs):
        async with async_session() as session:
            return await func_(session, *args, **kwargs)
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
async def add_comment(data: Dict[str, Any]) -> int:
    """
    Добавляет отзыв (комментарий) от пользователя.

    :param data: Словарь с полями модели Comments (tg_id, user_name, text).
    :return: id: int
    """
    async with async_session() as session:
        comment_obj = Comments(**data)
        session.add(comment_obj)
        await session.commit()
        await session.refresh(comment_obj)  #обновляет объект, включая id
        return comment_obj.id


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


async def get_all_masters(exclude_tg_id: int | None = None) -> list[dict]:
    """
    Возвращает список мастеров: [{'tg_id': ..., 'user_name': ..., 'contact': ...}]
    Исключает мастера с указанным tg_id (если задан).
    """
    async with async_session() as session:
        query = select(User.tg_id, User.user_name, User.contact).where(User.role == "master")
        if exclude_tg_id is not None:
            query = query.where(User.tg_id != exclude_tg_id)
        result = await session.execute(query)
        return [
            {"tg_id": row.tg_id, "user_name": row.user_name, "contact": row.contact}
            for row in result.fetchall()
        ]


async def get_user_by_tg_id(tg_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
    """
    Получает пользователя по Telegram ID, возвращая указанные поля.
    Если `fields` не указан — возвращает все поля модели User.

    Примеры:
        # Все поля
        user = await get_user_by_tg_id(123)

        # Только нужные поля
        user = await get_user_by_tg_id(123, ["user_name", "contact", "brand_auto"])

    :param tg_id: Telegram ID пользователя.
    :param fields: Список имён полей для выборки (например, ["user_name", "contact"]).
                   Если None — возвращаются все поля.
    :return: Словарь с данными пользователя или None, если не найден.
    """
    allowed_columns = set(User.__table__.columns.keys())

    if fields is not None:
        # Оставляем только существующие поля
        valid_fields = [f for f in fields if f in allowed_columns]
        if not valid_fields:
            return None
        columns_to_select = [User.__table__.c[field] for field in valid_fields]
    else:
        # Выбираем все колонки
        columns_to_select = list(User.__table__.columns.keys)

    async with async_session() as session:
        stmt = select(*columns_to_select).where(User.tg_id == tg_id)
        result = await session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        user_dict = dict(row)

        # Обрабатываем дату, как в оригинале (если есть)
        if 'date' in user_dict and user_dict['date'] is not None:
            user_dict['date'] = user_dict['date'].isoformat()

        return user_dict


async def get_user_dict(tg_id: int, fields: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
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

    :param tg_id: Telegram ID пользователя (уникальный идентификатор).
    :param fields: Список имён колонок для выборки (например: ["user_name", "contact"]).
                   Если None — возвращаются все поля модели User.
    :return: Словарь вида {"поле": значение, ...} или None, если пользователь не найден.
    """
    # Получаем множество допустимых имён колонок из модели User
    allowed_columns = set(User.__table__.columns.keys())

    if fields is not None:
        # Фильтруем только существующие поля (защита от опечаток)
        valid_fields = [f for f in fields if f in allowed_columns]
        if not valid_fields:
            return None
        # Формируем список колонок для SELECT-запроса
        columns = [getattr(User, field) for field in valid_fields]
    else:
        # Выбираем все колонки модели User
        columns = [getattr(User, col) for col in allowed_columns]

    # Извлекаем имена колонок для последующего сопоставления с данными
    column_names = [col.key for col in columns]

    async with async_session() as session:
        stmt = select(*columns).where(User.tg_id == tg_id)
        result = await session.execute(stmt)
        row = result.fetchone()

        if row is None:
            return None

        # Собираем словарь: ключ:значение
        return dict(zip(column_names, row))


async def update_user(tg_id: int, column: str, value: Any) -> bool:
    """
    Обновляет одно поле пользователя по его Telegram ID.

    :param tg_id: Telegram ID пользователя.
    :param column: Имя колонки модели User (например, 'contact', 'brand_auto').
    :param value: Новое значение.
    :return: True, если пользователь найден и поле обновлено.
    """
    if not hasattr(User, column):
        return False

    async with async_session() as session:
        stmt = update(User).where(User.tg_id == tg_id).values({column: value})
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


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
                    # для надёжности — проверим все часы до 24
                    pass

                current_hour += 1
                if hour_start >= end_dt:
                    break

        # Возвращаем свободные часы
        all_possible_hours = config.DEFAULT_HOURS  # например, {9, 10, ..., 17}
        return all_possible_hours - occupied_hours


async def get_appointment_by_users(tg_id_user: int, tg_id_master: int) -> Optional[Appointment]:
    """
    Возвращает запись на приём по Telegram ID клиента и мастера.
    :param tg_id_user: Telegram ID клиента.
    :param tg_id_master: Telegram ID мастера.
    :return: Объект Appointment или None, если не найден.
    """
    async with async_session() as session:
        stmt = select(Appointment).where(
            Appointment.tg_id_user == tg_id_user,
            Appointment.tg_id_master == tg_id_master
        )
        result = await session.execute(stmt)
        return result.scalars().first()


async def create_appointment(user_id: int, master_id: int, date_val: date, start_hour: float, end_hour: float) -> None:
    """
    Создаёт новую запись на приём.
    Если уже существует запись между user_id и master_id — она удаляется перед созданием новой.
    """
    # Удаляем существующую запись между этим клиентом и мастером
    existing = await get_appointment_by_users(user_id, master_id)
    if existing:
        await delete_appointment(existing.id)

    # Преобразуем дробные часы в (часы, минуты)
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

    # Создаём новую запись
    async with async_session() as session:
        new_appointment = Appointment(
            tg_id_user=user_id,
            tg_id_master=master_id,
            appointment_date=date_val,
            appointment_time=start_time,
            end_time=end_time
        )
        session.add(new_appointment)
        await session.commit()


async def get_appointment(appointment_id: int) -> Optional[Appointment]:
    """
    Возвращает запись на приём по её уникальному идентификатору.
    """
    async with async_session() as session:
        stmt = select(Appointment).where(Appointment.id == appointment_id)
        result = await session.execute(stmt)
        return result.scalars().first()


async def get_filter_appointments(
    tg_id_master: Optional[int] = None,
    tg_id_user: Optional[int] = None,
    date_filter: Optional[str] = None  # "today", "month", or None (all)
) -> List[Dict[str, Any]]:
    """
    Получает записи с опциональной фильтрацией по дате.
    """
    async with async_session() as session:
        stmt = select(Appointment)

        if tg_id_master is not None:
            stmt = stmt.where(Appointment.tg_id_master == tg_id_master)
        if tg_id_user is not None:
            stmt = stmt.where(Appointment.tg_id_user == tg_id_user)

        # Фильтрация по дате
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


async def delete_appointment(appointment_id: int) -> bool:
    """
    Удаляет запись из таблицы appointments по её ID.

    :param appointment_id: ID записи.
    :return: True, если запись существовала и была удалена.
    """
    async with async_session() as session:
        stmt = delete(Appointment).where(Appointment.id == appointment_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


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

    :param tg_id_user: Telegram ID клиента (опционально).
    :param tg_id_master: Telegram ID мастера (опционально).
    :param active:
        - True → заказы со статусом in_work/wait (активные)
        - False → только закрытые (close)
    :param order_id: ID конкретного заказа (опционально).
    :return: Список словарей с данными заказов.
    :raises ValueError: если не указан ни один из фильтров.
    """
    async with async_session() as session:
        conditions = []

        if order_id is not None:
            # Поиск ТОЛЬКО по ID заказа
            conditions.append(Orders.id == order_id)
        else:
            # Старая логика
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


async def update_order(order_id: int, **kwargs) -> bool:
    """
    Обновляет указанные поля заказа по его ID.
    Обновляются только те поля, которые переданы и не равны None.
    Поддерживаемые поля: все колонки модели Orders.

    Пример:
        await update_order(5, repair_status="in_work", tg_id_master=12345)

    :return: True, если заказ найден и обновлён.
    """
    if not kwargs:
        return False

    # Получаем список допустимых имён колонок из модели
    allowed_columns = set(Orders.__table__.columns.keys())

    # Фильтруем только разрешённые и не-None поля
    update_data = {
        key: value for key, value in kwargs.items()
        if key in allowed_columns and value is not None
    }

    if not update_data:
        return False

    async with async_session() as session:
        stmt = update(Orders).where(Orders.id == order_id).values(**update_data)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


async def delete_order(order_id: int) -> bool:
    """
    Удаляет заказ из базы данных по ID.
    :return: True, если заказ был найден и удалён.
    """
    async with async_session() as session:
        stmt = delete(Orders).where(Orders.id == order_id)
        result = await session.execute(stmt)
        await session.commit()
        return result.rowcount > 0


# ==============================
# ИСТОРИЯ ЗАПРОСОВ API - history
# ==============================
async def save_search_history(
    tg_id: int,
    code_dtc: str,
    description: str,
    possible_reasons: list[str]
) -> None:
    """
    Сохраняет запись в историю DTC-поиска.
    :param tg_id: Telegram ID пользователя
    :param code_dtc: Код ошибки (например, P0300)
    :param description: Описание ошибки
    :param possible_reasons: Список возможных причин (будет сохранён как строка с разделителем '\n')
    """
    # Преобразуем список причин в строку
    reasons_str = "\n".join(possible_reasons) if isinstance(possible_reasons, list) else str(possible_reasons)

    async with async_session() as session:
        history_entry = History(
            tg_id=tg_id,
            code_dtc=code_dtc,
            description=description,
            possible_reasons=reasons_str
            # created_at будет установлен автоматически
        )
        session.add(history_entry)
        await session.commit()