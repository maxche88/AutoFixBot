from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from database.models import Base

DB_PATH = 'database/data_users.db'
engine = create_async_engine(f'sqlite+aiosqlite:///{DB_PATH}')
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


# Асинхронная функция для создания таблиц
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
