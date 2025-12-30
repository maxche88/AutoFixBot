from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from database.requests import get_user_role


class BlockUserMiddleware(BaseMiddleware):
    """
    Middleware, блокирующая всех пользователей с ролью 'blocked'.
    Такие пользователи не получают ответов и не могут взаимодействовать с ботом.
    """
    async def __call__(self, handler, event, data):
        user_id = None

        # Поддерживаем и Message, и CallbackQuery
        if isinstance(event, (Message, CallbackQuery)):
            user_id = event.from_user.id
        else:
            # Если событие другого типа — пропускаем
            return await handler(event, data)

        # Получаем роль из БД
        role = await get_user_role(user_id)

        # Если пользователь заблокирован — НЕ вызываем обработчик
        if role == "blocked":
            return  # тишина

        # Иначе — продолжаем обработку
        return await handler(event, data)