# Telegram-бот «Какое у вас тотемное животное?» (сделано для Московского зоопарка)
# Итоговая работа по дисциплине "Язык программирования пайтон"
# Запуск: python bot.py (предварительно необходимо заполнить .env)

import csv
import logging
import os
import sys
import urllib.request
from datetime import datetime
from threading import Lock
from urllib.parse import quote

try:
    import telebot
    from telebot import types
except ModuleNotFoundError:
    # Самая частая засада: пользователь запустил python из системного окружения
    # (например, conda base), где нет наших зависимостей. Подсказываем способы.
    print(
        "\nНе установлен пакет pyTelegramBotAPI.\n\n"
        "Самый простой способ запустить — через лаунчер,\n"
        "он сам создаст виртуальное окружение и поставит зависимости:\n"
        "    python run.py\n\n"
        "Либо вручную:\n"
        "    python -m venv .venv\n"
        "    source .venv/bin/activate     # Windows: .venv\\Scripts\\activate\n"
        "    pip install -r requirements.txt\n"
        "    python bot.py\n"
    )
    sys.exit(1)

from config import (
    BOT_TOKEN, BOT_USERNAME, ADMIN_CHAT_ID,
    ADMIN_USERNAME, ADMIN_EMAIL, ADMIN_PHONE,
    GUARDIAN_URL, FEEDBACK_FILE,
)
from data import ANIMALS, QUESTIONS
from keyboards import (
    kb_welcome, kb_question, kb_result, kb_share,
    kb_restart, kb_learn_more, kb_contact,
)

# Логирование (в файл и в консоль)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# threaded=True — обслуживание нескольких пользователей одновременно
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=True)

# Состояния пользователей в памяти.
# user_id -> {"q": номер вопроса, "scores": {животное: очки},
#            "result": ключ_животного, "wait_feedback": bool}
states = {}
fb_lock = Lock()  # чтобы запись отзывов из разных потоков не пересекалась


# Тексты
WELCOME = (
    "<b>Привет!</b> 👋\n\n"
    "Я — бот-викторина Московского зоопарка. За пару минут помогу узнать, "
    "какое <b>тотемное животное</b> живёт в твоём характере, и расскажу о "
    "программе <b>«Возьми животное под опеку»</b>.\n\n"
    f"В викторине {len(QUESTIONS)} вопросов с долей юмора и реальных фактов о "
    "наших зверях. Правильных ответов нет — отвечай как чувствуешь.\n\n"
    "<i>Жми «Начать», когда будешь готов.</i>"
)

HELP = (
    "<b>Команды бота:</b>\n"
    "/start — стартовый экран\n"
    "/quiz — пройти викторину\n"
    "/about — о программе опеки\n"
    "/contact — связаться с сотрудником\n"
    "/feedback — оставить отзыв\n"
    "/privacy — какие данные собирает бот\n"
    "/cancel — отменить ввод (например, отзыв)\n"
)

ABOUT = (
    "<b>Программа «Возьми животное под опеку»</b> 🐾\n\n"
    "В Московском зоопарке живут около <b>6 000 животных</b> примерно "
    "<b>1 100 видов</b>. Каждое уникально, и каждому нужна забота. "
    "Опека — это пожертвование на любую сумму, которое помогает зоопарку "
    "развиваться и сохранять биоразнообразие планеты. Стоимость опеки "
    "рассчитывается из ежедневного рациона животного.\n\n"
    "<b>Что получает опекун:</b>\n"
    "• почётный статус опекуна;\n"
    "• возможность круглый год навещать подопечного;\n"
    "• новости о его жизни и самочувствии;\n"
    "• ощущение, что ты реально помогаешь живому существу.\n\n"
    f"Подробности и оформление: {GUARDIAN_URL}"
)

