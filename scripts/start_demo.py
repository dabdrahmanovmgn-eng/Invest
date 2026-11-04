"""Прежний ярлык запускает локальный Django без внешнего туннеля."""
import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    print("Теперь используется Django Admin. Запуск только на этом компьютере; внешний показ настраивается отдельно.", flush=True)
    raise SystemExit(subprocess.call([
        sys.executable, str(Path(__file__).with_name("start_django.py")), *sys.argv[1:],
    ]))
