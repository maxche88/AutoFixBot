from aiogram import Dispatcher
import logging
import asyncio
from routers.common_handlers import router as common_router
from routers.staff_handlers import router as staff_router
from database.engine import init_db
from config import bot
from services.init_admin import init_admin_user


logging.basicConfig(filename='logs/bot.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


dp = Dispatcher()

dp.include_router(common_router)
dp.include_router(staff_router)


async def main():
    await init_db()
    await init_admin_user()
    print('✅ Бот включен')
    logging.info('Пользователь вошел в bot')
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('🛑 Бот остановлен')

