# Скрипт на автоматизированный запуск бота.
#
# Нужен на случай, когда у пользователя в терминале нет активированного venv
# (например, открыто новое окно — а там conda base активна, или вообще
# системный python). Скрипт сам создаст виртуальное окружение в .venv,
# доустановит зависимости из requirements.txt и запустит bot.py внутри venv.
#
# Использование:
#   python run.py        (macOS / Linux / Windows)
#   py run.py            (Windows, через Python Launcher)


import os
import subprocess
import sys
import venv

ROOT = os.path.dirname(os.path.abspath(__file__))
VENV_DIR = os.path.join(ROOT, ".venv")
REQS = os.path.join(ROOT, "requirements.txt")
BOT = os.path.join(ROOT, "bot.py")


def venv_python_path():
    # Путь к python внутри .venv с учётом разной структуры на Windows и Unix
    if os.name == "nt":
        return os.path.join(VENV_DIR, "Scripts", "python.exe")
    return os.path.join(VENV_DIR, "bin", "python")


def main():
    # Если виртуального окружения ещё нет — создадем
    if not os.path.isdir(VENV_DIR):
        print("Создаю виртуальное окружение в .venv ...")
        venv.create(VENV_DIR, with_pip=True)

    py = venv_python_path()
    if not os.path.exists(py):
        print(f"Не нашёл python в {VENV_DIR}. "
              "Удалите папку .venv и запустите run.py ещё раз.")
        sys.exit(1)

    # Поставим/обновим зависимости
    print("Проверяю зависимости из requirements.txt ...")
    subprocess.check_call([py, "-m", "pip", "install", "-q", "-r", REQS])

    # Запускаем bot.py внутри venv. execv заменяет текущий процесс,
    # чтобы Ctrl+C попадал прямо в бота, а не в этот скрипт.
    print("Запускаю бота...\n")
    if os.name == "nt":
        # На Windows execv ведёт себя странно с Ctrl+C, безопаснее subprocess
        sys.exit(subprocess.call([py, BOT]))
    else:
        os.execv(py, [py, BOT])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
