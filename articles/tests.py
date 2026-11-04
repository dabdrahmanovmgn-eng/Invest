"""Регрессии Django-замены. Данные только во временных каталогах и тестовой БД."""
import json
import sqlite3
import tempfile
import uuid
from io import BytesIO, StringIO
from pathlib import Path
from contextlib import closing
from unittest.mock import patch

from concurrency.exceptions import RecordModifiedError
from concurrency.forms import VersionField
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, TestCase, override_settings
from django.db import transaction
from PIL import Image

from .models import Article, ArticleImage
from .validators import validate_image

def png(name="sample.png"):
    output = BytesIO()
    Image.new("RGB", (4, 3), "green").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")

class CmsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("editor", password="test-only-strong-password-8492")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(MEDIA_ROOT=Path(self.temp.name), ALLOWED_HOSTS=["testserver", "localhost"])
        self.override.enable()
        self.addCleanup(self.override.disable)

    def article(self, **kwargs):
        values = {"title": "Investor update", "body": "First paragraph.\n\nSecond paragraph."}
        values.update(kwargs)
        return Article.objects.create(**values)

    def admin_data(self, article=None, **kwargs):
        data = {
            "title": "Investor update", "slug": "investor-update", "language": "en", "body": "Article body",
            "excerpt": "Summary", "status": "draft", "revision": "",
            "gallery-TOTAL_FORMS": "0", "gallery-INITIAL_FORMS": "0",
            "gallery-MIN_NUM_FORMS": "0", "gallery-MAX_NUM_FORMS": "12", "_save": "Сохранить",
        }
        if article:
            for key in ("title", "slug", "language", "body", "excerpt", "status"):
                data[key] = getattr(article, key)
            data["revision"] = str(VersionField().prepare_value(article.revision))
        data.update(kwargs)
        return data

    def test_public_visibility_and_english_only(self):
        pub = self.article(status="published")
        self.article(title="Draft")
        self.article(title="Archived", status="archived")
        self.article(title="Русский", language="ru")
        rows = self.client.get("/api/articles").json()["articles"]
        self.assertEqual([row["slug"] for row in rows], [pub.slug])
        self.assertNotIn("revision", rows[0])
        self.assertNotIn("status", rows[0])
        self.assertEqual(self.client.get("/api/articles?language=ru").json()["articles"], [])

    def test_detail_hides_draft_and_archive(self):
        item = self.article()
        self.assertEqual(self.client.get(f"/api/articles/{item.slug}").status_code, 404)
        item.status = "published"
        item.save()
        self.assertEqual(self.client.get(f"/api/articles/{item.slug}").json()["article"]["body"], item.body)
        date = item.published_at
        item.status = "archived"
        item.save()
        self.assertEqual(self.client.get(f"/api/articles/{item.slug}").status_code, 404)
        item.status = "published"
        item.save()
        self.assertEqual(item.published_at, date)

    def test_ru_and_empty_publication_rejected(self):
        for values in ({"language": "ru"}, {"body": "  "}):
            with self.assertRaises(ValidationError):
                self.article(status="published", **values)

    def test_admin_crud_and_gallery(self):
        self.client.force_login(self.admin)
        data = self.admin_data(cover=png(), **{
            "gallery-TOTAL_FORMS": "1", "gallery-0-image": png("gallery.png"), "gallery-0-position": "0",
        })
        response = self.client.post("/admin/articles/article/add/", data)
        self.assertEqual(response.status_code, 302, response.context and response.context.get("errors"))
        article = Article.objects.get(slug="investor-update")
        self.assertEqual(article.gallery.count(), 1)
        response = self.client.get(article.cover.url)
        self.assertEqual(response.status_code, 200)
        response.close()
        self.assertTrue(article.get_absolute_url().startswith("/article/?slug="))

    def test_admin_publish_archive_restore(self):
        self.client.force_login(self.admin)
        article = self.article()
        for status in ("published", "archived", "draft", "published"):
            response = self.client.post(f"/admin/articles/article/{article.pk}/change/", self.admin_data(article, status=status))
            self.assertEqual(response.status_code, 302)
            article.refresh_from_db()
            self.assertEqual(article.status, status)

    def test_admin_ru_error_retains_text(self):
        self.client.force_login(self.admin)
        response = self.client.post("/admin/articles/article/add/", self.admin_data(language="ru", status="published", body="Сохранить этот текст"))
        self.assertContains(response, "Сохранить этот текст")
        self.assertEqual(Article.objects.count(), 0)

    def test_stale_admin_form_does_not_overwrite(self):
        self.client.force_login(self.admin)
        article = self.article()
        data = self.admin_data(article, body="My unsaved text")
        article.body = "Other editor saved"
        article.save()
        response = self.client.post(f"/admin/articles/article/{article.pk}/change/", data)
        self.assertContains(response, "My unsaved text")
        self.assertContains(response, "Статья уже изменена другим редактором")
        article.refresh_from_db()
        self.assertEqual(article.body, "Other editor saved")

    def test_model_atomic_version_check(self):
        article = self.article()
        stale = Article.objects.get(pk=article.pk)
        article.body = "New saved text"
        article.save()
        stale.body = "Old form text"
        with self.assertRaises(RecordModifiedError), transaction.atomic():
            stale.save()
        self.assertEqual(Article.objects.get(pk=article.pk).body, "New saved text")

    def test_missing_version_does_not_overwrite(self):
        self.client.force_login(self.admin)
        article = self.article()
        data = self.admin_data(article, body="Must not save", revision="")
        response = self.client.post(f"/admin/articles/article/{article.pk}/change/", data)
        self.assertNotEqual(response.status_code, 302)
        self.assertNotEqual(Article.objects.get(pk=article.pk).body, "Must not save")

    def test_gallery_limit_is_enforced_on_server(self):
        self.client.force_login(self.admin)
        data = self.admin_data(**{"gallery-TOTAL_FORMS": "13"})
        for index in range(13):
            data[f"gallery-{index}-image"] = png(f"image-{index}.png")
            data[f"gallery-{index}-position"] = str(index)
        response = self.client.post("/admin/articles/article/add/", data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Article.objects.count(), 0)

    def test_narrow_save_race_returns_safe_text_copy(self):
        self.client.force_login(self.admin)
        self.client.raise_request_exception = False
        item = self.article()
        data = self.admin_data(item, body="<script>QA preserved text</script>")
        with patch.object(Article, "save", side_effect=RecordModifiedError("race", target=item)):
            response = self.client.post(f"/admin/articles/article/{item.pk}/change/", data)
        self.assertContains(response, "QA preserved text", status_code=409)
        self.assertContains(response, "&lt;script&gt;", status_code=409)
        self.assertNotContains(response, "<script>QA", status_code=409)

    def test_private_media_visibility_and_revocation(self):
        item = self.article(cover=png())
        gallery = ArticleImage.objects.create(article=item, image=png("gallery.png"))
        urls = [item.cover.url, gallery.image.url]
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)
        item.status = "published"
        item.save()
        for url in urls:
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertIn("no-store", response["Cache-Control"])
            response.close()
        item.status = "archived"
        item.save()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 404)

    def test_staff_needs_article_permissions(self):
        staff = get_user_model().objects.create_user("limited", is_staff=True)
        item = self.article(cover=png())
        self.client.force_login(staff)
        self.assertEqual(self.client.get(item.cover.url).status_code, 404)
        self.assertEqual(self.client.get("/admin/articles/article/").status_code, 403)
        staff.user_permissions.add(Permission.objects.get(codename="view_article"))
        response = self.client.get(item.cover.url)
        self.assertEqual(response.status_code, 200)
        response.close()

    def test_admin_requires_login_and_cannot_delete(self):
        self.assertEqual(self.client.get("/admin/articles/article/").status_code, 302)
        self.client.force_login(self.admin)
        item = self.article()
        self.assertEqual(self.client.post(f"/admin/articles/article/{item.pk}/delete/", {"post": "yes"}).status_code, 403)
        self.assertTrue(Article.objects.filter(pk=item.pk).exists())

    def test_csrf_is_required_for_login_and_changes(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/admin/login/", {"username": "editor", "password": "test-only-strong-password-8492"}).status_code, 403)
        client.force_login(self.admin)
        self.assertEqual(client.post("/admin/articles/article/add/", self.admin_data()).status_code, 403)
        client.get("/admin/articles/article/add/")
        self.assertEqual(client.post("/admin/articles/article/add/", self.admin_data(), HTTP_X_CSRFTOKEN=client.cookies["csrftoken"].value, HTTP_ORIGIN="https://evil.invalid").status_code, 403)

    def test_session_invalidated_after_password_change(self):
        self.client.force_login(self.admin)
        user = get_user_model().objects.get(pk=self.admin.pk)
        user.set_password("another-strong-password-3940")
        user.save()
        self.assertEqual(self.client.get("/admin/articles/article/").status_code, 302)

    def test_axes_limit_and_untrusted_proxy_headers(self):
        for _ in range(10):
            self.client.post("/admin/login/", {"username": "editor", "password": "wrong"}, REMOTE_ADDR="192.0.2.10")
        response = self.client.post("/admin/login/", {"username": "editor", "password": "test-only-strong-password-8492"}, REMOTE_ADDR="192.0.2.10", HTTP_X_FORWARDED_FOR="192.0.2.20")
        self.assertEqual(response.status_code, 429)
        response = self.client.post("/admin/login/", {"username": "editor", "password": "test-only-strong-password-8492"}, REMOTE_ADDR="192.0.2.20")
        self.assertEqual(response.status_code, 302)

    def test_legacy_custom_endpoints_unavailable(self):
        for path in ("/api/setup", "/api/login", "/api/session", "/api/admin/articles", "/data/cms/cms.sqlite3", "/data/django/db.sqlite3", "/assets/../../data/django/db.sqlite3", "/assets/team/../../../../data/cms/cms.sqlite3", "/uploads/../db.sqlite3", "/assets/team/manifest.json", "/assets/team/../team/manifest.json"):
            self.assertIn(self.client.get(path).status_code, (400, 404), path)

    def test_public_site_and_documents(self):
        for path in ("/", "/index.html", "/index.ru.html", "/articles/", "/article/?slug=test", "/assets/config.js", "/documents/financial-statements-2025-en.pdf"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            response.close()
        self.assertRedirects(self.client.get("/admin/index.html"), "/admin/", fetch_redirect_response=False)

    def test_invalid_images(self):
        for name, data in (("bad.svg", b"<svg></svg>"), ("bad.png", b"not a png"), ("bad.png", png().read()[:-15]), ("bad.jpg", png().read()), ("huge.png", b"x" * (8 * 1024 * 1024 + 1))):
            with self.assertRaises(ValidationError, msg=name):
                validate_image(SimpleUploadedFile(name, data))

class ImportTests(TestCase):
    def setUp(self):
        self.source_temp = tempfile.TemporaryDirectory()
        self.target_temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.source_temp.cleanup)
        self.addCleanup(self.target_temp.cleanup)
        self.source = Path(self.source_temp.name)
        self.media = Path(self.target_temp.name)
        (self.source / "uploads").mkdir()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.name = uuid.uuid4().hex + ".png"
        (self.source / "uploads" / self.name).write_bytes(png().read())
        self.id = uuid.uuid4().hex
        with closing(sqlite3.connect(self.source / "cms.sqlite3")) as db, db:
            db.execute("CREATE TABLE articles (id,slug,title,excerpt,body,language,cover,images,status,created_at,updated_at,published_at)")
            db.execute("INSERT INTO articles VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (self.id, "old-post", "Original title", "Original excerpt", "Original body", "en", "/uploads/" + self.name, json.dumps(["/uploads/" + self.name]), "published", "2025-02-01T08:00:00Z", "2025-03-01T09:00:00Z", "2025-03-01T09:00:00Z"))

    def run_import(self, apply=False):
        call_command("import_legacy_cms", source=self.source, apply=apply, stdout=StringIO())

    def test_dry_run_has_no_content_writes(self):
        before = (self.source / "cms.sqlite3").read_bytes()
        self.run_import()
        self.assertEqual(Article.objects.count(), 0)
        self.assertFalse(list(self.media.iterdir()))
        self.assertEqual(before, (self.source / "cms.sqlite3").read_bytes())

    def test_import_preserves_content_dates_media_and_source(self):
        before = (self.source / "cms.sqlite3").read_bytes()
        self.run_import(apply=True)
        item = Article.objects.get()
        self.assertEqual(item.pk.hex, self.id)
        self.assertEqual(item.body, "Original body")
        self.assertEqual(item.created_at.isoformat(), "2025-02-01T08:00:00+00:00")
        self.assertEqual(item.updated_at.isoformat(), "2025-03-01T09:00:00+00:00")
        self.assertEqual(item.published_at.isoformat(), "2025-03-01T09:00:00+00:00")
        self.assertEqual(item.gallery.count(), 1)
        self.assertEqual((self.media / self.name).read_bytes(), (self.source / "uploads" / self.name).read_bytes())
        self.assertEqual(before, (self.source / "cms.sqlite3").read_bytes())
        self.assertEqual(get_user_model().objects.count(), 0)

    def test_repeat_import_cannot_overwrite(self):
        self.run_import(apply=True)
        with self.assertRaises(CommandError):
            self.run_import(apply=True)
        self.assertEqual(Article.objects.count(), 1)

    def test_missing_image_aborts(self):
        (self.source / "uploads" / self.name).unlink()
        with self.assertRaises(CommandError):
            self.run_import(apply=True)
        self.assertEqual(Article.objects.count(), 0)

    def test_existing_different_image_is_not_replaced(self):
        (self.media / self.name).write_bytes(b"keep existing")
        with self.assertRaises(CommandError):
            self.run_import(apply=True)
        self.assertEqual((self.media / self.name).read_bytes(), b"keep existing")
        self.assertEqual(Article.objects.count(), 0)

    def test_legacy_ru_publication_becomes_draft(self):
        with closing(sqlite3.connect(self.source / "cms.sqlite3")) as db, db:
            db.execute("UPDATE articles SET language='ru'")
        self.run_import(apply=True)
        self.assertEqual(Article.objects.get().status, "draft")
