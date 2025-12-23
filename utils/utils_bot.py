import asyncio
from aiogram import Bot
from typing import List
from aiogram.exceptions import TelegramAPIError
from config import config


async def delete_messages_after_delay(
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

    actual_delay = delay if delay is not None else config.TEMP_MESSAGE_LIFETIME_SEC
    await asyncio.sleep(actual_delay)

    for msg_id in message_ids:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except TelegramAPIError:
            # Игнорируем ошибки Telegram API:
            # - сообщение уже удалено
            # - прошло более 48 часов (в ЛС)
            # - нет прав на удаление
            # - пользователь заблокировал бота и т.п.
            pass
