"""Интеграционные проверки CMS через настоящий локальный HTTP-сервер."""
import base64
import http.client
import json
import secrets
import struct
import tempfile
import threading
import time
import unittest
import zlib
from pathlib import Path

from cms_store import IDLE_SECONDS, Store, image_metadata
from serve_cms import LocalCmsServer


def png(width=1, height=1, compressed=None):
    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x80\x00") if compressed is None else compressed) + chunk(b"IEND", b""))


class CmsIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dengi-cms-test-")
        root = Path(self.temp.name)
        self.site, self.data = root / "site", root / "data"
        self.site.mkdir()
        (self.site / "index.html").write_text("<!doctype html><title>Local test</title>", encoding="utf-8")
        self.server = LocalCmsServer(("127.0.0.1", 0), self.site, self.data)
        self.password = secrets.token_urlsafe(24)
        if getattr(self, "configure_admin", True):
            self.server.store.set_admin("testadmin", self.password)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.cookie, self.csrf = "", ""

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request(self, method, path, payload=None, *, auth=True, csrf=True, origin=True, headers=None):
        prepared = {}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        if body is not None:
            prepared["Content-Type"] = "application/json"
        if auth and self.cookie:
            prepared["Cookie"] = self.cookie
        if csrf and self.csrf:
            prepared["X-CSRF-Token"] = self.csrf
        if origin:
            prepared["Origin"] = self.origin
        prepared.update(headers or {})
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request(method, path, body=body, headers=prepared)
        response = connection.getresponse()
        raw, returned_headers, status = response.read(), dict(response.getheaders()), response.status
        connection.close()
        if returned_headers.get("Content-Type", "").startswith("application/json"):
            raw = json.loads(raw)
        return status, raw, returned_headers

    def login(self):
        status, body, headers = self.request("POST", "/api/login", {"username": "testadmin", "password": self.password})
        self.assertEqual(status, 200, body)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = body["csrf"]
        return headers

    def create(self, **fields):
        payload = {"title": "Investor news", "excerpt": "Company update", "body": "First paragraph.\n\nSecond paragraph.", "language": "en", "status": "draft"}
        payload.update(fields)
        status, body, _ = self.request("POST", "/api/admin/articles", payload)
        self.assertEqual(status, 201, body)
        return body["article"]

    def upload(self):
        return self.request("POST", "/api/uploads", {"filename": "photo.png", "mime": "image/png", "data": base64.b64encode(png()).decode()})

    def test_auth_cookie_session_and_logout(self):
        self.assertEqual(self.request("GET", "/api/session")[1]["authenticated"], False)
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 401)
        headers = self.login()
        for attribute in ("HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=28800"):
            self.assertIn(attribute, headers["Set-Cookie"])
        session = self.request("GET", "/api/session")[1]
        self.assertEqual(session["csrf"], self.csrf)
        self.assertTrue(session["authenticated"])
        self.assertEqual(self.request("POST", "/api/logout", {})[0], 200)
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 401)

    def test_csrf_and_origin_reject_untrusted_mutations(self):
        self.login()
        payload = {"title": "Should not save", "body": "No"}
        self.assertEqual(self.request("POST", "/api/admin/articles", payload, csrf=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/admin/articles", payload, origin=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/admin/articles", payload, headers={"Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/admin/articles", payload, headers={"X-CSRF-Token": "wrong"})[0], 403)
        self.assertEqual(self.request("GET", "/api/admin/articles")[1]["articles"], [])

    def test_login_requires_origin_and_correct_password(self):
        payload = {"username": "testadmin", "password": self.password}
        self.assertEqual(self.request("POST", "/api/login", payload, origin=False)[0], 403)
        payload["password"] = secrets.token_urlsafe(24)
        self.assertEqual(self.request("POST", "/api/login", payload)[0], 401)
        payload["username"] = "unknown"
        self.assertEqual(self.request("POST", "/api/login", payload)[0], 401)

    def test_rate_limit(self):
        for _ in range(10):
            # Некорректный формат также расходует лимит, не тратя время PBKDF2 в тесте.
            self.assertEqual(self.request("POST", "/api/login", {"username": None, "password": None})[0], 401)
        status, body, _ = self.request("POST", "/api/login", {"username": "testadmin", "password": self.password})
        self.assertEqual(status, 429)
        self.assertEqual(body["code"], "rate_limited")

    def test_draft_publish_edit_archive_and_restore(self):
        self.login()
        article = self.create(title="Новости компании", language="ru")
        slug, identifier = article["slug"], article["id"]
        self.assertTrue(slug.startswith("post-"))
        self.assertEqual(self.request("GET", "/api/articles", auth=False)[1]["articles"], [])
        self.assertEqual(self.request("GET", "/api/articles/" + slug, auth=False)[0], 404)
        status, result, _ = self.request("PUT", "/api/admin/articles/" + identifier, {"status": "published"})
        self.assertEqual(status, 200, result)
        published = self.request("GET", "/api/articles/" + slug, auth=False)[1]["article"]
        self.assertEqual(published["title"], article["title"])
        self.assertEqual(published["body"], article["body"])
        self.assertIsNotNone(published["published_at"])
        self.assertNotIn("status", published)
        self.assertEqual(len(self.request("GET", "/api/articles?language=ru", auth=False)[1]["articles"]), 1)
        self.assertEqual(self.request("GET", "/api/articles?language=en", auth=False)[1]["articles"], [])
        self.assertEqual(self.request("PUT", "/api/admin/articles/" + identifier, {"status": "archived"})[0], 200)
        self.assertEqual(self.request("GET", "/api/articles/" + slug, auth=False)[0], 404)
        self.assertEqual(self.request("PUT", "/api/admin/articles/" + identifier, {"status": "published"})[0], 200)
        self.assertEqual(Store(self.data).get_article(slug, True)["body"], article["body"])

    def test_unique_slug_validation_and_plain_text(self):
        self.login()
        article = self.create(slug="news-2026", body="<script>alert('test')</script>")
        self.assertEqual(article["body"], "<script>alert('test')</script>")
        status, _, _ = self.request("POST", "/api/admin/articles", {"title": "Second", "slug": "news-2026"})
        self.assertEqual(status, 409)
        for patch in ({"language": "fr"}, {"status": "unknown"}, {"slug": "../../outside"}, {"title": ""}, {"body": "x" * 100001}, {"cover": "https://example.com/a.png"}, {"images": ["/uploads/fake.png"]}):
            self.assertEqual(self.request("PUT", "/api/admin/articles/" + article["id"], patch)[0], 400, patch)
        self.assertEqual(Store(self.data).get_article(article["id"])["slug"], "news-2026")
        # JSON escape с одиночным суррогатом не должен обрывать HTTP-соединение.
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.request("PUT", "/api/admin/articles/" + article["id"], body=b'{"title":"\\ud800"}', headers={"Content-Type": "application/json", "Origin": self.origin, "Cookie": self.cookie, "X-CSRF-Token": self.csrf})
        response = connection.getresponse()
        self.assertEqual(response.status, 400)
        response.read()
        connection.close()

    def test_upload_is_authenticated_and_draft_image_private(self):
        self.assertEqual(self.upload()[0], 401)
        self.login()
        status, image, _ = self.upload()
        self.assertEqual(status, 201, image)
        self.assertEqual((image["width"], image["height"]), (1, 1))
        url = image["url"]
        self.assertRegex(url, r"^/uploads/[0-9a-f]{32}\.png$")
        self.assertEqual(self.request("GET", url, auth=False)[0], 404)
        self.assertEqual(self.request("GET", url)[1], png())
        article = self.create(cover=url, images=[url])
        self.assertEqual(self.request("GET", url, auth=False)[0], 404)
        self.request("PUT", "/api/admin/articles/" + article["id"], {"status": "published"})
        status, data, headers = self.request("GET", url, auth=False)
        self.assertEqual((status, data), (200, png()))
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.request("PUT", "/api/admin/articles/" + article["id"], {"status": "draft"})
        self.assertEqual(self.request("GET", url, auth=False)[0], 404)

    def test_rejects_active_files_mime_lies_and_bad_images(self):
        self.login()
        empty_webp = b"RIFF" + struct.pack("<I", 22) + b"WEBPVP8X" + struct.pack("<I", 10) + b"\x00" * 10
        empty_jpeg = b"\xff\xd8\xff\xc0" + struct.pack(">H", 8) + b"\x08" + struct.pack(">HH", 1, 1) + b"\x03\xff\xd9"
        for raw, mime, filename in ((b"<svg onload='alert(1)'/>", "image/svg+xml", "bad.svg"), (b"<html>Hello</html>", "image/png", "bad.png"), (png(), "image/jpeg", "lie.jpg"), (png()[:-1], "image/png", "broken.png"), (png(compressed=b"not-deflate"), "image/png", "invalid-pixels.png"), (empty_webp, "image/webp", "empty.webp"), (empty_jpeg, "image/jpeg", "empty.jpg"), (png(12001, 1), "image/png", "huge.png"), (png(), "image/png", "../escape.png")):
            status, _, _ = self.request("POST", "/api/uploads", {"filename": filename, "mime": mime, "data": base64.b64encode(raw).decode()})
            self.assertIn(status, (400, 413, 415))
        self.assertEqual(list(self.server.store.uploads.iterdir()), [])

    def test_host_traversal_private_files_and_no_directory_listing(self):
        for path in ("/../data/cms.sqlite3", "/%2e%2e/data/cms.sqlite3", "/data/cms/cms.sqlite3", "/.git/config", "/uploads/../../data/cms.sqlite3", "/%5c..%5ccms.sqlite3"):
            self.assertEqual(self.request("GET", path)[0], 404, path)
        self.assertEqual(self.request("GET", "/", headers={"Host": "attacker.invalid"})[0], 403)
        (self.site / "empty").mkdir()
        self.assertEqual(self.request("GET", "/empty/")[0], 404)
        status, _, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")

    def test_expiry_and_password_reset_invalidate_sessions(self):
        self.login()
        with self.server.store.connect() as db:
            db.execute("UPDATE sessions SET touched=?", (time.time() - IDLE_SECONDS - 1,))
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 401)
        self.login()
        self.server.store.set_admin("testadmin", secrets.token_urlsafe(24))
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 401)
        with self.server.store.connect() as db:
            saved = db.execute("SELECT password FROM admins").fetchone()[0]
        self.assertTrue(saved.startswith("pbkdf2_sha256$600000$"))
        self.assertNotIn(self.password, saved)


