from django.urls import path

from . import views

app_name = "menu"

urlpatterns = [
    path("categories/", views.category_list, name="categories"),
    path("categories/save/", views.category_save, name="category_save"),
    path("categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("products/", views.product_list, name="products"),
    path("products/save/", views.product_save, name="product_save"),
    path("products/<int:pk>/delete/", views.product_delete, name="product_delete"),
]
