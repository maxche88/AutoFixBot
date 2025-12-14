from aiogram import Dispatcher
import os
import logging
import asyncio
from routers.common_handlers import router as common_router
from routers.staff_handlers import router as staff_router
from database.engine import init_db
from config import bot
from services.init_admin import init_admin_user


log_dir = "logs"
if not os.path.exists(log_dir):
    os.makedirs(log_dir)

log_file = os.path.join(log_dir, "bot.log")
logging.basicConfig(filename='logs/bot.log',
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
        print('🛑 Бот остановлен')

