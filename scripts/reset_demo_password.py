"""Смена пароля существующего пользователя Django, без изменения старых баз CMS."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    root = Path(__file__).resolve().parents[1]
    python = root / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    if not python.is_file():
        raise SystemExit("Сначала запустите START-SITE.cmd. Инструкция: docs/DJANGO.md")
    username = input("Логин существующего пользователя Django: ").strip()
    if not username or username.startswith("-"):
        raise SystemExit("Укажите существующий логин.")
    raise SystemExit(subprocess.call([str(python), str(root / "manage.py"), "changepassword", username], cwd=root))
