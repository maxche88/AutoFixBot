from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import config

if not config.API_TOKEN:
    raise ValueError("❌ API_TOKEN не найден в .env")

bot = Bot(
    token=config.API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
