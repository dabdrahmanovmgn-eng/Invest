"""Локальная CMS и отдельная кратковременная демоверсия через HTTPS-туннель."""
import argparse
import getpass
import hashlib
import hmac
import json
import logging
import mimetypes
import re
import secrets
import socket
import sqlite3
import sys
import threading
import time
from collections import defaultdict, deque
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from cms_store import CmsError, SESSION_SECONDS, Store

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COOKIE_PREFIX = "dm_cms"
COOKIE_PREFIX = re.compile(r"[a-z][a-z0-9_]{0,31}\Z")
SETUP_SECONDS = 15 * 60
MAX_JSON = 12 * 1024 * 1024
LOGGER = logging.getLogger("dengi.cms")
DEMO_ORIGIN = re.compile(r"https://[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.trycloudflare\.com\Z")
WORKING_DATA = ROOT / "data" / "cms"


def validate_demo_origin(origin):
    if not isinstance(origin, str) or not DEMO_ORIGIN.fullmatch(origin):
        raise ValueError("Для демо нужен точный HTTPS-адрес вида https://имя.trycloudflare.com без пути и порта.")
    return origin


def validate_demo_directory(directory):
    if Path(directory).resolve().is_relative_to(WORKING_DATA.resolve()):
        raise ValueError("Демо должно использовать отдельное хранилище вне рабочего data/cms/.")


class LocalCmsServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True

    def __init__(self, address, site, data, *, public_origin=None, cookie_prefix=None):
        if address[0] != "127.0.0.1":
            raise ValueError("CMS допускает только локальный адрес 127.0.0.1.")
        prefix = DEFAULT_COOKIE_PREFIX if cookie_prefix is None else cookie_prefix
        if not isinstance(prefix, str) or not COOKIE_PREFIX.fullmatch(prefix):
            raise ValueError("Префикс cookie: 1–32 символа a-z, 0-9, _, начиная с буквы.")
        self.session_cookie = f"{prefix}_session"
        self.setup_cookie = f"{prefix}_setup"
        self.site = Path(site).resolve()
        if Path(data).resolve().is_relative_to(self.site):
            raise ValueError("Каталог CMS должен находиться вне публичного site/.")
        # Проверить до открытия Store: публичный режим не читает рабочую базу.
        if public_origin is not None:
            validate_demo_origin(public_origin)
            validate_demo_directory(data)
        self.store = Store(data)
        self._public_origin = None
        self.demo_lock = threading.Lock()
        if public_origin is not None:
            self.set_public_origin(public_origin)
        # Только текущий процесс может выдавать одноразовые токены первого входа.
        self.setup_secret = secrets.token_bytes(32)
        self.attempts = defaultdict(deque)
        self.attempt_lock = threading.Lock()
        super().__init__(address, CmsHandler)

    @property
    def public_origin(self):
        return self._public_origin

    def set_public_origin(self, origin):
        """Атомарно разрешить ровно один адрес уже настроенной отдельной демо-CMS.

        Сетевого маршрута активации нет: метод вызывает только локальный launcher.
        Приложение продолжает слушать только loopback; HTTPS завершается туннелем.
        """
        validated = validate_demo_origin(origin)
        validate_demo_directory(self.store.directory)
        with self.demo_lock:
            if not self.store.admin_configured():
                raise ValueError("Сначала создайте аккаунт демо локально; внешний первый вход запрещён.")
            self._public_origin = validated

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()

    def login_allowed(self, key):
        stamp = time.monotonic()
        with self.attempt_lock:
            attempts = self.attempts[key]
            while attempts and attempts[0] < stamp - 60:
                attempts.popleft()
            if len(attempts) >= 10:
                return False
            attempts.append(stamp)
            return True


