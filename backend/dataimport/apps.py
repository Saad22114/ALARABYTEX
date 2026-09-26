from django.apps import AppConfig


class DataImportConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dataimport"
    verbose_name = "الاستيراد من Excel"
