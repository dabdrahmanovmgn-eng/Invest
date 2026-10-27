"""Сценарии восстановления только на временных фиктивных демобазах."""
import contextlib
import hashlib
import io
import secrets
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cms_store import CmsError, Store
import reset_demo_password as recovery


class ResetDemoPasswordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="dengi-reset-demo-test-")
        self.root = Path(self.temp.name)
        self.demo = self.root / "data" / "demo"
        self.working = self.root / "data" / "cms"
        self.store = Store(self.demo)
        self.username = "demo_owner"
        self.old_password = secrets.token_urlsafe(24)
        self.new_password = secrets.token_urlsafe(24)
        self.store.set_admin(self.username, self.old_password)
        self.article = self.store.save_article({"title": "Фиктивная статья", "body": "Тестовый материал", "language": "ru", "status": "published"})
        self.original_articles = self.store.list_articles()
        self.output = io.StringIO()
        self.config_patches = (
            patch.object(recovery, "DEMO_DATA", self.demo),
            patch("serve_cms.WORKING_DATA", self.working),
            patch("sys.argv", ["reset_demo_password.py"]),
            patch.object(recovery.sys.stdin, "isatty", return_value=True),
            patch.object(recovery.sys.stderr, "isatty", return_value=True),
        )
        for configured in self.config_patches:
            configured.start()

    def tearDown(self):
        for configured in reversed(self.config_patches):
            configured.stop()
        self.temp.cleanup()

    def digest(self, directory=None):
        path = (directory or self.demo) / "cms.sqlite3"
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def invoke(self, username=None, passwords=None):
        with patch("builtins.input", return_value=self.username if username is None else username), patch.object(recovery.getpass, "getpass", side_effect=passwords if passwords is not None else [self.new_password, self.new_password]) as getpass, contextlib.redirect_stdout(self.output):
            recovery.main()
        return getpass

    def test_existing_demo_password_changes_and_articles_are_preserved(self):
        self.invoke()
        self.assertEqual(self.store.list_articles(), self.original_articles)
        self.assertIsNone(self.store.authenticate(self.username, self.old_password))
        self.assertIsNotNone(self.store.authenticate(self.username, self.new_password))
        self.assertIn("Перезапуск демо не нужен", self.output.getvalue())
        self.assertNotIn(self.old_password, self.output.getvalue())
        self.assertNotIn(self.new_password, self.output.getvalue())
        self.assertFalse(self.working.exists())

    def test_unknown_login_never_creates_account_or_prompts_password(self):
        before = self.digest()
        with patch("builtins.input", return_value="unknown_user"), patch.object(recovery.getpass, "getpass") as getpass, contextlib.redirect_stdout(self.output):
            with self.assertRaises(CmsError):
                recovery.main()
            getpass.assert_not_called()
        self.assertEqual(self.digest(), before)
        with self.store.connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM admins WHERE username='unknown_user'").fetchone())
        self.assertEqual(self.store.list_articles(), self.original_articles)

    def test_mismatched_passwords_leave_database_unchanged(self):
        before = self.digest()
        with self.assertRaises(CmsError):
            self.invoke(passwords=[self.new_password, self.new_password + "other"])
        self.assertEqual(self.digest(), before)
        self.assertEqual(self.store.list_articles(), self.original_articles)

    def test_noninteractive_mode_exits_before_store_or_secret_prompt(self):
        before = self.digest()
        with patch.object(recovery.sys.stdin, "isatty", return_value=False), patch.object(recovery, "Store") as store, patch.object(recovery.getpass, "getpass") as getpass:
            with self.assertRaises(CmsError):
                recovery.main()
            store.assert_not_called()
            getpass.assert_not_called()
        self.assertEqual(self.digest(), before)

    def test_wrong_directory_is_rejected_before_opening_working_store(self):
        # Эта рабочая база тоже фиктивная и находится только в TemporaryDirectory.
        working_store = Store(self.working)
        working_store.set_admin("working_owner", secrets.token_urlsafe(24))
        before_working = self.digest(self.working)
        before_demo = self.digest()
        with patch.object(recovery, "DEMO_DATA", self.working), patch.object(recovery, "Store") as store, patch.object(recovery.getpass, "getpass") as getpass:
            with self.assertRaises(ValueError):
                recovery.main()
            store.assert_not_called()
            getpass.assert_not_called()
        self.assertEqual(self.digest(self.working), before_working)
        self.assertEqual(self.digest(), before_demo)

    def test_missing_demo_database_is_not_created(self):
        absent = self.root / "fresh" / "data" / "demo"
        with patch.object(recovery, "DEMO_DATA", absent), patch.object(recovery, "Store") as store:
            with self.assertRaises(CmsError):
                recovery.main()
            store.assert_not_called()
        self.assertFalse(absent.exists())

    def test_account_removed_before_write_is_not_recreated(self):
        with self.store.connect() as connection:
            connection.execute("DELETE FROM admins WHERE username=?", (self.username,))
        before = self.digest()
        with self.assertRaises(CmsError):
            recovery.reset_existing_account(self.store, self.username, self.new_password, self.new_password)
        self.assertEqual(self.digest(), before)
        with self.store.connect() as connection:
            self.assertIsNone(connection.execute("SELECT 1 FROM admins WHERE username=?", (self.username,)).fetchone())


if __name__ == "__main__":
    unittest.main(verbosity=2)
