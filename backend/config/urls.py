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
]