PRIVACY = (
    "<b>Какие данные собирает бот</b> 🔐\n\n"
    "• Ваши Telegram-id и имя — пока вы проходите викторину, "
    "чтобы помнить ваши ответы.\n"
    "• Текст вашего отзыва, если вы его оставите.\n"
    "• Запрос на связь — вместе с результатом викторины передаётся "
    "сотруднику зоопарка.\n\n"
    "Бот не запрашивает телефон, e-mail, геолокацию или платёжные данные."
)


# Работа с состоянием

def get_state(user_id):
    # Получить состояние пользователя, а если его нет — создать пустое
    if user_id not in states:
        states[user_id] = {
            "q": 0,
            "scores": {key: 0 for key in ANIMALS},
            "result": None,
            "wait_feedback": False,
        }
    return states[user_id]


def reset_state(user_id):
    # Полный сброс — например, перед новым прохождением
    states[user_id] = {
        "q": 0,
        "scores": {key: 0 for key in ANIMALS},
        "result": None,
        "wait_feedback": False,
    }


# Картинки животных (fallback на дозагрузку)

IMG_DIR = "images"


def ensure_images():
    # Картинки лежат в папке images/. Если какая-то вдруг отсутствует
    # пробуем дотянуть её с Wikimedia Commons. Если не получилось — бот всё равно
    # запустится, просто пользователь увидит результат без фото.
    os.makedirs(IMG_DIR, exist_ok=True)
    for key, info in ANIMALS.items():
        path = info.get("image")
        wiki = info.get("image_source")
        if not path:
            continue
        if os.path.exists(path) and os.path.getsize(path) > 1000:
            continue  # файл уже на месте — ничего не делаем
        if not wiki:
            log.warning("Картинки %s нет, и нечем её скачать.", path)
            continue
        url = (f"https://commons.wikimedia.org/wiki/Special:FilePath/"
               f"{quote(wiki)}?width=800")
        log.info("Картинки %s нет — скачиваю с Wikimedia (%s)", path, wiki)
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "MoscowZooBot/1.0 (educational)"}
            )
            with urllib.request.urlopen(req, timeout=30) as r, open(path, "wb") as f:
                f.write(r.read())
        except Exception as e:
            log.warning("Не удалось скачать %s: %s", path, e)


# Сохранение отзыва

