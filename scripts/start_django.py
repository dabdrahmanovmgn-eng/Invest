"""Локальный запуск Django; без туннелей и внешней публикации."""
import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8345)
    parser.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Порт должен быть от 1 до 65535.")
    if os.environ.get("DJANGO_ENV", "local") != "local":
        parser.error("Этот запуск предназначен только для локального режима.")
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not python.is_file():
        if sys.version_info < (3, 11):
            parser.error("Нужен Python 3.11 или новее.")
        venv.create(ROOT / ".venv", with_pip=True)
    pinned = [line.strip().split("==") for line in (ROOT / "requirements.txt").read_text().splitlines() if "==" in line]
    probe = "import importlib.metadata,json; print(json.dumps({x:importlib.metadata.version(x) for x in " + repr([name for name, _ in pinned]) + "}))"
    result = subprocess.run([str(python), "-c", probe], cwd=ROOT, capture_output=True, text=True)
    import json
    installed = json.loads(result.stdout) if result.returncode == 0 else {}
    if installed != dict(pinned):
        subprocess.run([str(python), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")], cwd=ROOT, check=True)
    command = [str(python), str(ROOT / "manage.py")]
    subprocess.run(command + ["migrate", "--noinput"], cwd=ROOT, check=True)
    if args.prepare_only:
        print("Django подготовлен. Инструкции: docs/DJANGO.md", flush=True)
        return
    check = subprocess.run(command + ["shell", "-c", "from django.contrib.auth import get_user_model; raise SystemExit(0 if get_user_model().objects.filter(is_superuser=True,is_active=True).exists() else 2)"], cwd=ROOT)
    if check.returncode == 2:
        print("Создайте администратора. Пароль вводится только здесь и не отображается.", flush=True)
        subprocess.run(command + ["createsuperuser"], cwd=ROOT, check=True)
    elif check.returncode:
        raise SystemExit(check.returncode)
    print(f"Сайт: http://127.0.0.1:{args.port}/\nАдминка: http://127.0.0.1:{args.port}/admin/\nОстановка: Ctrl+C", flush=True)
    subprocess.run(command + ["runserver", f"127.0.0.1:{args.port}", "--noreload"], cwd=ROOT, check=True)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
