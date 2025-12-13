from datetime import datetime


async def get_greeting():
    now = datetime.now().hour

    if 6 <= now < 12:
        greeting = "🔆Доброе утро!"
    elif 12 <= now < 18:
        greeting = " 🔆 Добрый день"
    elif 18 <= now < 23:
        greeting = "🔆 Добрый вечер!"
    else:
        greeting = "🌙 Доброй ночи!"

    return greeting