def save_feedback(user_id, username, text):
    # Дописываем строку в CSV. При первой записи добавляем заголовок.
    is_new = not os.path.exists(FEEDBACK_FILE)
    row = [
        datetime.now().isoformat(timespec="seconds"),
        user_id,
        username or "",
        (text or "").replace("\n", " ").strip(),
    ]
    with fb_lock:
        with open(FEEDBACK_FILE, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if is_new:
                w.writerow(["timestamp", "user_id", "username", "text"])
            w.writerow(row)


# Команды

@bot.message_handler(commands=["start"])
def on_start(m):
    reset_state(m.from_user.id)
    bot.send_message(m.chat.id, WELCOME, reply_markup=kb_welcome())


@bot.message_handler(commands=["help"])
def on_help(m):
    bot.send_message(m.chat.id, HELP)


@bot.message_handler(commands=["about"])
def on_about(m):
    bot.send_message(m.chat.id, ABOUT, reply_markup=kb_learn_more(),
                     disable_web_page_preview=True)


@bot.message_handler(commands=["privacy"])
def on_privacy(m):
    bot.send_message(m.chat.id, PRIVACY)


@bot.message_handler(commands=["quiz"])
def on_quiz(m):
    start_quiz(m.chat.id, m.from_user.id)


@bot.message_handler(commands=["feedback"])
def on_feedback_cmd(m):
    s = get_state(m.from_user.id)
    s["wait_feedback"] = True
    bot.send_message(m.chat.id,
        "Поделись впечатлениями о боте — что понравилось, а что можно улучшить? "
        "Напиши одним сообщением. /cancel — отменить.")


@bot.message_handler(commands=["contact"])
def on_contact_cmd(m):
    send_contacts(m.chat.id, m.from_user)


@bot.message_handler(commands=["cancel"])
def on_cancel(m):
    reset_state(m.from_user.id)
    bot.send_message(m.chat.id, "Окей, отменил. /start — начать заново.",
                     reply_markup=kb_restart())


# Логика нашей мини викторины

def start_quiz(chat_id, user_id):
    # Сбрасываем счёт и показываем первый вопрос
    reset_state(user_id)
    send_question(chat_id, user_id)


def send_question(chat_id, user_id, msg_id=None):
    # Показываем текущий вопрос. Если задан msg_id, то пытаемся отредактировать.
    s = get_state(user_id)
    idx = s["q"]
    text = f"<b>Вопрос {idx + 1} / {len(QUESTIONS)}</b>\n\n{QUESTIONS[idx]['text']}"
    kb = kb_question(idx)
    if msg_id is not None:
        try:
            bot.edit_message_text(text, chat_id=chat_id, message_id=msg_id, reply_markup=kb)
            return
        except Exception:
            # Сообщение с фото редактировать нельзя
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


# Кеш file_id, чтобы повторно не загружать одну и ту же картинку. После того
# как любой пользователь получил, например, манула или слоника, Telegram запоминает картинку
# по file_id, и в дальнейшем она прилетает мгновенно.
_file_id_cache = {}


def _wiki_image_url(animal):
    # Собираем URL картинки на Wikimedia Commons из имени файла.
    wiki = animal.get("image_source")
    if not wiki:
        return None
    return ("https://commons.wikimedia.org/wiki/Special:FilePath/"
            f"{quote(wiki)}?width=800")


def _send_animal_photo(chat_id, animal_key, caption, kb):
    # Пробуем отправить фото в три попытки
    # по file_id - мгновенно, если картинку уже отправляли
    # по URL Wikimedia - Telegram сам кеширует
    # локальный файл - это наш резерв, если URL не сработал.
    # Если ничего не сработало пользователь всё равно получит текстовый результат
    animal = ANIMALS[animal_key]
    sent = None

    if animal_key in _file_id_cache:
        try:
            sent = bot.send_photo(chat_id, _file_id_cache[animal_key],
                                  caption=caption, reply_markup=kb)
        except Exception:
            _file_id_cache.pop(animal_key, None)  # устаревший file_id

    if sent is None:
        url = _wiki_image_url(animal)
        if url:
            try:
                sent = bot.send_photo(chat_id, url, caption=caption, reply_markup=kb)
            except Exception as e:
                log.warning("Не удалось через URL для %s: %s", animal_key, e)

    if sent is None:
        path = animal.get("image")
        if path and os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    sent = bot.send_photo(chat_id, f, caption=caption, reply_markup=kb)
            except Exception as e:
                log.warning("Не удалось локальный файл %s: %s", path, e)

    if sent is None:
        log.warning("Фото для %s не отправлено — отдаю текст", animal_key)
        bot.send_message(chat_id, caption, reply_markup=kb)
        return

    # Запоминаем file_id, чтобы следующая отправка была мгновенной
    if sent.photo:
        _file_id_cache[animal_key] = sent.photo[-1].file_id


def finish_quiz(chat_id, user_id):
    # Считаем победителя и показываем карточку животного с фото
    s = get_state(user_id)
    winner = max(s["scores"], key=lambda k: s["scores"][k])
    s["result"] = winner
    animal = ANIMALS[winner]

    caption = (
        f"🎉 Готово!\n\n"
        f"Твоё тотемное животное в Московском зоопарке — <b>{animal['name']}</b>.\n"
        f"<i>{animal['title']}</i>\n\n"
        f"{animal['description']}\n\n"
        f"<b>А знаешь ли ты?</b>\n{animal['fact']}\n\n"
        f"💚 Этого зверя можно <b>взять под опеку</b>: пожертвованием "
        f"на любую сумму ты помогаешь кормить и беречь живых обитателей зоопарка."
    )
    try:
        _send_animal_photo(chat_id, winner, caption, kb_result(winner))
    except Exception as e:
        # Совсем неожиданная ошибка — пользователь должен увидеть хотя бы текст
        log.warning("finish_quiz: непредвиденная ошибка для %s: %s", winner, e)
        bot.send_message(chat_id, caption, reply_markup=kb_result(winner))


# Обработчики кнопок

@bot.callback_query_handler(func=lambda c: c.data == "start_quiz")
def cb_start(call):
    start_quiz(call.message.chat.id, call.from_user.id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "help")
def cb_help(call):
    bot.send_message(call.message.chat.id, HELP)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "learn_more")
