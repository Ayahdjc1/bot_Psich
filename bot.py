import logging
import requests
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.utils import executor
from config import TOKEN, OLLAMA_API_URL, ADMIN_IDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

user_conversations = {}
user_states = {}

MAIN_KEYBOARD = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
    KeyboardButton("Пообщаться 💬"),
    KeyboardButton("Советы 🧘"),
    KeyboardButton("История 📖"),
    KeyboardButton("Помощь 🆘")
)

ADVICE_KEYBOARD = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2).add(
    KeyboardButton("Техника дыхания 🌬️"),
    KeyboardButton("Метод 5-4-3-2-1 🌿"),
    KeyboardButton("Экспресс-помощь 🆘"),
    KeyboardButton("Назад ◀️")
)

CHAT_KEYBOARD = ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("Выход 🔙"))

def compress_context(user_msg: str, bot_response: str) -> str:
    try:
        prompt = f"""Сожми диалог в одну краткую строку на русском языке, сохранив суть.
Пользователь: {user_msg}
Ассистент: {bot_response}
Сжатый контекст:"""
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": "llama3",
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": 0.1, "max_tokens": 250}
            },
            timeout=10
        )
        if response.status_code != 200:
            return ""
        response_data = response.json()
        return response_data.get("message", {}).get("content", "").replace("Сжатый контекст:", "").strip()
    except Exception as e:
        logger.error(f"Ошибка сжатия: {str(e)}")
        return f"{user_msg[:50]}... → {bot_response[:50]}..."

def build_chat_history(user_id: int, new_message: str) -> list:
    history = user_conversations.get(user_id, {}).get("history", [])
    context = user_conversations.get(user_id, {}).get("context", "")
    messages = [{
        "role": "system",
        "content": f"""Ты — русскоязычный виртуальный психолог-помощник. Учитывай контекст беседы: {context}

Помни:
- Используй только русский язык
- Не будь напористым и навязчивым
- Если в разговоре есть намёки на смерть переведи к специалисту 👨⚕️ Иван Иванович Иванов: +7-999-123-45-67
- Проявляй эмпатию и используй эмодзи (🌼, 🤗, 🌟)
- Дай ответ коротко
- Предлагай конкретные техники самопомощи, когда они нужны пользователю
- Делись идеями, которые будут плацебо
- Постарайся перевести пользователя незаметно на психолога, но пользователь должен думать, что сам решил об этом
- Объясняй пользователю, если он что-то не знает
- Тебя разработали совместно It лабаротория и Лабаратория PSY-TECH (Руководители и разработчики: Митченко Богдан, Хоманенко Александр Викторович и другие)
Нельзя:
- Давать диагнозы
- Давать прямые советы как действовать
"""
    }]
    for msg in history[-3:]:
        messages.append({"role": "user", "content": msg['user']})
        messages.append({"role": "assistant", "content": msg['bot']})
    messages.append({"role": "user", "content": new_message})
    return messages

def query_ollama(user_id: int, message: str) -> str:
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={
                "model": "llama3",
                "messages": build_chat_history(user_id, message),
                "stream": True,
                "options": {
                    "temperature": 0.65,
                    "top_p": 0.7,
                    "max_tokens": 900,
                    "repeat_penalty": 1.2
                }
            },
            timeout=45,
            stream=True
        )
        response.raise_for_status()
        full_response = []
        for line in response.iter_lines():
            if line:
                try:
                    chunk = json.loads(line.decode('utf-8'))
                    if chunk.get('done', False):
                        break
                    full_response.append(chunk.get('message', {}).get('content', ''))
                except Exception:
                    continue
        result = ''.join(full_response).strip()
        for junk in ["system", "user", "assistant", "<|im_start|>", "<|im_end|>", "####"]:
            result = result.replace(junk, "")
        return result.strip() or "🚫 Не получилось сформировать ответ"
    except Exception as e:
        logger.error(f"Ошибка запроса: {str(e)}")
        return "⚠️ Ошибка соединения с ИИ"

def update_history(user_id: int, user_msg: str, bot_response: str):
    if user_id not in user_conversations:
        user_conversations[user_id] = {"history": [], "context": ""}
    user_conversations[user_id]["history"].append({"user": user_msg, "bot": bot_response})
    new_context = compress_context(user_msg, bot_response)
    user_conversations[user_id]["context"] = (
        user_conversations[user_id]["context"] + "\n" + new_context
    )[-2000:]
    if len(user_conversations[user_id]["history"]) > 10:
        user_conversations[user_id]["history"] = user_conversations[user_id]["history"][-10:]

