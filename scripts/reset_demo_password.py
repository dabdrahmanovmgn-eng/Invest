"""Смена забытого пароля существующего демо-аккаунта в локальной консоли владельца."""
import argparse
import getpass
import re
import sys
from pathlib import Path

from cms_store import CmsError, Store, password_hash
from serve_cms import validate_demo_directory

ROOT = Path(__file__).resolve().parents[1]
DEMO_DATA = ROOT / "data" / "demo"


def reset_existing_account(store, username, password, confirmation):
    """Обновить существующий аккаунт без чтения прежнего пароля или сессий."""
    validate_demo_directory(store.directory)
    if store.directory.resolve() != DEMO_DATA.resolve():
        raise CmsError("Восстановление разрешено только для отдельного data/demo.")
    if password != confirmation:
        raise CmsError("Пароли не совпали. Ничего не изменено.")
    encoded = password_hash(password)
    with store.connect() as database:
        database.execute("BEGIN IMMEDIATE")
        if not database.execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone():
            raise CmsError("Такого логина в демоверсии нет. Новый аккаунт не создан.")
        database.execute("UPDATE admins SET password=? WHERE username=?", (encoded, username))
        database.execute("DELETE FROM sessions WHERE username=?", (username,))


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    argparse.ArgumentParser(description=__doc__).parse_args()
    # getpass не должен переходить к открытому вводу из pipe или фонового запуска.
    if not sys.stdin.isatty() or not sys.stderr.isatty():
        raise CmsError("Запустите RESET-DEMO-PASSWORD.cmd в обычном окне консоли. Скрытый ввод пароля требует интерактивного запуска.")
    validate_demo_directory(DEMO_DATA)
    directory = DEMO_DATA.resolve()
    database = directory / "cms.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise CmsError("Отдельная демобаза не найдена. Сначала создайте аккаунт через START-DEMO.cmd.")
    print("ВОССТАНОВЛЕНИЕ ВХОДА В ДЕМО\nИзменяется только существующий аккаунт в data/demo. Статьи сохранятся.", flush=True)
    username = input("Введите существующий логин демо: ").strip()
    if not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
        raise CmsError("Введите существующий логин: 3–64 латинских символа, цифры, . _ @ -.")
    store = Store(directory)
    with store.connect() as connection:
        exists = connection.execute("SELECT 1 FROM admins WHERE username=?", (username,)).fetchone()
    if not exists:
        raise CmsError("Такого логина в демоверсии нет. Проверьте написание. Новый аккаунт не создан.")
    password = getpass.getpass("Новый пароль демо (от 12 символов): ")
    confirmation = getpass.getpass("Повторите новый пароль: ")
    reset_existing_account(store, username, password, confirmation)
    del password, confirmation
    print("Пароль демо изменён. Войдите тем же логином и новым паролем. Перезапуск демо не нужен. Статьи сохранены.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nВосстановление отменено.", file=sys.stderr)
        sys.exit(130)
    except (CmsError, OSError, ValueError, EOFError) as error:
        print(f"Вход не изменён: {error}", file=sys.stderr)
        sys.exit(1)