class CmsHandler(BaseHTTPRequestHandler):
    server_version = "DengiMarketLocal/1"
    sys_version = ""
    protocol_version = "HTTP/1.0"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *arguments):
        # Не записывать URL-параметры, Cookie, пароли и тело запроса в журнал.
        if arguments:
            LOGGER.info("CMS %s: %s", getattr(self, "command", "-"), getattr(self, "response_code", "-"))

    def respond(self, status, body, content_type="application/json; charset=utf-8", headers=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode("utf-8")
        elif isinstance(body, str):
            body = body.encode("utf-8")
        self.response_code = status
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        if self.server.public_origin:
            self.send_header("X-Robots-Tag", "noindex, nofollow")
        if self.path.startswith(("/admin", "/article", "/api")):
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; form-action 'self'; object-src 'none'")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def check_host(self):
        port = self.server.server_port
        valid = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            valid.update({"127.0.0.1", "localhost"})
        public_origin = self.server.public_origin
        if public_origin:
            valid.add(urlsplit(public_origin).netloc)
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0] not in valid:
            raise CmsError("Недопустимый Host.", 403, "invalid_host")

    def external_request(self):
        public_origin = self.server.public_origin
        return bool(public_origin and self.headers.get("Host") == urlsplit(public_origin).netloc)

    def same_origin(self):
        origins = self.headers.get_all("Origin", [])
        expected = self.server.public_origin if self.external_request() else "http://" + self.headers["Host"]
        if len(origins) != 1 or origins[0] != expected or self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise CmsError("Разрешены только запросы с этого сайта.", 403, "invalid_origin")

    def session(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            name = self.server.session_cookie
            token = cookies[name].value if name in cookies else ""
        except Exception:
            token = ""
        return token, self.server.store.session(token)

    def admin(self, mutation=False):
        token, session = self.session()
        if not session:
            raise CmsError("Войдите в редактор.", 401, "authentication_required")
        supplied_csrf = self.headers.get("X-CSRF-Token", "")
        if mutation and not hmac.compare_digest(supplied_csrf.encode("utf-8"), session["csrf"].encode("ascii")):
            raise CmsError("Обновите страницу редактора и повторите действие.", 403, "invalid_csrf")
        return token, session

    def read_json(self, limit=512_000):
        if self.headers.get("Transfer-Encoding"):
            raise CmsError("Transfer-Encoding не поддерживается.")
        if len(self.headers.get_all("Content-Length", [])) != 1:
            raise CmsError("Нужен Content-Length.", 411)
        try:
            length = int(self.headers["Content-Length"])
        except ValueError:
            raise CmsError("Некорректный Content-Length.") from None
        if length < 1 or length > limit:
            raise CmsError("Слишком большой запрос.", 413, "request_too_large")
        if self.headers.get_content_type() != "application/json":
            raise CmsError("Нужен application/json.", 415, "unsupported_content_type")
        raw = self.rfile.read(length)
        if len(raw) != length:
            raise CmsError("Неполный запрос.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError, RecursionError):
            raise CmsError("Некорректный JSON.") from None
        if not isinstance(payload, dict):
            raise CmsError("Нужен объект JSON.")
        return payload

    def cookie(self, token, clear=False):
        secure = "; Secure" if self.external_request() else ""
        return {"Set-Cookie": f"{self.server.session_cookie}={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={0 if clear else SESSION_SECONDS}{secure}"}

    def setup_cookie_value(self):
        try:
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            name = self.server.setup_cookie
            value = cookies[name].value if name in cookies else ""
            if re.fullmatch(r"[0-9a-f]{64}\.[0-9]{1,12}", value):
                age = time.time() - int(value.rsplit(".", 1)[1])
                if 0 <= age < SETUP_SECONDS:
                    return value
        except (CookieError, ValueError, TypeError):
            pass
        return ""

    def setup_token(self, value):
        return hmac.new(self.server.setup_secret, value.encode("ascii"), hashlib.sha256).hexdigest()

    def first_setup_session(self):
        if self.external_request():
            raise CmsError("Первый аккаунт создаётся только локально до открытия демо.", 403, "local_setup_only")
        value = self.setup_cookie_value() or f"{secrets.token_hex(32)}.{int(time.time())}"
        headers = {"Set-Cookie": f"{self.server.setup_cookie}={value}; Path=/api/; HttpOnly; SameSite=Strict; Max-Age={SETUP_SECONDS}"}
        return self.setup_token(value), headers

    def verify_setup_token(self):
        value = self.setup_cookie_value()
        supplied = self.headers.get("X-Setup-Token", "")
        if not value or not re.fullmatch(r"[0-9a-f]{64}", supplied) or not hmac.compare_digest(supplied, self.setup_token(value)):
            raise CmsError("Обновите страницу первого входа и повторите действие.", 403, "invalid_setup_token")

    def dispatch(self):
        self.check_host()
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if "\x00" in path or "\\" in path or any(segment in (".", "..") for segment in path.split("/")):
            raise CmsError("Путь не найден.", 404, "not_found")
        method = "GET" if self.command == "HEAD" else self.command
        if method in ("POST", "PUT", "DELETE", "PATCH"):
            self.same_origin()
        store = self.server.store
        if path.startswith("/api/"):
            if path == "/api/session" and method == "GET":
                _, session = self.session()
                configured = store.admin_configured()
                result = {"authenticated": bool(session), "csrf": session["csrf"] if session else None, "username": session["username"] if session else None, "adminConfigured": configured}
                headers = None
                if not configured:
                    result["setupCsrf"], headers = self.first_setup_session()
                self.respond(200, result, headers=headers)
            elif path == "/api/setup" and method == "POST":
                if self.external_request():
                    raise CmsError("Первый аккаунт создаётся только локально до открытия демо.", 403, "local_setup_only")
                if store.admin_configured():
                    raise CmsError("Первый вход уже настроен. Войдите с существующим аккаунтом.", 409, "setup_complete")
                self.verify_setup_token()
                if not self.server.login_allowed(self.client_address[0]):
                    raise CmsError("Слишком много попыток. Подождите минуту.", 429, "rate_limited")
                data = self.read_json(4096)
                username = data.get("username")
                token, csrf = store.create_first_admin(username, data.get("password"))
                self.respond(201, {"authenticated": True, "csrf": csrf, "username": username, "adminConfigured": True}, headers=self.cookie(token))
            elif path == "/api/login" and method == "POST":
                if not self.server.login_allowed(self.client_address[0]):
                    raise CmsError("Слишком много попыток. Подождите минуту.", 429, "rate_limited")
                data = self.read_json(4096)
                username, password = data.get("username"), data.get("password")
                if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username) or not isinstance(password, str) or len(password) > 1024:
                    raise CmsError("Неверный логин или пароль.", 401, "invalid_credentials")
                login = store.authenticate(username, password)
                if not login:
                    raise CmsError("Неверный логин или пароль.", 401, "invalid_credentials")
                old_token, _ = self.session()
                if old_token:
                    store.logout(old_token)
                token, csrf = login
                self.respond(200, {"authenticated": True, "csrf": csrf, "username": username}, headers=self.cookie(token))
            elif path == "/api/logout" and method == "POST":
                token, _ = self.admin(True)
                self.read_json(4096)
                store.logout(token)
                self.respond(200, {"authenticated": False, "csrf": None}, headers=self.cookie("", True))
            elif path == "/api/articles" and method == "GET":
                language = parse_qs(parsed.query).get("language", [None])[0]
                if language not in (None, "en", "ru"):
                    raise CmsError("Недопустимый язык.")
                self.respond(200, {"articles": store.list_articles(language, True)})
            elif path.startswith("/api/articles/") and method == "GET":
                self.respond(200, {"article": store.get_article(path.removeprefix("/api/articles/"), True)})
            elif path == "/api/admin/articles" and method == "GET":
                self.admin()
                self.respond(200, {"articles": store.list_articles()})
            elif path == "/api/admin/articles" and method == "POST":
                self.admin(True)
                self.respond(201, {"article": store.save_article(self.read_json())})
            elif re.fullmatch(r"/api/admin/articles/[0-9a-f]{32}", path) and method == "GET":
                self.admin()
                self.respond(200, {"article": store.get_article(path.rsplit("/", 1)[1])})
            elif re.fullmatch(r"/api/admin/articles/[0-9a-f]{32}", path) and method == "PUT":
                self.admin(True)
                self.respond(200, {"article": store.save_article(self.read_json(), path.rsplit("/", 1)[1])})
            elif path == "/api/uploads" and method == "POST":
                self.admin(True)
                self.respond(201, store.upload(self.read_json(MAX_JSON)))
            else:
                raise CmsError("Маршрут API не найден.", 404, "not_found")
            return
        if method != "GET":
            raise CmsError("Метод не поддерживается.", 405, "method_not_allowed")
        if path.startswith("/uploads/"):
            _, session = self.session()
            target, mime = store.image(path, bool(session))
        else:
            if any(segment.startswith(".") for segment in path.split("/")):
                raise CmsError("Страница не найдена.", 404, "not_found")
            target = (self.server.site / path.lstrip("/")).resolve()
            try:
                target.relative_to(self.server.site)
            except ValueError:
                raise CmsError("Страница не найдена.", 404, "not_found") from None
            if target.is_dir():
                target = (target / "index.html").resolve()
            try:
                target.relative_to(self.server.site)
            except ValueError:
                raise CmsError("Страница не найдена.", 404, "not_found") from None
            if not target.is_file():
                raise CmsError("Страница не найдена.", 404, "not_found")
            mime = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            if mime.startswith("text/") or mime in ("application/javascript", "application/json"):
                mime += "; charset=utf-8"
        try:
            body = target.read_bytes()
        except OSError:
            raise CmsError("Файл не найден.", 404, "not_found") from None
        self.respond(200, body, mime)

    def do_GET(self):
        try:
            self.dispatch()
        except CmsError as error:
            self.respond(error.status, {"error": str(error), "code": error.code})
        except (ConnectionError, TimeoutError):
            self.close_connection = True
        except (OSError, sqlite3.Error):
            self.respond(500, {"error": "Ошибка локального хранилища.", "code": "storage_error"})

    do_HEAD = do_GET
    do_POST = do_GET
    do_PUT = do_GET
    do_DELETE = do_GET
    do_PATCH = do_GET


def main():
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("serve", "set-admin"), default="serve")
    parser.add_argument("--port", type=int, default=8345)
    parser.add_argument("--username", default="admin")
    parser.add_argument("--data-dir", type=Path, help="Отдельное хранилище для локальной проверки/демо; по умолчанию data/cms")
    parser.add_argument("--public-origin", help="Точный HTTPS-адрес trycloudflare.com для уже настроенного отдельного демо")
    args = parser.parse_args()
    if args.public_origin and args.data_dir is None:
        parser.error("--public-origin требует явного отдельного --data-dir.")
    if args.public_origin and args.command != "serve":
        parser.error("--public-origin используется только при запуске сервера.")
    args.data_dir = args.data_dir or WORKING_DATA
    if args.public_origin:
        try:
            validate_demo_origin(args.public_origin)
            validate_demo_directory(args.data_dir)
        except ValueError as error:
            parser.error(str(error))
    if args.data_dir.resolve().is_relative_to((ROOT / "site").resolve()):
        parser.error("Хранилище должно находиться вне публичного site/.")
    if args.command == "set-admin":
        password = getpass.getpass("Новый пароль (от 12 символов): ")
        if password != getpass.getpass("Повторите пароль: "):
            parser.error("Пароли не совпадают.")
        try:
            Store(args.data_dir).set_admin(args.username, password)
        except CmsError as error:
            parser.error(str(error))
        print("Учётная запись сохранена. Прежние сессии этого пользователя завершены.")
        return
    if not 0 < args.port < 65536:
        parser.error("Порт должен быть от 1 до 65535.")
    try:
        server = LocalCmsServer(("127.0.0.1", args.port), ROOT / "site", args.data_dir, public_origin=args.public_origin)
    except ValueError as error:
        parser.error(str(error))
    LOGGER.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(message)s")
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(server.store.directory / "server.log", encoding="utf-8")):
        handler.setFormatter(formatter)
        LOGGER.addHandler(handler)
    LOGGER.info("Dengi Market: http://127.0.0.1:%s/", server.server_port)
    LOGGER.info("Редактор: http://127.0.0.1:%s/admin/", server.server_port)
    LOGGER.info("Локальный просмотр; остановка Ctrl+C. Первый вход на странице редактора; восстановление через set-admin.")
    if server.public_origin:
        LOGGER.info("Временное демо: %s/; отдельные данные: %s", server.public_origin, server.store.directory)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
