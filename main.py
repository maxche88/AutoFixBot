from aiogram import Dispatcher
import logging
import asyncio
from routers.common import router
from database.models import async_main
from config import bot
from database.requests import init_admin_user


logging.basicConfig(filename='logs/bot.log', level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


dp = Dispatcher()
dp.include_router(router)


async def main():
    await async_main()
    await init_admin_user()
    print('✅ Бот включен')
    logging.info('Пользователь вошел в bot')
    await dp.start_polling(bot)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('🛑 Бот остановлен')

