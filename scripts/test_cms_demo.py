"""Демо-CMS: запросы туннеля моделируются только локальным HTTP-клиентом."""
import base64
import http.client
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import test_cms
from serve_cms import LocalCmsServer, ROOT, WORKING_DATA, validate_demo_directory


class CmsDemoTests(unittest.TestCase):
    tearDown = test_cms.CmsIntegrationTests.tearDown
    public_origin = "https://demo-investor-check.trycloudflare.com"
    public_host = "demo-investor-check.trycloudflare.com"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dengi-cms-demo-test-")
        root = Path(self.temp.name)
        self.site, self.data = root / "site", root / "data"
        self.site.mkdir()
        (self.site / "index.html").write_text("<!doctype html><title>Demo test</title>", encoding="utf-8")
        self.server = LocalCmsServer(("127.0.0.1", 0), self.site, self.data, cookie_prefix="dm_demo")
        self.password = secrets.token_urlsafe(24)
        self.server.store.set_admin("testadmin", self.password)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"
        self.cookie, self.csrf = "", ""

    def local_request(self, method, path, payload=None, **options):
        return test_cms.CmsIntegrationTests.request(self, method, path, payload, **options)

    def request(self, method, path, payload=None, *, headers=None, **options):
        external_headers = {"Host": self.public_host, "Origin": self.public_origin}
        external_headers.update(headers or {})
        return self.local_request(method, path, payload, headers=external_headers, **options)

    def activate(self):
        self.server.set_public_origin(self.public_origin)

    def login(self):
        status, body, headers = self.request("POST", "/api/login", {"username": "testadmin", "password": self.password})
        self.assertEqual(status, 200, body)
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.csrf = body["csrf"]
        return headers

    def test_activation_is_explicit_exact_and_keeps_loopback(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertIsNone(self.server.public_origin)
        self.assertEqual(self.request("GET", "/")[0], 403)
        rejected = (
            "http://demo-investor-check.trycloudflare.com",
            self.public_origin + "/", self.public_origin + ":443",
            self.public_origin + "/path", self.public_origin + "?x=1",
            self.public_origin + "#fragment", "https://trycloudflare.com",
            "https://demo.trycloudflare.com.attacker.invalid",
            "https://name@demo-investor-check.trycloudflare.com",
            "https://nested.demo.trycloudflare.com", None,
            "https://-demo.trycloudflare.com", self.public_origin + "\n",
        )
        for origin in rejected:
            with self.assertRaises(ValueError, msg=str(origin)):
                self.server.set_public_origin(origin)
            self.assertIsNone(self.server.public_origin)
        self.activate()
        self.assertEqual(self.server.public_origin, self.public_origin)
        status, _, headers = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.local_request("GET", "/")[0], 200)
        for host in ("attacker.invalid", "other.trycloudflare.com", self.public_host + ":443", self.public_host.upper()):
            status, _, headers = self.request("GET", "/", headers={"Host": host})
            self.assertEqual(status, 403, host)
            self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")

    def test_requires_local_account_and_separate_store_before_activation(self):
        with self.server.store.connect() as db:
            db.execute("DELETE FROM admins")
        with self.assertRaises(ValueError):
            self.activate()
        self.assertIsNone(self.server.public_origin)
        self.assertEqual(self.request("GET", "/api/session")[0], 403)
        # Конструктор не открывает рабочую базу даже ради проверки администратора.
        with mock.patch("serve_cms.Store", side_effect=AssertionError("Working store must not open")) as store:
            with self.assertRaises(ValueError):
                LocalCmsServer(("127.0.0.1", 0), self.site, WORKING_DATA, public_origin=self.public_origin)
            store.assert_not_called()
        with self.assertRaises(ValueError):
            validate_demo_directory(WORKING_DATA / "nested-demo")
        actual_directory = self.server.store.directory
        try:
            self.server.store.directory = WORKING_DATA
            with self.assertRaises(ValueError):
                self.activate()
        finally:
            self.server.store.directory = actual_directory
        self.assertIsNone(self.server.public_origin)

    def test_external_login_uses_secure_cookie_and_local_login_stays_http(self):
        self.activate()
        headers = self.login()
        for attribute in ("Secure", "HttpOnly", "SameSite=Strict", "Path=/", "Max-Age=28800"):
            self.assertIn(attribute, headers["Set-Cookie"])
        self.assertTrue(self.request("GET", "/api/session")[1]["authenticated"])
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 200)
        status, _, headers = self.request("POST", "/api/logout", {})
        self.assertEqual(status, 200)
        self.assertIn("Secure", headers["Set-Cookie"])
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.request("GET", "/api/admin/articles")[0], 401)
        status, _, headers = self.local_request("POST", "/api/login", {"username": "testadmin", "password": self.password}, auth=False, csrf=False)
        self.assertEqual(status, 200)
        self.assertNotIn("Secure", headers["Set-Cookie"])
        self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")

    def test_demo_session_cookie_cannot_collide_with_working_cms(self):
        self.activate()
        headers = self.login()
        self.assertTrue(headers["Set-Cookie"].startswith("dm_demo_session="))
        self.assertNotIn("dm_cms_session=", headers["Set-Cookie"])
        valid_token = self.cookie.split("=", 1)[1]
        # Даже корректный токен демобазы не принимается под именем рабочей cookie.
        status, session, _ = self.request("GET", "/api/session", headers={"Cookie": "dm_cms_session=" + valid_token})
        self.assertEqual(status, 200)
        self.assertFalse(session["authenticated"])
        self.assertEqual(self.request("GET", "/api/admin/articles", headers={"Cookie": "dm_cms_session=" + valid_token})[0], 401)
        status, session, _ = self.request("GET", "/api/session", headers={"Cookie": "dm_cms_session=unrelated; " + self.cookie})
        self.assertEqual(status, 200)
        self.assertTrue(session["authenticated"])
        status, _, headers = self.request("POST", "/api/logout", {})
        self.assertEqual(status, 200)
        self.assertTrue(headers["Set-Cookie"].startswith("dm_demo_session="))
        self.assertNotIn("dm_cms_session=", headers["Set-Cookie"])

    def test_demo_first_setup_cookie_has_its_own_namespace(self):
        with self.server.store.connect() as db:
            db.execute("DELETE FROM admins")
        status, session, headers = self.local_request("GET", "/api/session")
        self.assertEqual(status, 200)
        self.assertTrue(headers["Set-Cookie"].startswith("dm_demo_setup="))
        self.assertNotIn("dm_cms_setup=", headers["Set-Cookie"])
        setup_cookie = headers["Set-Cookie"].split(";", 1)[0]
        setup_value = setup_cookie.split("=", 1)[1]
        payload = {"username": "testadmin", "password": self.password}
        status, _, _ = self.local_request("POST", "/api/setup", payload, headers={"Cookie": "dm_cms_setup=" + setup_value, "X-Setup-Token": session["setupCsrf"]})
        self.assertEqual(status, 403)
        self.assertFalse(self.server.store.admin_configured())
        status, _, headers = self.local_request("POST", "/api/setup", payload, headers={"Cookie": setup_cookie, "X-Setup-Token": session["setupCsrf"]})
        self.assertEqual(status, 201)
        self.assertTrue(headers["Set-Cookie"].startswith("dm_demo_session="))
        self.assertNotIn("dm_cms_session=", headers["Set-Cookie"])

    def test_cookie_prefix_validation_and_legacy_default(self):
        self.assertEqual(self.server.session_cookie, "dm_demo_session")
        self.assertEqual(self.server.setup_cookie, "dm_demo_setup")
        for prefix in ("", "UPPER", "with-hyphen", "with space", "кириллица", "9start", "a" * 33, "x\r\nHeader", "x; Path=/", 12):
            with mock.patch("serve_cms.Store", side_effect=AssertionError("Store must not open")) as store:
                with self.assertRaises(ValueError, msg=str(prefix)):
                    LocalCmsServer(("127.0.0.1", 0), self.site, self.data, cookie_prefix=prefix)
                store.assert_not_called()
        legacy = LocalCmsServer(("127.0.0.1", 0), self.site, self.data)
        try:
            self.assertEqual(legacy.session_cookie, "dm_cms_session")
            self.assertEqual(legacy.setup_cookie, "dm_cms_setup")
        finally:
            legacy.server_close()

    def test_external_origin_csrf_and_forwarded_header_rejections(self):
        self.activate()
        payload = {"username": "testadmin", "password": self.password}
        for headers in (
            {"Origin": "http://" + self.public_host},
            {"Origin": self.origin},
            {"Origin": "https://attacker.invalid"},
            {"Origin": ""},
            {"Sec-Fetch-Site": "cross-site"},
            {"Host": "attacker.invalid", "X-Forwarded-Host": self.public_host, "X-Forwarded-Proto": "https"},
            {"Origin": "http://" + self.public_host, "X-Forwarded-Proto": "https"},
        ):
            self.assertEqual(self.request("POST", "/api/login", payload, headers=headers)[0], 403, headers)
        # Forwarded-заголовки не меняют корректный точный Host/Origin.
        status, _, _ = self.request("POST", "/api/login", payload, headers={"X-Forwarded-Host": "attacker.invalid", "X-Forwarded-Proto": "http"})
        self.assertEqual(status, 200)
        self.login()
        self.assertEqual(self.request("POST", "/api/admin/articles", {"title": "No CSRF"}, csrf=False)[0], 403)
        self.assertEqual(self.request("POST", "/api/admin/articles", {"title": "Wrong CSRF"}, headers={"X-CSRF-Token": "wrong"})[0], 403)
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        connection.putrequest("POST", "/api/login", skip_host=True)
        for name, value in (("Host", self.public_host), ("Origin", self.public_origin), ("Origin", self.public_origin), ("Content-Type", "application/json"), ("Content-Length", "2")):
            connection.putheader(name, value)
        connection.endheaders(b"{}")
        response = connection.getresponse()
        self.assertEqual(response.status, 403)
        response.read()
        connection.close()

    def test_external_first_setup_never_returns_nonce_or_changes_account(self):
        self.activate()
        status, session, headers = self.request("GET", "/api/session")
        self.assertEqual(status, 200)
        self.assertTrue(session["adminConfigured"])
        self.assertNotIn("setupCsrf", session)
        self.assertNotIn("Set-Cookie", headers)
        status, result, headers = self.request("POST", "/api/setup", {"username": "outsider", "password": self.password})
        self.assertEqual((status, result["code"]), (403, "local_setup_only"))
        self.assertNotIn("Set-Cookie", headers)
        # Даже если отдельная демобаза опустеет после активации, setup не откроется извне.
        with self.server.store.connect() as db:
            db.execute("DELETE FROM admins")
        status, result, headers = self.request("GET", "/api/session")
        self.assertEqual((status, result["code"]), (403, "local_setup_only"))
        self.assertNotIn("Set-Cookie", headers)
        self.assertEqual(self.request("POST", "/api/setup", {"username": "outsider", "password": self.password})[0], 403)
        self.assertFalse(self.server.store.admin_configured())

    def test_external_article_image_publish_archive_and_noindex(self):
        self.activate()
        self.login()
        upload = {"filename": "photo.png", "mime": "image/png", "data": base64.b64encode(test_cms.png()).decode()}
        status, image, _ = self.request("POST", "/api/uploads", upload)
        self.assertEqual(status, 201, image)
        url = image["url"]
        self.assertEqual(self.request("GET", url, auth=False)[0], 404)
        self.assertEqual(self.request("GET", url)[1], test_cms.png())
        payload = {"title": "Демонстрация", "language": "ru", "body": "Статья с изображением", "cover": url, "images": [url], "status": "draft"}
        status, result, _ = self.request("POST", "/api/admin/articles", payload)
        self.assertEqual(status, 201, result)
        article = result["article"]
        self.assertEqual(self.request("GET", "/api/articles", auth=False)[1]["articles"], [])
        status, _, _ = self.request("PUT", "/api/admin/articles/" + article["id"], {"status": "published"})
        self.assertEqual(status, 200)
        status, result, headers = self.request("GET", "/api/articles/" + article["slug"], auth=False)
        self.assertEqual(status, 200)
        self.assertEqual(result["article"]["cover"], url)
        self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
        status, data, headers = self.request("GET", url, auth=False)
        self.assertEqual((status, data), (200, test_cms.png()))
        self.assertEqual(headers["X-Robots-Tag"], "noindex, nofollow")
        self.assertEqual(self.request("PUT", "/api/admin/articles/" + article["id"], {"status": "archived"})[0], 200)
        self.assertEqual(self.request("GET", url, auth=False)[0], 404)
        self.assertEqual(self.request("GET", "/api/articles/" + article["slug"], auth=False)[0], 404)

    def test_cli_rejects_implicit_working_data_without_starting_server(self):
        for arguments in (
            ["--public-origin", self.public_origin],
            ["--public-origin", self.public_origin, "--data-dir", str(WORKING_DATA)],
            ["--public-origin", "https://attacker.invalid", "--data-dir", str(self.data)],
        ):
            result = subprocess.run([sys.executable, str(ROOT / "scripts" / "serve_cms.py"), *arguments], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 2, result.stderr.decode("utf-8", errors="replace"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
