import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()


class LoggingConfig:
    LOG_DIR = Path("logs")
    LOG_LEVEL = "INFO"
    BOT_LOG_FILE = "bot.log"
    DB_LOG_FILE = "database.log"
    API_LOG_FILE = "api.log"

    @classmethod
    def ensure_log_dir(cls):
        cls.LOG_DIR.mkdir(exist_ok=True)


class CarApiConfig:
    RAPID_API_KEY = os.getenv("RAPID_API_KEY", "")
    USE_MOCK_API = False
    BASE_URL = "https://car-code.p.rapidapi.com/obd2/".strip()

    headers = {
        "x-rapidapi-host": "car-code.p.rapidapi.com",
        "x-rapidapi-key": RAPID_API_KEY,
    }


class Config:
    API_TOKEN = os.getenv("API_TOKEN")
    ADMIN_ID = os.getenv("ADMIN_ID")

    if not API_TOKEN:
        raise ValueError("Переменная окружения API_TOKEN обязательна!")
    if not ADMIN_ID:
        raise ValueError("Переменная окружения ADMIN_ID обязательна!")

    TEMP_MESSAGE_LIFETIME_SEC: int = 5

    SERVICE_LOCATION_URL = (
        "https://yandex.ru/navi/?whatshere%5Bpoint%5D=73.305003%2C54.908418"
        "&whatshere%5Bzoom%5D=18&lang=ru&from=navi"
    )

    SUPPORT_PHONE = "+7 (999) 123-45-67"
    SUPPORT_EMAIL = "info@autoservis.ru"
    OFFICE_ADDRESS = "г. Омск, ул. 2-я Казахстанская, 3Б"
    WORKING_HOURS = "Пн–Сб: 08:00–19:00\nВс: выходной"
    DEFAULT_HOURS = set(range(8, 24))
