import os
from dotenv import load_dotenv
from aiogram import Bot
from aiogram.enums.parse_mode import ParseMode
from aiogram.client.default import DefaultBotProperties


load_dotenv()

bot = Bot(os.getenv('API_TOKEN'), default=DefaultBotProperties(parse_mode=ParseMode.HTML))

# Рабочие часы по умолчанию: с 8 до 23 (24 не включён)
DEFAULT_HOURS = set(range(8, 24))
