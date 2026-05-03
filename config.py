# Загрузка настроек из .env
import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Username бота
BOT_USERNAME = os.getenv("BOT_USERNAME", "MoscowZooQuizBot").strip().lstrip("@")

# ID чата администратора (в него пересылаются результаты и отзывы)
try:
    ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
except ValueError:
    ADMIN_CHAT_ID = 0

# Контакты админа (ну или сотрудника зоопарка)
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip().lstrip("@")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "").strip()

# Внешние ссылки
GUARDIAN_URL = "https://moscowzoo.ru/my-zoo/become-a-guardian/"
ZOO_TG_CHANNEL = "https://t.me/Moscowzoo_official"

# Файл, куда сохраняем отзывы
FEEDBACK_FILE = "feedback.csv"

# Если токена нет, то сразу падаем с ошибкой
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и заполните.")
