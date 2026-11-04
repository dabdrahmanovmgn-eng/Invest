from django.contrib import admin
from django.urls import path, re_path

from articles import views

admin.site.site_header = "Dengi Market — редактор статей"
admin.site.site_title = "Dengi Market"
admin.site.index_title = "Управление публикациями"

urlpatterns = [
    path("admin/index.html", views.admin_redirect),
    path("admin/", admin.site.urls),
    path("api/articles", views.article_list),
    path("api/articles/<slug:slug>", views.article_detail),
    re_path(r"^uploads/(?P<name>[a-f0-9]{32}\.(?:png|jpg|webp))$", views.upload),
    path("", views.home),
    path("index.html", views.home),
    path("index.ru.html", views.legacy_home),
    path("articles/", views.editorial_list),
    path("articles/index.html", views.editorial_list),
    path("article/", views.editorial_detail, name="article-page"),
    path("article/index.html", views.editorial_detail),
    path("sitemap.xml", views.sitemap),
    re_path(r"^(?P<path>(?:assets|documents)/.+)$", views.site_asset),
]
