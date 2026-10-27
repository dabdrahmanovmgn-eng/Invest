"""Хранилище локального редактора: SQLite, сессии и проверенные изображения."""
import base64
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import struct
import time
import unicodedata
import uuid
import zlib
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
IDLE_SECONDS = 30 * 60
MAX_IMAGE_BYTES = 8 * 1024 * 1024
UPLOAD_RE = re.compile(r"/uploads/[0-9a-f]{32}\.(?:png|jpg|webp)\Z")


class CmsError(Exception):
    def __init__(self, message, status=400, code="invalid_request"):
        super().__init__(message)
        self.status = status
        self.code = code


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 1024:
        raise CmsError("Пароль должен содержать от 12 до 1024 символов.", 400, "weak_password")
    try:
        password_bytes = password.encode("utf-8")
    except UnicodeError:
        raise CmsError("Пароль содержит недопустимые символы.", 400, "weak_password") from None
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes, salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def password_matches(password, encoded):
    try:
        algorithm, rounds, salt, digest = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or len(password) > 1024:
            return False
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return hmac.compare_digest(candidate.hex(), digest)
    except (ValueError, TypeError, AttributeError, UnicodeError):
        return False


def image_metadata(data):
    """Допускаются только контейнеры PNG/JPEG/WebP с ограниченными размерами."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise CmsError("Изображение должно быть не больше 8 МБ.", 413, "image_too_large")
    width = height = 0
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        offset, seen_data, seen_end, compressed = 8, False, False, []
        bit_depth = color = interlace = None
        while offset + 12 <= len(data):
            length = struct.unpack(">I", data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            end = offset + 12 + length
            if end > len(data) or length > MAX_IMAGE_BYTES:
                break
            chunk = data[offset + 8:end - 4]
            checksum = struct.unpack(">I", data[end - 4:end])[0]
            if zlib.crc32(kind + chunk) & 0xffffffff != checksum:
                raise CmsError("Повреждённый PNG.")
            if offset == 8:
                if kind != b"IHDR" or length != 13:
                    raise CmsError("Повреждённый заголовок PNG.")
                width, height = struct.unpack(">II", chunk[:8])
                bit_depth, color, compression, filtering, interlace = chunk[8:13]
                allowed_depths = {0: (1, 2, 4, 8, 16), 2: (8, 16), 3: (1, 2, 4, 8), 4: (8, 16), 6: (8, 16)}
                if bit_depth not in allowed_depths.get(color, ()) or compression or filtering or interlace not in (0, 1):
                    raise CmsError("Неподдерживаемые параметры PNG.")
                if not 0 < width <= 12000 or not 0 < height <= 12000 or width * height > 40_000_000:
                    raise CmsError("Слишком большое разрешение PNG.")
            if kind == b"IDAT":
                seen_data = True
                compressed.append(chunk)
            if kind == b"IEND":
                seen_end = length == 0 and end == len(data)
                break
            offset = end
        if not seen_data or not seen_end:
            raise CmsError("Повреждённый PNG.")
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color]
        passes = ((0, 0, 1, 1),) if interlace == 0 else ((0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2))
        expected = 0
        for start_x, start_y, step_x, step_y in passes:
            pass_width = max(0, (width - start_x + step_x - 1) // step_x)
            pass_height = max(0, (height - start_y + step_y - 1) // step_y)
            if pass_width and pass_height:
                expected += (((pass_width * channels * bit_depth + 7) // 8) + 1) * pass_height
        decoder, decoded_size = zlib.decompressobj(), 0
        try:
            for packed in compressed:
                remaining = packed
                while remaining:
                    decoded_size += len(decoder.decompress(remaining, 65536))
                    if decoded_size > expected:
                        raise CmsError("Некорректный размер данных PNG.")
                    remaining = decoder.unconsumed_tail
            if decoded_size != expected or not decoder.eof or decoder.unused_data:
                raise CmsError("Повреждённые данные PNG.")
        except zlib.error:
            raise CmsError("Повреждённые данные PNG.") from None
        mime, extension = "image/png", "png"
    elif data.startswith(b"\xff\xd8") and data.endswith(b"\xff\xd9"):
        offset, seen_scan = 2, False
        sof = {0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf}
        while offset + 4 <= len(data):
            if data[offset] != 0xff:
                break
            while offset < len(data) and data[offset] == 0xff:
                offset += 1
            if offset >= len(data):
                break
            marker = data[offset]
            offset += 1
            if marker == 0xda:
                if offset + 2 <= len(data):
                    scan_length = struct.unpack(">H", data[offset:offset + 2])[0]
                    seen_scan = scan_length >= 6 and offset + scan_length < len(data) - 2
                break
            if marker == 0xd9:
                break
            if marker in (0x01, 0xd8) or 0xd0 <= marker <= 0xd7:
                continue
            length = struct.unpack(">H", data[offset:offset + 2])[0]
            if length < 2 or offset + length > len(data):
                break
            if marker in sof and length >= 8:
                height, width = struct.unpack(">HH", data[offset + 3:offset + 7])
            offset += length
        if not width or not seen_scan:
            raise CmsError("Повреждённый JPEG.")
        mime, extension = "image/jpeg", "jpg"
    elif len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if struct.unpack("<I", data[4:8])[0] + 8 != len(data):
            raise CmsError("Повреждённый WebP.")
        kind = data[12:16]
        chunk_length = struct.unpack("<I", data[16:20])[0]
        if chunk_length + 20 > len(data):
            raise CmsError("Повреждённый WebP.")
        if kind == b"VP8X" and chunk_length == 10:
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
        elif kind == b"VP8 " and data[23:26] == b"\x9d\x01\x2a":
            width, height = struct.unpack("<HH", data[26:30])
            width, height = width & 0x3fff, height & 0x3fff
        elif kind == b"VP8L" and data[20] == 0x2f:
            bits = int.from_bytes(data[21:25], "little")
            width, height = (bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1
        if not width:
            raise CmsError("Неподдерживаемый WebP.")
        offset, has_pixels = 12, False
        while offset + 8 <= len(data):
            chunk_kind = data[offset:offset + 4]
            size = struct.unpack("<I", data[offset + 4:offset + 8])[0]
            end = offset + 8 + size
            if end > len(data):
                raise CmsError("Повреждённый WebP.")
            if chunk_kind == b"VP8 " and size >= 10 and data[offset + 11:offset + 14] == b"\x9d\x01\x2a":
                has_pixels = True
            if chunk_kind == b"VP8L" and size >= 5 and data[offset + 8] == 0x2f:
                has_pixels = True
            offset = end + (size & 1)
        if offset != len(data) or not has_pixels:
            raise CmsError("Нужен статичный WebP с данными изображения.")
        mime, extension = "image/webp", "webp"
    else:
        raise CmsError("Допустимы только PNG, JPEG и WebP.", 415, "unsupported_image")
    if not 0 < width <= 12000 or not 0 < height <= 12000 or width * height > 40_000_000:
        raise CmsError("Слишком большое разрешение: максимум 40 Мп и 12000 px по стороне.")
    return mime, extension, width, height


class Store:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.uploads = self.directory / "uploads"
        self.uploads.mkdir(exist_ok=True)
        self.database = self.directory / "cms.sqlite3"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS admins (
                    username TEXT PRIMARY KEY, password TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, username TEXT NOT NULL,
                    csrf TEXT NOT NULL, expires REAL NOT NULL, touched REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY, slug TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL, excerpt TEXT NOT NULL, body TEXT NOT NULL,
                    language TEXT NOT NULL, cover TEXT NOT NULL,
                    images TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL, published_at TEXT
                );
                CREATE TABLE IF NOT EXISTS uploads (
                    url TEXT PRIMARY KEY, mime TEXT NOT NULL,
                    width INTEGER NOT NULL, height INTEGER NOT NULL, created_at TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def set_admin(self, username, password):
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
            raise CmsError("Логин: 3–64 латинских символа, цифры, . _ @ -.")
        encoded = password_hash(password)
        with self.connect() as db:
            db.execute("INSERT INTO admins VALUES (?,?) ON CONFLICT(username) DO UPDATE SET password=excluded.password", (username, encoded))
            db.execute("DELETE FROM sessions WHERE username=?", (username,))

    def admin_configured(self):
        with self.connect() as db:
            return bool(db.execute("SELECT 1 FROM admins LIMIT 1").fetchone())

    def create_first_admin(self, username, password):
        """Создать ровно первый аккаунт и его сессию одной транзакцией."""
        if not isinstance(username, str) or not re.fullmatch(r"[A-Za-z0-9_.@-]{3,64}", username):
            raise CmsError("Логин: 3–64 латинских символа, цифры, . _ @ -.", 400, "invalid_username")
        encoded = password_hash(password)
        token, csrf, stamp = secrets.token_urlsafe(32), secrets.token_urlsafe(32), time.time()
        with self.connect() as db:
            # Проверка и создание атомарны, включая запросы из разных вкладок.
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM admins LIMIT 1").fetchone():
                raise CmsError("Первый вход уже настроен. Войдите с существующим аккаунтом.", 409, "setup_complete")
            db.execute("INSERT INTO admins VALUES (?,?)", (username, encoded))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, csrf, stamp + SESSION_SECONDS, stamp))
        return token, csrf

    def authenticate(self, username, password):
        with self.connect() as db:
            row = db.execute("SELECT password FROM admins WHERE username=?", (username,)).fetchone()
        # Неизвестный логин выполняет такую же дорогую проверку.
        encoded = row[0] if row else f"pbkdf2_sha256${PASSWORD_ITERATIONS}${'00' * 16}${'00' * 32}"
        valid = password_matches(password, encoded)
        if not row or not valid:
            return None
        token, csrf, stamp = secrets.token_urlsafe(32), secrets.token_urlsafe(32), time.time()
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE expires<? OR touched<?", (stamp, stamp - IDLE_SECONDS))
            db.execute("INSERT INTO sessions VALUES (?,?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), username, csrf, stamp + SESSION_SECONDS, stamp))
        return token, csrf

    def session(self, token):
        if not token or len(token) > 128:
            return None
        digest, stamp = hashlib.sha256(token.encode()).hexdigest(), time.time()
        with self.connect() as db:
            row = db.execute("SELECT * FROM sessions WHERE token_hash=? AND expires>? AND touched>?", (digest, stamp, stamp - IDLE_SECONDS)).fetchone()
            if row:
                db.execute("UPDATE sessions SET touched=? WHERE token_hash=?", (stamp, digest))
        return dict(row) if row else None

    def logout(self, token):
        with self.connect() as db:
            db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))

    @staticmethod
    def article(row, public=False):
        result = dict(row)
        result["images"] = json.loads(result["images"])
        if public:
            result.pop("status", None)
        return result

    def list_articles(self, language=None, public=False):
        query, arguments = "SELECT * FROM articles WHERE 1=1", []
        if public:
            query += " AND status='published'"
        if language:
            query += " AND language=?"
            arguments.append(language)
        query += " ORDER BY COALESCE(published_at,created_at) DESC, id DESC LIMIT 500"
        with self.connect() as db:
            return [self.article(row, public) for row in db.execute(query, arguments)]

    def get_article(self, value, public=False):
        field = "slug" if public else "id"
        query = f"SELECT * FROM articles WHERE {field}=?" + (" AND status='published'" if public else "")
        with self.connect() as db:
            row = db.execute(query, (value,)).fetchone()
        if not row:
            raise CmsError("Статья не найдена.", 404, "not_found")
        return self.article(row, public)

    def save_article(self, payload, article_id=None):
        if not isinstance(payload, dict):
            raise CmsError("Нужен объект JSON.")
        previous = self.get_article(article_id) if article_id else None
        values = dict(previous or {})
        values.update(payload)
        limits = {"title": 180, "excerpt": 600, "body": 100_000}
        for key, limit in limits.items():
            value = values.get(key, "")
            if not isinstance(value, str) or len(value) > limit or "\x00" in value:
                raise CmsError(f"Некорректное поле {key}: максимум {limit} символов.")
            try:
                value.encode("utf-8")
            except UnicodeError:
                raise CmsError(f"Некорректная кодировка поля {key}.") from None
            values[key] = value.strip()
        if not values["title"]:
            raise CmsError("Укажите заголовок.")
        language, status = values.get("language", "en"), values.get("status", "draft")
        if language not in ("en", "ru") or status not in ("draft", "published", "archived"):
            raise CmsError("Недопустимый язык или статус.")
        if status == "published" and not values["body"]:
            raise CmsError("Для публикации нужен текст статьи.")
        slug = values.get("slug", "")
        if not slug:
            ascii_title = unicodedata.normalize("NFKD", values["title"]).encode("ascii", "ignore").decode()
            base = re.sub(r"[^a-z0-9]+", "-", ascii_title.lower()).strip("-")[:80].rstrip("-")
            slug = (base or "post") + "-" + uuid.uuid4().hex[:8]
        if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug) or len(slug) > 120:
            raise CmsError("Адрес статьи: строчные латинские буквы, цифры и дефисы, до 120 символов.")
        cover, images = values.get("cover", ""), values.get("images", [])
        if not isinstance(cover, str) or not isinstance(images, list) or len(images) > 12:
            raise CmsError("Некорректный список изображений (максимум 12).")
        urls = ([cover] if cover else []) + images
        with self.connect() as db:
            for url in urls:
                if not isinstance(url, str) or not UPLOAD_RE.fullmatch(url) or not db.execute("SELECT 1 FROM uploads WHERE url=?", (url,)).fetchone():
                    raise CmsError("Выберите изображение, загруженное в редактор.")
            stamp = now_iso()
            article_id = article_id or uuid.uuid4().hex
            created = previous["created_at"] if previous else stamp
            published = previous.get("published_at") if previous else None
            if status == "published" and not published:
                published = stamp
            try:
                db.execute("""INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET slug=excluded.slug,title=excluded.title,
                    excerpt=excluded.excerpt,body=excluded.body,language=excluded.language,
                    cover=excluded.cover,images=excluded.images,status=excluded.status,
                    updated_at=excluded.updated_at,published_at=excluded.published_at""",
                    (article_id, slug, values["title"], values["excerpt"], values["body"], language,
                     cover, json.dumps(list(dict.fromkeys(images))), status, created, stamp, published))
            except sqlite3.IntegrityError:
                raise CmsError("Этот адрес статьи уже занят.", 409, "slug_exists") from None
        return self.get_article(article_id)

    def upload(self, payload):
        if not isinstance(payload, dict) or not isinstance(payload.get("data"), str):
            raise CmsError("Нужны filename, mime и data (base64).")
        filename = payload.get("filename", "")
        if not isinstance(filename, str) or not 0 < len(filename) <= 255 or any(char in filename for char in "/\\\x00"):
            raise CmsError("Некорректное имя файла.")
        try:
            data = base64.b64decode(payload["data"], validate=True)
        except (ValueError, TypeError):
            raise CmsError("Некорректный base64.") from None
        mime, extension, width, height = image_metadata(data)
        if payload.get("mime") != mime:
            raise CmsError("Тип файла не совпадает с содержимым.", 415, "mime_mismatch")
        name = uuid.uuid4().hex + "." + extension
        target = self.uploads / name
        url = "/uploads/" + name
        try:
            with target.open("xb") as handle:
                handle.write(data)
            with self.connect() as db:
                db.execute("INSERT INTO uploads VALUES (?,?,?,?,?)", (url, mime, width, height, now_iso()))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {"url": url, "mime": mime, "width": width, "height": height}

    def image(self, url, authenticated=False):
        if not UPLOAD_RE.fullmatch(url):
            raise CmsError("Изображение не найдено.", 404, "not_found")
        with self.connect() as db:
            row = db.execute("SELECT * FROM uploads WHERE url=?", (url,)).fetchone()
            visible = authenticated
            if row and not visible:
                for article in db.execute("SELECT cover,images FROM articles WHERE status='published'"):
                    if article["cover"] == url or url in json.loads(article["images"]):
                        visible = True
                        break
        if not row or not visible:
            raise CmsError("Изображение не найдено.", 404, "not_found")
        return self.uploads / url.removeprefix("/uploads/"), row["mime"]
