import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import admin_required
from core.http import error, ok
from menu.models import Category, Product

from . import services
from .models import Order


@login_required
@require_GET
def order_list(request):
    orders = Order.objects.select_related("created_by").order_by("-created_at")
    return render(request, "orders/orders.html", {"orders": orders, "page": "orders"})


@login_required
@require_GET
def pos(request, pk=None):
    """The "Take Orders" screen. With an id, it reopens an unpaid order to add to it or bill it out."""
    order = None
    lines = []
    if pk is not None:
        order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
        if not order.is_open:
            return redirect("orders:list")
        lines = [
            {"product_id": i.product_id, "name": i.product_name, "price": str(i.unit_price), "qty": i.qty}
            for i in order.items.all()
        ]
    products = [
        {"id": p.id, "name": p.name, "price": str(p.price), "category_id": p.category_id}
        for p in Product.objects.filter(is_available=True).order_by("name")
    ]
    return render(
        request,
        "orders/pos.html",
        {
            "order": order,
            "categories": Category.objects.order_by("name"),
            "products": products,
            "lines": lines,
            "suggested_number": order.order_number if order else services.suggest_order_number(),
        },
    )


@login_required
@require_POST
def order_save(request):
    try:
        payload = json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return error("The request was not valid.")
    if not isinstance(payload, dict):
        return error("The request was not valid.")
    try:
        order = services.save_order(
            user=request.user,
            order_id=payload.get("id") or None,
            order_number=payload.get("order_number"),
            lines=payload.get("items"),
            tendered=payload.get("tendered"),
        )
    except services.OrderError as e:
        return error(str(e))
    return ok(
        id=order.pk,
        status=order.status,
        invoice_no=order.invoice_no,
        total=str(order.total_amount),
        change=str(order.change),
        receipt_url=reverse("orders:receipt", args=[order.pk]),
    )


@login_required
@require_GET
def order_view(request, pk):
    order = get_object_or_404(
        Order.objects.prefetch_related("items").select_related("created_by", "paid_by", "voided_by"), pk=pk
    )
    return render(request, "orders/_view_order.html", {"order": order})


@login_required
@require_GET
def receipt(request, pk):
    order = get_object_or_404(Order.objects.prefetch_related("items"), pk=pk)
    return render(request, "orders/receipt.html", {"order": order, "autoprint": request.GET.get("print") == "1"})


@login_required
@require_POST
def order_delete(request, pk):
    try:
        services.delete_order(pk)
    except services.OrderError as e:
        return error(str(e))
    return ok()


@admin_required
@require_POST
def order_void(request, pk):
    try:
        services.void_order(user=request.user, order_id=pk, reason=request.POST.get("reason", ""))
    except services.OrderError as e:
        return error(str(e))
    return ok()