class CmsFirstSetupTests(unittest.TestCase):
    configure_admin = False
    setUp = CmsIntegrationTests.setUp
    tearDown = CmsIntegrationTests.tearDown
    request = CmsIntegrationTests.request
    login = CmsIntegrationTests.login
    create = CmsIntegrationTests.create

    def setup_session(self):
        status, body, headers = self.request("GET", "/api/session")
        self.assertEqual(status, 200, body)
        self.assertFalse(body["adminConfigured"])
        self.assertFalse(body["authenticated"])
        self.assertRegex(body["setupCsrf"], r"^[0-9a-f]{64}$")
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        for attribute in ("HttpOnly", "SameSite=Strict", "Path=/api/", "Max-Age=900"):
            self.assertIn(attribute, headers["Set-Cookie"])
        return body["setupCsrf"]

    def test_first_setup_signs_in_and_closes_bootstrap(self):
        nonce = self.setup_session()
        payload = {"username": "testadmin", "password": self.password}
        status, body, headers = self.request("POST", "/api/setup", payload, headers={"X-Setup-Token": nonce})
        self.assertEqual(status, 201, body)
        self.assertTrue(body["authenticated"])
        self.assertTrue(body["adminConfigured"])
        self.assertEqual(body["username"], "testadmin")
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = body["csrf"]
        session = self.request("GET", "/api/session")[1]
        self.assertTrue(session["authenticated"])
        self.assertNotIn("setupCsrf", session)
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 200)
        article = self.create()
        self.assertEqual(article["status"], "draft")
        # Старый nonce не может создать второй аккаунт или заменить пароль.
        second, result, _ = self.request("POST", "/api/setup", {"username": "attacker", "password": secrets.token_urlsafe(24)}, headers={"X-Setup-Token": nonce})
        self.assertEqual((second, result["code"]), (409, "setup_complete"))
        with self.server.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM admins").fetchone()[0], 1)
            saved = db.execute("SELECT password FROM admins WHERE username='testadmin'").fetchone()[0]
        self.assertTrue(saved.startswith("pbkdf2_sha256$600000$"))
        self.assertNotIn(self.password, saved)
        self.login()

    def test_first_setup_rejects_cross_origin_missing_nonce_and_cookie(self):
        nonce = self.setup_session()
        payload = {"username": "testadmin", "password": self.password}
        self.assertEqual(self.request("POST", "/api/setup", payload, origin=False, headers={"X-Setup-Token": nonce})[0], 403)
        self.assertEqual(self.request("POST", "/api/setup", payload, headers={"X-Setup-Token": nonce, "Origin": "https://attacker.invalid"})[0], 403)
        self.assertEqual(self.request("POST", "/api/setup", payload)[0], 403)
        self.assertEqual(self.request("POST", "/api/setup", payload, headers={"X-Setup-Token": "0" * 64})[0], 403)
        self.assertEqual(self.request("POST", "/api/setup", payload, auth=False, headers={"X-Setup-Token": nonce})[0], 403)
        self.assertEqual(self.request("POST", "/api/setup", payload, auth=False, headers={"X-Setup-Token": nonce, "Cookie": "[invalid]=x"})[0], 403)
        self.assertFalse(self.server.store.admin_configured())

    def test_first_setup_validates_credentials_without_creating_account(self):
        nonce = self.setup_session()
        for payload, expected in (({"username": "a", "password": self.password}, "invalid_username"),
                                  ({"username": "testadmin", "password": "short"}, "weak_password"),
                                  ({"username": "testadmin", "password": None}, "weak_password"),
                                  ({"username": "testadmin", "password": "x" * 1025}, "weak_password"),
                                  ({"username": "testadmin", "password": "x" * 12 + "\ud800"}, "weak_password")):
            if isinstance(payload.get("password"), str) and any(0xd800 <= ord(char) <= 0xdfff for char in payload["password"]):
                # Экранированный JSON передаёт некорректный Unicode без ошибки клиента.
                connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
                connection.request("POST", "/api/setup", body=json.dumps(payload).encode("ascii"), headers={"Content-Type": "application/json", "Origin": self.origin, "Cookie": self.cookie, "X-Setup-Token": nonce})
                response = connection.getresponse()
                status, body = response.status, json.loads(response.read())
                connection.close()
            else:
                status, body, _ = self.request("POST", "/api/setup", payload, headers={"X-Setup-Token": nonce})
            self.assertEqual((status, body["code"]), (400, expected), payload)
        self.assertFalse(self.server.store.admin_configured())

    def test_setup_nonce_bound_to_browser_and_server_run(self):
        nonce_a = self.setup_session()
        cookie_a = self.cookie
        nonce_b = self.setup_session()
        # Повторный GET с тем же cookie сохраняет привязку текущей формы.
        self.assertEqual(nonce_a, nonce_b)
        _, body_b, headers_b = self.request("GET", "/api/session", auth=False)
        self.assertNotEqual(nonce_a, body_b["setupCsrf"])
        payload = {"username": "testadmin", "password": self.password}
        self.cookie = headers_b["Set-Cookie"].split(";", 1)[0]
        self.assertEqual(self.request("POST", "/api/setup", payload, headers={"X-Setup-Token": nonce_a})[0], 403)
        self.cookie = cookie_a
        expired = "dm_cms_setup=" + "a" * 64 + "." + str(int(time.time()) - 901)
        self.assertEqual(self.request("POST", "/api/setup", payload, auth=False, headers={"X-Setup-Token": nonce_a, "Cookie": expired})[0], 403)
        self.server.setup_secret = secrets.token_bytes(32)
        self.assertEqual(self.request("POST", "/api/setup", payload, headers={"X-Setup-Token": nonce_a})[0], 403)
        # Секрет и nonce не хранятся на диске и не переживают перезапуск.
        self.assertFalse(self.server.store.admin_configured())

    def test_two_setup_requests_create_only_one_account(self):
        nonce_a = self.setup_session()
        cookie_a = self.cookie
        _, body_b, headers_b = self.request("GET", "/api/session", auth=False)
        barrier = threading.Barrier(2)
        results = []

        def attempt(username, nonce, cookie):
            barrier.wait(timeout=5)
            result = self.request("POST", "/api/setup", {"username": username, "password": self.password}, auth=False, headers={"X-Setup-Token": nonce, "Cookie": cookie})
            results.append(result[0])

        workers = [threading.Thread(target=attempt, args=("editor-a", nonce_a, cookie_a)),
                   threading.Thread(target=attempt, args=("editor-b", body_b["setupCsrf"], headers_b["Set-Cookie"].split(";", 1)[0]))]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=10)
        self.assertEqual(sorted(results), [201, 409])
        with self.server.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM admins").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
