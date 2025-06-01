import os

# Токен вашего бота, полученный от BotFather
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# URL вашего локального сервера Ollama
OLLAMA_API_URL = "http://localhost:11434/api/chat"

# Идентификаторы администраторов (для управления ботом)
ADMIN_IDS = []  # Замените на свои ID, если нужно

# Уберите ограничение на пользователей, чтобы все могли использовать бота
USER_IDS = []  # Теперь список пустой, значит все пользователи могут пользоваться ботом

# Инициализационная модель
INITMODEL = "llama3"

# Параметры Ollama
OLLAMA_BASE_URL = "localhost"
OLLAMA_PORT = 11434
TIMEOUT = 3000

