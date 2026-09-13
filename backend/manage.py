#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from pathlib import Path

import dotenv

# Correct BASE_DIR: points to the directory containing the .env and config/
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

dotenv.load_dotenv(BASE_DIR / ".env")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def main():
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "تعذر استيراد Django. تأكد من تثبيت المتطلبات في ملف requirements.txt"
            " وتفعيل البيئة الافتراضية."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()