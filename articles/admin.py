from concurrency.forms import ConcurrentForm
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.contrib import admin
from django.forms.models import BaseInlineFormSet

from .models import Article, ArticleImage

class GalleryFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.validate_max = True

class GalleryInline(admin.TabularInline):
    model = ArticleImage
    formset = GalleryFormSet
    extra = 0
    max_num = 12
    fields = ["image", "position"]

class ArticleForm(ConcurrentForm):
    def clean(self):
        values = super().clean()
        if NON_FIELD_ERRORS in self._errors:
            self._errors.pop(NON_FIELD_ERRORS)
            self.add_error(None, "Статья уже изменена другим редактором. Ваш текст остался в форме: скопируйте его, откройте актуальную статью в новой вкладке и перенесите нужные правки.")
        if not self.instance._state.adding and not values.get("revision"):
            raise ValidationError("Отсутствует версия статьи. Скопируйте текст и откройте актуальную статью в новой вкладке.")
        return values

@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleForm
    list_display = ["title", "language", "status", "updated_at", "published_at"]
    list_filter = ["status", "language"]
    search_fields = ["title", "excerpt", "body", "slug"]
    readonly_fields = ["created_at", "updated_at", "published_at"]
    fields = ["title", "slug", "language", "excerpt", "body", "cover", "status", "revision", "created_at", "updated_at", "published_at"]
    inlines = [GalleryInline]
    save_on_top = True
    actions = None
    list_per_page = 30

    def has_delete_permission(self, request, obj=None):
        # Архивирование обратимо и не ломает возможность восстановить материал.
        return False

    class Media:
        js = ["articles/editor.js"]
