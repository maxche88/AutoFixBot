import asyncio
from aiogram import Bot
from typing import List
from aiogram.exceptions import TelegramAPIError
from config import Config
import logging


logger = logging.getLogger("bot")


async def message_deleter(
        bot: Bot,
        chat_id: int,
        message_ids: List[int],
        delay: int = None
) -> None:
    """
    Удаляет список сообщений в чате через заданную задержку.

    :param bot: Экземпляр бота
    :param chat_id: ID чата
    :param message_ids: Список ID сообщений для удаления
    :param delay: Задержка в секундах. Если не указано — берётся из config.TEMP_MESSAGE_LIFETIME_SEC
    """

    actual_delay = delay if delay is not None else Config.TEMP_MESSAGE_LIFETIME_SEC
    await asyncio.sleep(actual_delay)

    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramAPIError:
            pass
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при удалении {msg_id} в чате {chat_id}: {e}",
                exc_info=True
            )
