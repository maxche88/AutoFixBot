import asyncio
import logging
from aiogram import Dispatcher
from bot import bot
from database.engine import init_db
from services.init_admin import init_admin_user
from handlers.common_handlers import router as common_router
from handlers.staff_handlers import router as staff_router
from middlewares.block_middleware import BlockUserMiddleware
from logger import setup_logging


# Инициализация диспетчера и подключение роутеров
dp = Dispatcher()

# Подключаем middleware
dp.message.middleware(BlockUserMiddleware())
dp.callback_query.middleware(BlockUserMiddleware())

# Подключаем роутеры
dp.include_router(common_router)
dp.include_router(staff_router)


async def main():
    # Настройка логирования
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Инициализация базы данных
        await init_db()
        # Создание администратора при первом запуске
        await init_admin_user()
        # Запуск бота
        await dp.start_polling(bot)
    except Exception:
        logger.critical("Критическая ошибка при запуске бота", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        print("✅ Запуск бота")
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 Бот остановлен вручную.")
        logging.getLogger(__name__).info("Бот остановлен.")
    except Exception as e:
        logging.getLogger(__name__).critical(f"Необработанное исключение на верхнем уровне: {e}", exc_info=True)

