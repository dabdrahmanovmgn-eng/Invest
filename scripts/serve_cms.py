"""Совместимый локальный запуск: теперь используется Django Admin."""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8345)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    if args.data_dir:
        os.environ["DJANGO_DATA_DIR"] = str(args.data_dir.resolve())
    raise SystemExit(subprocess.call([
        sys.executable, str(ROOT / "scripts/start_django.py"), "--port", str(args.port),
    ], cwd=ROOT))
