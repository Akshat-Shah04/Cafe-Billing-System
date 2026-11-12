from django.urls import include, path

urlpatterns = [
    path("", include("core.urls")),
    path("", include("accounts.urls")),
    path("", include("menu.urls")),
    path("", include("orders.urls")),
]
