import json
import os
from config import api_config
import aiohttp


# Загрузка мок-данных из файла
MOCK_DATA_PATH = os.path.join(os.path.dirname(__file__), "mock_obd2.json")

try:
    with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
        MOCK_RESPONSES = json.load(f)
except FileNotFoundError:
    MOCK_RESPONSES = {}
    print(f"Файл мок-данных не найден: {MOCK_DATA_PATH}")
except json.JSONDecodeError as e:
    MOCK_RESPONSES = {}
    print(f"Ошибка чтения JSON в {MOCK_DATA_PATH}: {e}")


async def decode_obd2_code(code: str) -> dict | None:
    """
    Расшифровывает OBD2-код через car-code.p.rapidapi.com.
    Возвращает словарь с ключами: code, definition, cause (list).
    Если ошибка — возвращает None.
    """
    code = code.strip().upper()
    if not code or len(code) < 4:
        return None

    # Если включён мок — возвращаем локальные данные
    if api_config.USE_MOCK_API:
        return MOCK_RESPONSES.get(code)

    # Иначе — идём в настоящий API
    url = f"{api_config.BASE_URL}{code}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=api_config.headers) as resp:
                if resp.status == 200:
                    data = await resp.json()
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