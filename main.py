from aiogram import Dispatcher
import os
import logging
import asyncio
from routers.common_handlers import router as common_router
from routers.staff_handlers import router as staff_router
from database.engine import init_db
from bot import bot
from services.init_admin import init_admin_user


# Настройка логирования
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(log_dir, "bot.log"),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

dp = Dispatcher()

dp.include_router(common_router)
dp.include_router(staff_router)


async def main():
    await init_db()
    await init_admin_user()
    print('✅ Бот включен')
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('🛑 Бот остановлен вручную.')
    except Exception as e:
        logging.error(f"Критическая ошибка: {e}")
        print(f"❌ Ошибка: {e}")

