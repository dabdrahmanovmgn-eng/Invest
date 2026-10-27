"""Временная демонстрация с компьютера владельца; внешний доступ включается явно."""
import argparse
import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path

from serve_cms import LocalCmsServer, validate_demo_directory

ROOT = Path(__file__).resolve().parents[1]
DEMO_DATA = ROOT / "data" / "demo"
TOOLS = ROOT / "work" / "demo-tools"
RELEASE_API = "https://api.github.com/repos/cloudflare/cloudflared/releases/latest"
ASSET_NAME = "cloudflared-windows-amd64.exe"
ORIGIN_PATTERN = re.compile(r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com(?=[\s|/]|$)")


def request(url):
    return urllib.request.Request(url, headers={"User-Agent": "DengiMarket-Demo/1", "Accept": "application/vnd.github+json" if url == RELEASE_API else "*/*"})


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def release_asset(release):
    for asset in release.get("assets", []):
        if asset.get("name") != ASSET_NAME:
            continue
        digest = asset.get("digest") or ""
        url = asset.get("browser_download_url", "")
        prefix = "https://github.com/cloudflare/cloudflared/releases/download/"
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", digest) or not url.startswith(prefix) or not url.endswith("/" + ASSET_NAME):
            raise RuntimeError("У официального файла нет ожидаемой контрольной суммы SHA-256.")
        if not 0 < asset.get("size", 0) < 128 * 1024 * 1024:
            raise RuntimeError("Неожиданный размер cloudflared.")
        return url, digest.removeprefix("sha256:"), asset["size"]
    raise RuntimeError("В официальном выпуске не найден cloudflared для Windows x64.")


def install_tunnel():
    """Скачивает только официальный файл и проверяет digest из GitHub API."""
    if os.name != "nt":
        raise RuntimeError("Этот запуск подготовлен для Windows x64.")
    TOOLS.mkdir(parents=True, exist_ok=True)
    binary = TOOLS / "cloudflared.exe"
    manifest = TOOLS / "cloudflared.json"
    if binary.is_file() and manifest.is_file():
        info = json.loads(manifest.read_text(encoding="utf-8"))
        if re.fullmatch(r"[a-f0-9]{64}", info.get("sha256", "")) and sha256(binary) == info["sha256"]:
            return binary
    print("Загружаю cloudflared с официального GitHub Cloudflare…", flush=True)
    with urllib.request.urlopen(request(RELEASE_API), timeout=30) as response:
        release = json.loads(response.read(2 * 1024 * 1024))
    url, expected, size = release_asset(release)
    partial = TOOLS / "cloudflared.download"
    try:
        with urllib.request.urlopen(request(url), timeout=30) as response, partial.open("wb") as output:
            count = 0
            while chunk := response.read(1024 * 1024):
                count += len(chunk)
                if count > size:
                    raise RuntimeError("Размер загрузки не совпал с официальным выпуском.")
                output.write(chunk)
        if count != size or sha256(partial) != expected:
            raise RuntimeError("Контрольная сумма cloudflared не совпала. Файл не запущен.")
        partial.replace(binary)
        manifest.write_text(json.dumps({"release": release.get("tag_name"), "sha256": expected, "source": url}, indent=2), encoding="utf-8")
    finally:
        partial.unlink(missing_ok=True)
    print("Официальный cloudflared сохранён; SHA-256 совпала.", flush=True)
    return binary


def tunnel_origin(line):
    match = ORIGIN_PATTERN.search(line)
    return match.group(0) if match else None


def start_tunnel(binary, port):
    # Отдельный пустой config не меняет настройки Cloudflare владельца компьютера.
    config = TOOLS / "demo-config.yml"
    config.write_text("{}\n", encoding="utf-8")
    command = [str(binary), "tunnel", "--no-autoupdate", "--config", str(config), "--protocol", "http2", "--metrics", "127.0.0.1:0", "--loglevel", "info", "--url", f"http://127.0.0.1:{port}"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    lines = queue.Queue()
    capture = threading.Event()
    capture.set()

    def read_output():
        for line in process.stdout:
            if capture.is_set():
                lines.put(line)
        lines.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    deadline = time.monotonic() + 55
    try:
        while time.monotonic() < deadline:
            try:
                line = lines.get(timeout=1)
            except queue.Empty:
                if process.poll() is not None:
                    break
                continue
            if line is None:
                break
            origin = tunnel_origin(line)
            if origin:
                capture.clear()
                return process, origin
        raise RuntimeError("Cloudflare не выдал ссылку. Проверьте интернет и повторите запуск.")
    except BaseException:
        stop_tunnel(process)
        raise


def stop_tunnel(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def check_external(origin):
    # Учётная запись уже настроена; endpoint не выдаёт setup-токен или пароль.
    for attempt in range(3):
        if attempt:
            time.sleep(attempt + 1)
        try:
            with urllib.request.urlopen(request(origin + "/api/session"), timeout=10) as response:
                info = json.loads(response.read(4096))
                if info.get("adminConfigured") is True and info.get("authenticated") is False:
                    return True
        except (OSError, ValueError):
            pass
    return False


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8346)
    parser.add_argument("--prepare-only", action="store_true", help="Только локальный первый вход; без внешнего доступа")
    parser.add_argument("--install-tunnel", action="store_true", help="Только скачать официальный cloudflared; без запуска туннеля")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--open-window", action="store_true", help="Открыть отдельное окно запуска для действий владельца")
    args = parser.parse_args()
    if args.open_window:
        if os.name != "nt":
            parser.error("Отдельное окно запуска доступно в Windows.")
        subprocess.Popen(["cmd.exe", "/c", "START-DEMO.cmd"], cwd=ROOT, creationflags=subprocess.CREATE_NEW_CONSOLE)
        print("Открыто окно запуска демоверсии. Создайте тестовый аккаунт в браузере и продолжите в этом окне.")
        return
    if args.install_tunnel:
        print(install_tunnel())
        return
    if not 0 < args.port < 65536:
        parser.error("Порт должен быть от 1 до 65535.")
    validate_demo_directory(DEMO_DATA)
    server = LocalCmsServer(("127.0.0.1", args.port), ROOT / "site", DEMO_DATA, cookie_prefix="dm_demo")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    process = None
    local = f"http://127.0.0.1:{args.port}"
    print(f"\nДЕМОВЕРСИЯ DENGI MARKET\nСайт: {local}/\nТестовая админка: {local}/admin/", flush=True)
    print("Тестовые статьи сохраняются отдельно в data/demo. Текущая CMS не переносится.", flush=True)
    try:
        if not args.no_browser:
            webbrowser.open(local + "/admin/")
        if args.prepare_only:
            print("Сейчас доступ только с этого компьютера. Остановка: Ctrl+C.", flush=True)
            while True:
                time.sleep(1)
        while not server.store.admin_configured():
            print("\nСначала создайте тестовый логин и пароль в открытой админке. Пароль сюда вводить не нужно.", flush=True)
            input("После создания аккаунта нажмите Enter: ")
        print("\nСледующий шаг откроет временную ссылку через Cloudflare.\nСайт будет доступен любому получателю ссылки; редактор — только по тестовому логину и паролю.\nПросмотр и пробные статьи проходят через Cloudflare. Ссылка работает, пока запущено это окно.\nУсловия Cloudflare: https://www.cloudflare.com/terms/\nДля завершения показа нажмите Ctrl+C. При повторном запуске адрес изменится.", flush=True)
        if input("Открыть временный доступ? Введите ДА: ").strip().casefold() not in ("да", "yes"):
            print("Внешний доступ не включён.", flush=True)
            return
        binary = install_tunnel()
        process, origin = start_tunnel(binary, args.port)
        server.set_public_origin(origin)
        print("Проверяю внешнюю ссылку…", flush=True)
        if not check_external(origin):
            raise RuntimeError("Проверка внешнего доступа не прошла. Туннель остановлен; повторите запуск.")
        output = ROOT / "work" / "demo" / "links.txt"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(f"Сайт: {origin}/\nАдминка: {origin}/admin/\nСтатьи: {origin}/articles/\n\nРаботает, пока запущена демонстрация. Пароль передайте получателям отдельно.\n", encoding="utf-8")
        print(f"\nГОТОВО. МОЖНО ПЕРЕДАВАТЬ ССЫЛКИ:\nСайт: {origin}/\nАдминка: {origin}/admin/\nСтатьи: {origin}/articles/\n\nСсылки также сохранены: {output}\nЛогин и пароль передайте руководству отдельно. Все редакторы работают с общей тестовой базой.\nОстановка показа: Ctrl+C. Не выключайте компьютер и не переводите его в сон во время показа.", flush=True)
        if not args.no_browser:
            webbrowser.open(origin)
        process.wait()
        print("Туннель завершён. Для нового показа запустите START-DEMO.cmd снова.", flush=True)
    except KeyboardInterrupt:
        print("\nДемонстрация остановлена.", flush=True)
    finally:
        stop_tunnel(process)
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, ValueError, EOFError) as error:
        print(f"Не удалось запустить демонстрацию: {error}", file=sys.stderr, flush=True)
        sys.exit(1)
