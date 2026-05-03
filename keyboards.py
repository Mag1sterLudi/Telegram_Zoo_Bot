# Все inline-клавиатуры бота собраны в одном файле, чтобы не дублировать.

import random
from urllib.parse import quote
from telebot import types

from config import BOT_USERNAME, GUARDIAN_URL, ZOO_TG_CHANNEL
from data import ANIMALS, QUESTIONS


def kb_welcome():
    # Стартовый экран
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🚀 Начать викторину", callback_data="start_quiz"))
    kb.add(types.InlineKeyboardButton("ℹ️ О программе опеки", callback_data="learn_more"))
    kb.add(types.InlineKeyboardButton("❓ Помощь", callback_data="help"))
    return kb


def kb_question(q_idx):
    # Кнопки с вариантами ответа - порядок перемешан, чтобы у разных пользователей раскладка отличалась
    # В callback_data при этом храним исходный индекс
    options = list(enumerate(QUESTIONS[q_idx]["options"]))
    random.shuffle(options)
    kb = types.InlineKeyboardMarkup()
    for i, opt in options:
        kb.add(types.InlineKeyboardButton(opt["text"], callback_data=f"ans:{q_idx}:{i}"))
    return kb


def _share_text(animal_name):
    # Текст для шаринга — со встроенной ссылкой на бота
    return (f"Моё тотемное животное в Московском зоопарке — {animal_name}! "
            f"А кто ты? Узнай в боте: https://t.me/{BOT_USERNAME}")


def kb_result(animal_key):
    # Кнопки под итоговой карточкой животного
    name = ANIMALS[animal_key]["name"]
    bot_link = f"https://t.me/{BOT_USERNAME}"
    tg_share = f"https://t.me/share/url?url={quote(bot_link)}&text={quote(_share_text(name))}"

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❤️ Узнать о программе опеки", callback_data="learn_more"))
    kb.row(
        types.InlineKeyboardButton("📤 Поделиться", callback_data="share"),
        types.InlineKeyboardButton("📲 В Telegram", url=tg_share),
    )
    kb.row(
        types.InlineKeyboardButton("🔁 Ещё раз", callback_data="restart"),
        types.InlineKeyboardButton("✉️ Связаться", callback_data="contact"),
    )
    kb.add(types.InlineKeyboardButton("📝 Оставить отзыв", callback_data="feedback"))
    return kb


def kb_share(animal_key):
    # Меню площадок: Telegram, ВК, X, e-mail. Везде ссылка на бота.
    name = ANIMALS[animal_key]["name"]
    bot_link = f"https://t.me/{BOT_USERNAME}"
    text = _share_text(name)

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "📲 Telegram",
        url=f"https://t.me/share/url?url={quote(bot_link)}&text={quote(text)}"))
    kb.add(types.InlineKeyboardButton(
        "🔵 ВКонтакте",
        url=f"https://vk.com/share.php?url={quote(bot_link)}&title={quote(text)}"))
    kb.add(types.InlineKeyboardButton(
        "🐦 Twitter / X",
        url=f"https://twitter.com/intent/tweet?text={quote(text)}"))
    # Telegram не пускает mailto: в inline-кнопки — даём «копию текста» вместо письма
    kb.add(types.InlineKeyboardButton("📋 Скопировать текст", callback_data="copy_text"))
    kb.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_result"))
    return kb


def kb_restart():
    # Клавиатура с предложением начать заново
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔁 Попробовать ещё раз", callback_data="restart"))
    kb.add(types.InlineKeyboardButton("ℹ️ О программе опеки", callback_data="learn_more"))
    return kb


def kb_learn_more():
    # Кнопки под текстом о программе опеки
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🌐 Страница опеки", url=GUARDIAN_URL))
    kb.add(types.InlineKeyboardButton("📣 Канал зоопарка", url=ZOO_TG_CHANNEL))
    kb.add(types.InlineKeyboardButton("🚀 Пройти викторину", callback_data="start_quiz"))
    return kb


def kb_contact():
    # Кнопки под блоком контактов
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❤️ Программа опеки", url=GUARDIAN_URL))
    kb.add(types.InlineKeyboardButton("🔁 Ещё раз", callback_data="restart"))
    kb.add(types.InlineKeyboardButton("📝 Оставить отзыв", callback_data="feedback"))
    return kb
