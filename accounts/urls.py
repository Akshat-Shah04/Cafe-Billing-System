from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html", redirect_authenticated_user=True), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("users/", views.user_list, name="users"),
    path("users/form/", views.user_form, name="user_form"),
    path("users/save/", views.user_save, name="user_save"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("account/form/", views.account_form, name="account_form"),
    path("account/save/", views.account_save, name="account_save"),
]
