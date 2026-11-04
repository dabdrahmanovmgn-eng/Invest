"""Перенос контента из прежней CMS; исходная база открывается только для чтения."""
import hashlib
import json
import re
import shutil
import sqlite3
from contextlib import closing
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from articles.models import Article, ArticleImage
from articles.validators import validate_image

UPLOAD = re.compile(r"\A/uploads/([a-f0-9]{32}\.(?:png|jpg|webp))\Z")

class Command(BaseCommand):
    help = "Проверить перенос статей и изображений; запись только с --apply. Аккаунты и сессии не переносятся."

    def add_arguments(self, parser):
        parser.add_argument("--source", required=True, type=Path, help="Каталог с cms.sqlite3 и uploads/")
        parser.add_argument("--apply", action="store_true", help="Записать в новую Django-базу; без флага только проверка")

    def handle(self, *args, **options):
        source = options["source"].resolve()
        database = source / "cms.sqlite3"
        if not database.is_file():
            raise CommandError("В исходном каталоге нет cms.sqlite3.")
        # Приватные данные не читаются и не включаются в отчёт.
        try:
            with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
                db.row_factory = sqlite3.Row
                rows = [dict(row) for row in db.execute("SELECT id,slug,title,excerpt,body,language,cover,images,status,created_at,updated_at,published_at FROM articles")]
            articles, files = [], {}
            for row in rows:
                gallery = json.loads(row.pop("images"))
                if not isinstance(gallery, list) or len(gallery) > 12:
                    raise ValueError("Некорректная галерея в исходной базе.")
                names = []
                for url in ([row["cover"]] if row["cover"] else []) + gallery:
                    match = UPLOAD.fullmatch(url)
                    if not match:
                        raise ValueError("Небезопасный путь изображения.")
                    name = match[1]
                    path = (source / "uploads" / name).resolve()
                    if not path.is_relative_to((source / "uploads").resolve()) or not path.is_file():
                        raise ValueError("Отсутствует изображение статьи.")
                    validate_image(SimpleUploadedFile(name, path.read_bytes()))
                    files[name] = path
                    names.append(name)
                row["cover"] = names[0] if row["cover"] else ""
                gallery_names = names[1:] if row["cover"] else names
                # Согласованное правило: прежние RU-публикации становятся черновиками.
                if row["language"] == "ru" and row["status"] == "published":
                    row["status"] = "draft"
                for field in ("created_at", "updated_at", "published_at"):
                    value = row[field]
                    row[field] = parse_datetime(value) if value else None
                    if value and row[field] is None:
                        raise ValueError("Некорректная дата статьи.")
                if not row["created_at"] or not row["updated_at"]:
                    raise ValueError("У статьи нет даты создания/изменения.")
                article = Article(**row, revision=1)
                article.full_clean(exclude=["cover"])
                if Article.objects.filter(pk=article.pk).exists() or Article.objects.filter(slug=article.slug).exists():
                    raise ValueError("Статья уже существует в Django. Повторный импорт и перезапись запрещены.")
                articles.append((article, gallery_names))
        except Exception as error:
            raise CommandError(f"Перенос отменён: {error}") from error
        self.stdout.write(f"Проверено: статей — {len(articles)}, изображений — {len(files)}. Аккаунты и сессии не переносятся.")
        if not options["apply"]:
            self.stdout.write("Проверка завершена без записи. Для переноса добавьте --apply.")
            return
        target_dir = Path(settings.MEDIA_ROOT)
        target_dir.mkdir(parents=True, exist_ok=True)
        created_files = []
        try:
            with transaction.atomic():
                for name, source_path in files.items():
                    target = target_dir / name
                    if target.exists():
                        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source_path.read_bytes()).digest():
                            raise ValueError("Конфликт имени изображения. Существующий файл не изменён.")
                    else:
                        with target.open("xb") as output, source_path.open("rb") as input_file:
                            created_files.append(target)
                            shutil.copyfileobj(input_file, output)
                # bulk_create сохраняет исходные даты, не вызывая save/сигналы изменения.
                Article.objects.bulk_create([article for article, _ in articles])
                ArticleImage.objects.bulk_create([
                    ArticleImage(article=article, image=name, position=index)
                    for article, names in articles for index, name in enumerate(names)
                ])
        except Exception as error:
            for path in created_files:
                path.unlink(missing_ok=True)
            raise CommandError(f"Перенос отменён, новые записи и файлы удалены: {error}") from error
        self.stdout.write(self.style.SUCCESS("Контент перенесён. Исходные данные не изменялись."))
