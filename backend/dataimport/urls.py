from django.urls import path

from .views import ImportCommitView, ImportPreviewView, ImportSchemaView, ImportTemplateView

urlpatterns = [
    path("import/<slug:entity>/schema/", ImportSchemaView.as_view(), name="import-schema"),
    path("import/<slug:entity>/preview/", ImportPreviewView.as_view(), name="import-preview"),
    path("import/<slug:entity>/commit/", ImportCommitView.as_view(), name="import-commit"),
    path("import/<slug:entity>/template/", ImportTemplateView.as_view(), name="import-template"),
]
