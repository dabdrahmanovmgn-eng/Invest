# Dengi Market — сайт инвесторов

Публичный английский сайт и редактор статей на Django 5.2 LTS со стандартной Django Admin. Утверждённый дизайн, показатели, контакты и финансовые PDF сохранены. Русские материалы доступны редакторам как черновики или архив.

## Быстрый запуск на Windows

Установите Python 3.11+ и откройте `START-SITE.cmd`. При первом запуске создаётся `.venv`, устанавливаются зависимости и готовится новая база Django. Затем в окне нужно самостоятельно создать администратора; пароль вводится скрыто.

- Сайт: http://127.0.0.1:8345/
- Статьи: http://127.0.0.1:8345/articles/
- Django Admin: http://127.0.0.1:8345/admin/
- Остановка: Ctrl+C в окне сервера.

Первый запуск требует интернета для установки пакетов. `START-DEMO.cmd` также запускает только локальный Django. Внешний туннель автоматически не включается.

## Инструкции

- [Редактору: статьи, картинки, публикация и архив](docs/CMS.md).
- [Разработчику: установка, перенос и сопровождение](docs/DJANGO.md).
- [Результаты проверки](docs/DJANGO-QA.md).

## Установка вручную

```text
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python manage.py createsuperuser
.venv\Scripts\python manage.py runserver 127.0.0.1:8345
```

На Linux/macOS используйте `.venv/bin/python`. Учётные данные в комплект не входят.

## Состав и проверки

`site/` — существующая вёрстка; `irsite/` — настройки и маршруты Django; `articles/` — модели, стандартная админка, публичный API, импорт и тесты. Новое приватное хранилище — `data/django/`.

```text
.venv\Scripts\python manage.py check
.venv\Scripts\python manage.py makemigrations --check --dry-run
.venv\Scripts\python manage.py test articles
.venv\Scripts\python scripts/verify_seo.py
```

В полном локальном проекте дополнительно выполняются `scripts/verify_project.py` и `scripts/verify_site.py`. Им нужны исходные материалы `sources/`, поэтому в чистый комплект GitHub они не включаются.

## GitHub и размещение

GitHub хранит код. GitHub Pages обслуживает статическую папку `site/`, а админка и API требуют серверного запуска. В существующем репозитории push в `main` публикует Pages; версия с Django готовится в отдельной ветке. Подготовка кода не означает разрешения на размещение, изменение DNS или настройку почты.

Не отправляйте в GitHub `data/`, `.venv/`, `.env`, рабочие архивы, служебные manifest, базы и загруженные редакторами изображения.
