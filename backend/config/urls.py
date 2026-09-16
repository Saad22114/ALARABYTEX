from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("branches.urls")),
    path("api/", include("suppliers.urls")),
    path("api/", include("sales.urls")),
    path("api/", include("expenses.urls")),
    path("api/settings/", include("appsettings.urls")),
    path("api/dashboard/", include("dashboard.urls")),
    path("api/reports/", include("reports.urls")),
    path("api/", include("warehouses.urls")),
    path("api/", include("partners.urls")),
    path("api/", include("sale_sessions.urls")),
    path("api/", include("customers.urls")),
    path("api/", include("accounting.urls")),
    path("api/", include("messaging.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
