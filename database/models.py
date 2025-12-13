from sqlalchemy import String, BigInteger, Boolean, DateTime, Time
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncAttrs, async_sessionmaker, create_async_engine, AsyncSession
from datetime import datetime, time, timezone


DB_PATH = 'database/data_users.db'

# Создаем асинхронный движок
engine = create_async_engine(url=f'sqlite+aiosqlite:///{DB_PATH}')

# Настраиваем асинхронную сессию
async_session = async_sessionmaker(engine, class_=AsyncSession)


# Возвращает текущее время в UTC без микросекунд
def current_time():
    return datetime.now(timezone.utc).replace(microsecond=0)


# Асинхронная функция для создания таблиц
async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# Базовый класс для моделей
# AsyncAttrs - автоматически оборачивает доступ к отношениям (relationship) в асинхронную загрузку
# DeclarativeBase — для автоматической регистрации моделей в метаданных SQLAlchemy.
class Base(AsyncAttrs, DeclarativeBase):
    pass


# Пользователь
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    user_name: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), nullable=True)
    rating: Mapped[int] = mapped_column(nullable=True)
    contact: Mapped[str] = mapped_column(String(20), nullable=True)
    brand_auto: Mapped[str] = mapped_column(String(20), nullable=True)
    year_auto: Mapped[str] = mapped_column(String(20), default="-")
    vin_number: Mapped[str] = mapped_column(String(20), default="-")
    role: Mapped[str] = mapped_column(String(10), default="user")  # "user", "admin", "master"
    can_messages: Mapped[bool] = mapped_column(Boolean(), default=False)
    date: Mapped[datetime] = mapped_column(DateTime, default=current_time)


# Заказы на ремонт
class Orders(Base):
    __tablename__ = 'orders'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id_user: Mapped[int] = mapped_column(BigInteger)
    tg_id_master: Mapped[int] = mapped_column(BigInteger)
    user_name: Mapped[str] = mapped_column(String(20))
    master_name: Mapped[str] = mapped_column(String(20))
    repair_status: Mapped[str] = mapped_column(String(20))  # Текущий статус (например, "в работе", "завершён")
    date: Mapped[datetime] = mapped_column(DateTime, default=current_time)
    complied: Mapped[bool] = mapped_column(Boolean(), default=False)  # Выполнен ли заказ


#  Запись на приём/ремонт
class Appointment(Base):
    __tablename__ = 'appointments'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    appointment_date: Mapped[datetime] = mapped_column(DateTime)
    appointment_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)


# Комментарии/отзывы пользователей
class Comments(Base):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tg_id: Mapped[int] = mapped_column(BigInteger)
    user_name: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(String(128))
    date: Mapped[datetime] = mapped_column(DateTime, default=current_time)

