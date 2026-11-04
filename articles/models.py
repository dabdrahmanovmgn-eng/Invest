import uuid
from pathlib import Path

from concurrency.fields import IntegerVersionField
from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from .validators import validate_image

def image_name(instance, filename):
    suffix = Path(filename).suffix.lower()
    return uuid.uuid4().hex + (".jpg" if suffix == ".jpeg" else suffix)

class ArticleQuerySet(models.QuerySet):
    def public(self):
        return self.filter(status="published", language="en")

class Article(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField("Заголовок", max_length=180)
    slug = models.SlugField("Адрес статьи", max_length=120, unique=True, blank=True,
        validators=[RegexValidator(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z", "Строчные латинские буквы, цифры и дефисы.")],
        help_text="Можно оставить пустым: адрес создастся автоматически. После публикации лучше не менять.")
    excerpt = models.TextField("Анонс", max_length=600, blank=True)
    body = models.TextField("Текст", max_length=100000, blank=True,
        validators=[MaxLengthValidator(100000)], help_text="Обычный текст. Пустая строка разделяет абзацы; HTML не выполняется.")
    language = models.CharField("Язык", max_length=2, choices=[("en", "English"), ("ru", "Русский")], default="en")
    status = models.CharField("Статус", max_length=10, default="draft",
        choices=[("draft", "Черновик"), ("published", "Опубликовано"), ("archived", "Архив")])
    cover = models.ImageField("Обложка", upload_to=image_name, blank=True, validators=[validate_image])
    created_at = models.DateTimeField("Создано", default=timezone.now, editable=False)
    updated_at = models.DateTimeField("Изменено", default=timezone.now, editable=False)
    published_at = models.DateTimeField("Впервые опубликовано", null=True, blank=True, editable=False)
    revision = IntegerVersionField("Версия", default=0, help_text="При конфликте сохранения скопируйте свой текст и откройте актуальную статью в новой вкладке.")
    objects = ArticleQuerySet.as_manager()

    class Meta:
        verbose_name = "Статья"
        verbose_name_plural = "Статьи"
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(condition=models.Q(language__in=["en", "ru"]), name="article_valid_language"),
            models.CheckConstraint(condition=models.Q(status__in=["draft", "published", "archived"]), name="article_valid_status"),
            models.CheckConstraint(condition=~models.Q(status="published") | models.Q(language="en"), name="article_public_english"),
            models.CheckConstraint(condition=~models.Q(status="published") | ~models.Q(body=""), name="article_public_body"),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        if not self.title.strip():
            raise ValidationError({"title": "Укажите заголовок."})
        if self.status == "published":
            if self.language != "en":
                raise ValidationError({"status": "На сайте публикуются только английские статьи. Русскую сохраните как черновик или в архив."})
            if not self.body.strip():
                raise ValidationError({"body": "Для публикации нужен текст статьи."})

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.title)[:80].rstrip("-") or "article"
            self.slug = f"{base}-{uuid.uuid4().hex[:8]}"
        self.clean()
        self.updated_at = timezone.now()
        if self.status == "published" and not self.published_at:
            self.published_at = timezone.now()
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("article-page") + f"?slug={self.slug}"

class ArticleImage(models.Model):
    article = models.ForeignKey(Article, on_delete=models.CASCADE, related_name="gallery")
    image = models.ImageField("Изображение", upload_to=image_name, validators=[validate_image])
    position = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Изображение галереи"
        verbose_name_plural = "Галерея — до 12 изображений"
        ordering = ["position", "id"]

    def __str__(self):
        return Path(self.image.name).name