def cb_learn(call):
    bot.send_message(call.message.chat.id, ABOUT,
                     reply_markup=kb_learn_more(),
                     disable_web_page_preview=True)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("ans:"))
def cb_answer(call):
    # Формат callback'а: "ans:<номер_вопроса>:<номер_варианта>"
    _, q_s, opt_s = call.data.split(":")
    q_idx, opt_idx = int(q_s), int(opt_s)
    s = get_state(call.from_user.id)

    # Если кликнули по старой кнопке от уже пройденного вопроса - игнорируем его
    if q_idx != s["q"]:
        bot.answer_callback_query(call.id, "Этот вопрос уже пройден")
        return

    # Начисляем веса всем животным из выбранного варианта
    for key, weight in QUESTIONS[q_idx]["options"][opt_idx]["scores"].items():
        s["scores"][key] = s["scores"].get(key, 0) + weight
    s["q"] += 1

    if s["q"] < len(QUESTIONS):
        send_question(call.message.chat.id, call.from_user.id, call.message.message_id)
    else:
        finish_quiz(call.message.chat.id, call.from_user.id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "restart")
def cb_restart(call):
    reset_state(call.from_user.id)
    bot.send_message(call.message.chat.id, WELCOME, reply_markup=kb_welcome())
    bot.answer_callback_query(call.id, "Поехали заново!")


@bot.callback_query_handler(func=lambda c: c.data == "share")
def cb_share(call):
    s = get_state(call.from_user.id)
    if not s.get("result"):
        bot.answer_callback_query(call.id, "Сначала пройди викторину", show_alert=True)
        return
    name = ANIMALS[s["result"]]["name"]
    bot.send_message(
        call.message.chat.id,
        f"Поделись результатом — друзьям тоже захочется проверить себя 😉\n\n"
        f"<i>«Моё тотемное животное в Московском зоопарке — {name}!»</i>",
        reply_markup=kb_share(s["result"]),
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "back_to_result")
def cb_back(call):
    s = get_state(call.from_user.id)
    if not s.get("result"):
        bot.answer_callback_query(call.id)
        return
    bot.send_message(call.message.chat.id, "Что дальше?",
                     reply_markup=kb_result(s["result"]))
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "copy_text")
def cb_copy_text(call):
    # Присылаем готовый текст - его можно зажать и скопировать
    s = get_state(call.from_user.id)
    if not s.get("result"):
        bot.answer_callback_query(call.id)
        return
    name = ANIMALS[s["result"]]["name"]
    text = (f"Моё тотемное животное в Московском зоопарке — {name}! "
            f"А кто ты? Узнай в боте: https://t.me/{BOT_USERNAME}")
    bot.send_message(
        call.message.chat.id,
        f"Зажми сообщение ниже и скопируй текст — его можно отправить куда угодно:\n\n<code>{text}</code>"
    )
    bot.answer_callback_query(call.id, "Готово, скопируй сообщение")


@bot.callback_query_handler(func=lambda c: c.data == "contact")
def cb_contact(call):
    send_contacts(call.message.chat.id, call.from_user)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data == "feedback")
def cb_feedback(call):
    s = get_state(call.from_user.id)
    s["wait_feedback"] = True
    bot.send_message(call.message.chat.id,
        "Расскажи, что понравилось и что можно улучшить. "
        "Напиши одним сообщением. /cancel — отменить.")
    bot.answer_callback_query(call.id)