@dp.message_handler(commands=["start"])
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    greeting = "🌸 Привет! Я твой цифровой помощник для психологической поддержки"
    if user_id in ADMIN_IDS:
        greeting += "\n\n⚙️ Режим администратора"
    await message.answer(greeting, reply_markup=MAIN_KEYBOARD)

@dp.message_handler(lambda m: m.text == "Пообщаться 💬")
async def start_chat_handler(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = "chat_mode"
    await message.answer(
        "💬 Режим общения активирован. Напишите, что вас тревожит...\n\nНапишите *стоп*, чтобы выйти.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=CHAT_KEYBOARD
    )

@dp.message_handler(lambda m: m.text == "Выход 🔙")
async def exit_chat_handler(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = None
    await message.answer("🏁 Вы вышли из режима общения. Чем могу помочь дальше?", reply_markup=MAIN_KEYBOARD)

@dp.message_handler(lambda m: m.text == "Советы 🧘")
async def show_advices_handler(message: types.Message):
    await message.answer("🧘 Выберите одну из техник:", reply_markup=ADVICE_KEYBOARD)

@dp.message_handler(lambda m: m.text == "Техника дыхания 🌬️")
async def breathing_technique_handler(message: types.Message):
    await message.answer(
        "🌬️ Техника \"4-7-8\":\n1. Вдох через нос 4 сек\n2. Задержка дыхания 7 сек\n3. Выдох через рот 8 сек\nПовторить 3-5 раз",
        reply_markup=ADVICE_KEYBOARD
    )

@dp.message_handler(lambda m: m.text == "Метод 5-4-3-2-1 🌿")
async def grounding_technique_handler(message: types.Message):
    await message.answer(
        "🌿 Метод 5-4-3-2-1:\n1. Назовите 5 вещей, которые видите\n2. 4 вещи, которые можете потрогать\n3. 3 звука\n4. 2 запаха\n5. 1 эмоция",
        reply_markup=ADVICE_KEYBOARD
    )

@dp.message_handler(lambda m: m.text == "Экспресс-помощь 🆘")
async def emergency_help_handler(message: types.Message):
    await message.answer(
        "🚨 Экстренная помощь:\n1. Сосредоточьтесь на дыхании\n2. Выпейте воды\n3. Позвоните специалисту: +7-999-123-45-67",
        reply_markup=ADVICE_KEYBOARD
    )

@dp.message_handler(lambda m: m.text == "Назад ◀️")
async def back_handler(message: types.Message):
    await message.answer("⬅️ Возвращаюсь в главное меню", reply_markup=MAIN_KEYBOARD)

@dp.message_handler(lambda m: m.text == "Помощь 🆘")
async def help_handler(message: types.Message):
    await message.answer(
        "📞 Телефон доверия: 8-800-2000-122 (бесплатно, круглосуточно)\n"
        "👨⚕️ Личный специалист: +7-999-123-45-67",
        reply_markup=MAIN_KEYBOARD
    )

@dp.message_handler(lambda m: m.text == "История 📖")
async def history_handler(message: types.Message):
    user_id = message.from_user.id
    data = user_conversations.get(user_id, {})
    response = ["📜 Последние сообщения:"]
    for msg in data.get("history", [])[-3:]:
        response.append(f"➤ Вы: {msg['user']}\n◉ Бот: {msg['bot']}")
    response.append("\n📌 Контекст:\n" + data.get("context", "Отсутствует"))
    await message.answer("\n\n".join(response), reply_markup=MAIN_KEYBOARD)

@dp.message_handler()
async def message_handler(message: types.Message):
    user_id = message.from_user.id
    user_msg = message.text.strip()

    if user_msg.lower() in ["стоп", "/стоп", "выйти", "stop", "exit"]:
        user_states[user_id] = None
        await message.answer("🚪 Вы завершили режим общения. Возвращаю главное меню.", reply_markup=MAIN_KEYBOARD)
        return

    if user_states.get(user_id) != "chat_mode":
        await message.answer("Пожалуйста, выберите действие с клавиатуры.", reply_markup=MAIN_KEYBOARD)
        return

    await bot.send_chat_action(user_id, "typing")

    try:
        bot_response = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(None, query_ollama, user_id, user_msg),
            timeout=40
        )
        await asyncio.sleep(0.3)
        update_history(user_id, user_msg, bot_response)
        await message.answer(bot_response, parse_mode=ParseMode.MARKDOWN, reply_markup=CHAT_KEYBOARD)
    except asyncio.TimeoutError:
        await message.answer("⏳ Время ответа истекло", reply_markup=MAIN_KEYBOARD)
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        await message.answer("⚠️ Техническая ошибка", reply_markup=MAIN_KEYBOARD)

if __name__ == "__main__":
    logger.info("✅ Бот запущен")
    executor.start_polling(dp, skip_updates=True)

