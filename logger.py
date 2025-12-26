import logging
from logging.handlers import RotatingFileHandler
from config import LoggingConfig


def setup_logging():
    """Настраивает три лог-файла: bot.log, database.log, api.log.
    Все уровни (включая ERROR/CRITICAL) пишутся в соответствующий файл.
    """
    LoggingConfig.ensure_log_dir()

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Основной логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, LoggingConfig.LOG_LEVEL))

    bot_handler = RotatingFileHandler(
        LoggingConfig.LOG_DIR / LoggingConfig.BOT_LOG_FILE,
        maxBytes=5_000_000,
        backupCount=3,
        encoding='utf-8'
    )
    bot_handler.setFormatter(formatter)
    bot_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(bot_handler)

    # Логгер для database
    db_handler = RotatingFileHandler(
        LoggingConfig.LOG_DIR / LoggingConfig.DB_LOG_FILE,
        maxBytes=5_000_000,
        backupCount=2,
        encoding='utf-8'
    )
    db_handler.setFormatter(formatter)
    db_handler.setLevel(logging.DEBUG)
    db_logger = logging.getLogger("database")
    db_logger.addHandler(db_handler)

    # Логгер для api
    api_handler = RotatingFileHandler(
        LoggingConfig.LOG_DIR / LoggingConfig.API_LOG_FILE,
        maxBytes=5_000_000,
        backupCount=2,
        encoding='utf-8'
    )
    api_handler.setFormatter(formatter)
    api_handler.setLevel(logging.DEBUG)
    api_logger = logging.getLogger("api")
    api_logger.addHandler(api_handler)
