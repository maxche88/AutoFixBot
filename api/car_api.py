from config import config
import aiohttp

API_KEY = config.RAPID_API_KEY
BASE_URL = "https://car-code.p.rapidapi.com/obd2/"
HEADERS = {
    "x-rapidapi-host": "car-code.p.rapidapi.com",
    "x-rapidapi-key": API_KEY
}


async def decode_obd2_code(code: str) -> dict | None:
    """
    Расшифровывает OBD2-код через car-code.p.rapidapi.com.
    Возвращает словарь с ключами: code, definition, cause (list).
    Если ошибка — возвращает None.
    """
    code = code.strip().upper()
    if not code or len(code) < 4:
        return None

    url = f"{BASE_URL}{code}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=HEADERS) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Ожидаем: {'code': 'P0001', 'definition': '...', 'cause': [...]}
                    return {
                        "code": data.get("code", code),
                        "definition": data.get("definition", "Описание недоступно"),
                        "cause": data.get("cause", [])
                    }
                else:
                    error_text = await resp.text()
                    print(f"OBD2 API ошибка ({resp.status}): {error_text}")
                    return None
    except Exception as e:
        print(f"Ошибка при запросе к OBD2 API: {e}")
        return None
