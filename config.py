import os
from dotenv import load_dotenv
from pathlib import Path


load_dotenv()


class LoggingConfig:
    LOG_DIR = Path("logs")
    LOG_LEVEL = "INFO"

    # Имена файлов для разных категорий
    BOT_LOG_FILE = "bot.log"
    DB_LOG_FILE = "database.log"
    API_LOG_FILE = "api.log"

    @classmethod
    def ensure_log_dir(cls):
        cls.LOG_DIR.mkdir(exist_ok=True)


class CarApiConfig:
    def __init__(self):
        self.RAPID_API_KEY = os.getenv("RAPID_API_KEY", "")
        self.USE_MOCK_API = False
        self.BASE_URL = "https://car-code.p.rapidapi.com/obd2/"

    @property
    def headers(self):
        return {
            "x-rapidapi-host": "car-code.p.rapidapi.com",
            "x-rapidapi-key": self.RAPID_API_KEY
        }


class Config:
    API_TOKEN = os.getenv("API_TOKEN")
    ADMIN_ID = os.getenv("ADMIN_ID")

    TEMP_MESSAGE_LIFETIME_SEC: int = 5  # время жизни временных сообщений (в секундах)

    # Ссылка на карту
    SERVICE_LOCATION_URL = ("https://yandex.ru/navi/"
                            "?whatshere%5Bpoint%5D=73.305003%2C54.908418&whatshere%5Bzoom%5D=18&lang=ru&from=navi")

    # Контакты
    SUPPORT_PHONE = "+7 (999) 123-45-67"
    SUPPORT_EMAIL = "info@autoservis.ru"

    # Адрес СТО
    OFFICE_ADDRESS = "г. Омск, ул. 2-я Казахстанская, 3Б"

    # Рабочие часы по умолчанию: с 8 до 23 (24 не включён)
    WORKING_HOURS = "Пн–Сб: 08:00–19:00\nВс: выходной"
    DEFAULT_HOURS = set(range(8, 24))


config = Config()
api_config = CarApiConfig()
