import mimetypes
import re

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET
from django.views.static import serve

from .models import Article, ArticleImage

def stamp(value):
    return value.isoformat().replace("+00:00", "Z") if value else None

def serialize(article):
    return {
        "id": article.pk.hex, "slug": article.slug, "title": article.title,
        "excerpt": article.excerpt, "body": article.body, "language": article.language,
        "cover": article.cover.url if article.cover else "",
        "images": [image.image.url for image in article.gallery.all()],
        "created_at": stamp(article.created_at), "updated_at": stamp(article.updated_at),
        "published_at": stamp(article.published_at),
    }

@require_GET
def article_list(request):
    if request.GET.get("language", "en") != "en":
        return JsonResponse({"articles": []})
    items = Article.objects.public().prefetch_related("gallery").order_by("-published_at", "-created_at", "-id")[:500]
    return JsonResponse({"articles": [serialize(item) for item in items]})

@require_GET
def article_detail(request, slug):
    article = get_object_or_404(Article.objects.public().prefetch_related("gallery"), slug=slug)
    return JsonResponse({"article": serialize(article)})

@require_GET
def upload(request, name):
    # Выдача медиа всегда идёт через проверку публикации, включая внешний сервер.
    if request.user.is_active and request.user.is_staff and request.user.has_perm("articles.view_article"):
        allowed = Article.objects.filter(cover=name).exists() or ArticleImage.objects.filter(image=name).exists()
    else:
        allowed = Article.objects.public().filter(cover=name).exists() or ArticleImage.objects.filter(
            image=name, article__in=Article.objects.public()
        ).exists()
    if not allowed:
        raise Http404
    path = settings.MEDIA_ROOT / name
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open("rb"), content_type=mimetypes.guess_type(name)[0])
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response

def file_page(name):
    path = settings.SITE_DIR / name
    return FileResponse(path.open("rb"), content_type="text/html; charset=utf-8")

@require_GET
def home(request):
    return file_page("index.html")

@require_GET
def legacy_home(request):
    return file_page("index.ru.html")

@require_GET
def editorial_list(request):
    return file_page("articles/index.html")

@require_GET
def editorial_detail(request):
    return file_page("article/index.html")

@require_GET
def sitemap(request):
    return FileResponse((settings.SITE_DIR / "sitemap.xml").open("rb"), content_type="application/xml")

@require_GET
def site_asset(request, path):
    # Только две явные публичные папки, без доступа к data/, work/ или исходникам.
    target = (settings.SITE_DIR / path).resolve()
    allowed = any(target.is_relative_to((settings.SITE_DIR / folder).resolve()) for folder in ("assets", "documents"))
    if not allowed or target == (settings.SITE_DIR / "assets/team/manifest.json").resolve():
        raise Http404
    return serve(request, path, document_root=settings.SITE_DIR, show_indexes=False)

@require_GET
def admin_redirect(request):
    return redirect("admin:index")

def conflict(request, target=None):
    # Узкая гонка после проверки формы: текст возвращается только автору POST.
    labels = {"title": "Заголовок", "slug": "Адрес статьи", "excerpt": "Анонс", "body": "Текст", "language": "Язык", "status": "Статус"}
    values = [{"id": key, "label": label, "value": request.POST.get(key, "")} for key, label in labels.items()]
    return render(request, "admin/article_conflict.html", {"values": values}, status=409)