# Контакты администрации

def send_contacts(chat_id, user):
    # Показываем контакты пользователю и пересылаем результат админу
    text = "<b>Связаться с сотрудником зоопарка:</b>\n\n"
    if ADMIN_USERNAME:
        text += f"💬 Telegram: @{ADMIN_USERNAME}\n"
    if ADMIN_EMAIL:
        text += f"📧 E-mail: {ADMIN_EMAIL}\n"
    if ADMIN_PHONE:
        text += f"📞 Телефон: {ADMIN_PHONE}\n"
    if not (ADMIN_USERNAME or ADMIN_EMAIL or ADMIN_PHONE):
        text += "<i>Контакты ещё не настроены — заполните их в .env.</i>\n"
    text += ("\nЯ уже передал твой результат сотруднику, чтобы он мог "
             "лучше ответить на вопросы.")
    bot.send_message(chat_id, text, reply_markup=kb_contact())

    # Пересылка администратору (если ADMIN_CHAT_ID указан в .env)
    if ADMIN_CHAT_ID:
        s = get_state(user.id)
        animal_name = ANIMALS[s["result"]]["name"] if s.get("result") else "(не пройдена)"
        uname = f"@{user.username}" if user.username else "(без username)"
        try:
            bot.send_message(
                ADMIN_CHAT_ID,
                f"<b>📨 Запрос на связь</b>\n"
                f"От: {user.first_name or ''} {user.last_name or ''} {uname} "
                f"(id <code>{user.id}</code>)\n"
                f"Результат викторины: <b>{animal_name}</b>"
            )
        except Exception as e:
            log.error("Не удалось переслать запрос админу: %s", e)


# Текстовые сообщения (отзыв или подсказка)

@bot.message_handler(content_types=["text"])
def on_text(m):
    s = get_state(m.from_user.id)

    # Если ждём отзыв - сохраняем и пересылаем админу
    if s.get("wait_feedback"):
        s["wait_feedback"] = False
        save_feedback(m.from_user.id, m.from_user.username or "", m.text)
        bot.send_message(m.chat.id, "Спасибо! 💚 Твой отзыв поможет сделать бота лучше.",
                         reply_markup=kb_restart())
        if ADMIN_CHAT_ID:
            try:
                uname = f"@{m.from_user.username}" if m.from_user.username else "(без username)"
                bot.send_message(
                    ADMIN_CHAT_ID,
                    f"<b>📝 Новый отзыв</b>\n"
                    f"От: {m.from_user.first_name or ''} {uname}\n\n{m.text}"
                )
            except Exception as e:
                log.error("Не удалось переслать отзыв админу: %s", e)
        return

    # Если идёт викторина - подсказка кликнуть кнопку
    if 0 < s.get("q", 0) < len(QUESTIONS):
        bot.send_message(m.chat.id,
            "Чтобы продолжить викторину, выбери вариант ответа кнопкой выше 👆")
        return

    # Общая подсказка
    bot.send_message(m.chat.id,
        "Я понимаю кнопки и команды. /start — начать заново, /help — список команд.",
        reply_markup=kb_restart())


# Запуск

def setup_commands():
    # Меню команд в Telegram-клиенте (значок «/» рядом со скрепкой)
    bot.set_my_commands([
        types.BotCommand("start", "Начать"),
        types.BotCommand("quiz", "Пройти викторину"),
        types.BotCommand("about", "О программе опеки"),
        types.BotCommand("contact", "Связаться с сотрудником"),
        types.BotCommand("feedback", "Оставить отзыв"),
        types.BotCommand("privacy", "О данных"),
        types.BotCommand("help", "Помощь"),
    ])


if __name__ == "__main__":
    ensure_images()        # проверяем картинки, при необходимости докачиваем
    setup_commands()
    log.info("Бот запущен")
    # infinity_polling сам перезапустится при сетевых ошибках
    bot.infinity_polling(skip_pending=True)
