"""Команды Django: запуск, пользователи, миграции и проверки."""
import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "irsite.settings")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
