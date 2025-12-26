"""
Модели базы данных для Telegram-бота.
Используется SQLAlchemy в асинхронном режиме (AsyncAttrs).
Все модели наследуются от общего базового класса `Base`.
"""

from sqlalchemy import String, BigInteger, Boolean, Date, DateTime, Time
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs
from datetime import datetime, time
from utils.time_bot import current_time


class Base(AsyncAttrs, DeclarativeBase):
    """
    Базовый класс для всех моделей SQLAlchemy.
    - `AsyncAttrs` — поддержка асинхронной загрузки связанных объектов (например, через `await obj.related`).
    - `DeclarativeBase` — стандартный базовый класс для декларативного стиля определения моделей.
    """
    pass


class User(Base):
    """
    Таблица пользователей Telegram, прошедших авторизацию в боте.
    Хранит профиль пользователя: контактные данные, информацию об авто, роль и права.
    """
    __tablename__ = 'users'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID пользователя")
    user_name: Mapped[str] = mapped_column(String(20), comment="Имя пользователя (указано при регистрации)")
    status: Mapped[str] = mapped_column(String(20), nullable=True, comment="Текущий статус (например, 'активен')")
    rating: Mapped[int] = mapped_column(nullable=True, comment="Рейтинг пользователя")
    contact: Mapped[str] = mapped_column(String(20), nullable=True, comment="Контактный телефон")
    brand_auto: Mapped[str] = mapped_column(String(20), nullable=True, comment="Марка автомобиля")
    model_auto: Mapped[str] = mapped_column(String(30), default="-", comment="Модель автомобиля")
    year_auto: Mapped[str] = mapped_column(String(20), default="-", comment="Год выпуска автомобиля")
    gos_num: Mapped[str] = mapped_column(String(20), default="-", comment="Гоc. Номер")
    vin_number: Mapped[str] = mapped_column(String(20), default="-", comment="VIN-номер автомобиля")
    total_km: Mapped[str] = mapped_column(String(20), default="-", comment="Пробег авто")
    role: Mapped[str] = mapped_column(String(10), default="user", comment="Роль: 'user', 'admin' или 'master'")
    can_messages: Mapped[bool] = mapped_column(Boolean(), default=False, comment="Может ли получать сообщения")
    date: Mapped[datetime] = mapped_column(DateTime, default=current_time, comment="Дата регистрации")


class Orders(Base):
    """
    Таблица заказов на ремонт/обслуживание.
    Связывает пользователя и мастера, отслеживает статус выполнения работ.
    """
    __tablename__ = 'orders'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    description: Mapped[str] = mapped_column(String(100), nullable=True, comment="Описание работ или неисправности")
    brand_auto: Mapped[str] = mapped_column(String(20), nullable=True, comment="Марка автомобиля")
    model_auto: Mapped[str] = mapped_column(String(30), default="-", comment="Модель автомобиля")
    gos_num: Mapped[str] = mapped_column(String(20), default="-", comment="Гоc. Номер")
    year_auto: Mapped[str] = mapped_column(String(20), default="-", comment="Год выпуска автомобиля")
    total_km: Mapped[str] = mapped_column(String(20), default="-", comment="Пробег авто")
    vin_number: Mapped[str] = mapped_column(String(20), default="-", comment="VIN-номер автомобиля")
    tg_id_user: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID клиента")
    tg_id_master: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID мастера")
    user_name: Mapped[str] = mapped_column(String(20), comment="Имя клиента")
    user_contact: Mapped[str] = mapped_column(String(20), nullable=True, comment="Контактный телефон клиента")
    master_name: Mapped[str] = mapped_column(String(20), comment="Имя мастера")
    master_contact: Mapped[str] = mapped_column(String(20), nullable=True, comment="Контактный телефон мастера")
    repair_status: Mapped[str] = mapped_column(String(20), comment="in_work/wait/close")
    date: Mapped[datetime] = mapped_column(DateTime, default=current_time, comment="Дата создания заказа")
    complied: Mapped[bool] = mapped_column(Boolean(), default=False, comment="True = Заказ выполнен")


class Appointment(Base):
    """
    Таблица записей на приём (дата и время).
    Используется для управления расписанием: клиенты записываются на свободное время.
    """
    __tablename__ = 'appointments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id_user: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID клиента")
    tg_id_master: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID мастера")
    appointment_date: Mapped[datetime] = mapped_column(Date, comment="Дата записи")
    appointment_time: Mapped[time] = mapped_column(Time, comment="Начало временного слота")
    end_time: Mapped[time] = mapped_column(Time, comment="Окончание временного слота")


class Comments(Base):
    """
    Таблица отзывов пользователей.
    Хранит текстовые комментарии, оставленные пользователями о работе СТО.
    """
    __tablename__ = 'comments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID автора отзыва")
    user_name: Mapped[str] = mapped_column(String(20), comment="Имя автора отзыва")
    text: Mapped[str] = mapped_column(String(128), comment="Текст отзыва")
    date: Mapped[datetime] = mapped_column(DateTime, default=current_time, comment="Дата публикации отзыва")
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True, comment="Отображать отзыв (True = да)")


class Diagnostics(Base):
    __tablename__ = 'diagnostics'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brand_auto: Mapped[str] = mapped_column(String(20), comment="Марка автомобиля")
    model_auto: Mapped[str] = mapped_column(String(30), comment="Модель автомобиля")
    year_auto: Mapped[str] = mapped_column(String(10), comment="Год выпуска")
    symptoms_and_causes: Mapped[str] = mapped_column(
        String(1000),
        default="{}",
        comment="JSON: {\"симптом или DTC\": \"причина\"}"
    )
    master_tg_id: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID мастера, добавившего запись")
    client_tg_id: Mapped[int] = mapped_column(BigInteger, comment="Telegram ID клиента")
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=True, comment="ID связанного заказа (Orders.id)")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=current_time, comment="Дата добавления записи")


class History(Base):
    __tablename__ = "history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, comment="tg_id пользователя")
    code_dtc: Mapped[str] = mapped_column(String(30), comment="Код неисправности")
    description: Mapped[str] = mapped_column(String(30), comment="Описание ошибки")
    possible_reasons: Mapped[str] = mapped_column(String(30), comment="Возможные причины")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=current_time, comment="Дата добавления записи")
