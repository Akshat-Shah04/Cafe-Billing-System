from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("orders/", views.order_list, name="list"),
    path("take-orders/", views.pos, name="pos"),
    path("take-orders/<int:pk>/", views.pos, name="pos_edit"),
    path("orders/save/", views.order_save, name="save"),
    path("orders/<int:pk>/view/", views.order_view, name="view"),
    path("orders/<int:pk>/receipt/", views.receipt, name="receipt"),
    path("orders/<int:pk>/delete/", views.order_delete, name="delete"),
    path("orders/<int:pk>/void/", views.order_void, name="void"),
]
