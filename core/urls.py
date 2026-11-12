from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("reports/sales/", views.sales_report, name="sales_report"),
    path("reports/sales.csv", views.sales_report_csv, name="sales_report_csv"),
    path("settings/", views.site_settings, name="settings"),
]
