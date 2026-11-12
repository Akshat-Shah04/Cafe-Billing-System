from django.db.models import Count, ProtectedError
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import admin_required
from core.http import error, form_errors, ok

from .forms import CategoryForm, ProductForm
from .models import Category, Product


@admin_required
@require_GET
def category_list(request):
    categories = Category.objects.annotate(product_count=Count("products")).order_by("name")
    return render(request, "menu/categories.html", {"categories": categories, "page": "categories"})


@admin_required
@require_POST
def category_save(request):
    category = get_object_or_404(Category, pk=request.POST["id"]) if request.POST.get("id") else None
    form = CategoryForm(request.POST, instance=category)
    if not form.is_valid():
        return form_errors(form)
    form.save()
    return ok(created=category is None)


@admin_required
@require_POST
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    try:
        category.delete()
    except ProtectedError:
        return error("This category still has products. Move or delete them first.")
    return ok()


@admin_required
@require_GET
def product_list(request):
    products = Product.objects.select_related("category").order_by("category__name", "name")
    categories = Category.objects.order_by("name")
    return render(request, "menu/products.html", {"products": products, "categories": categories, "page": "products"})


@admin_required
@require_POST
def product_save(request):
    product = get_object_or_404(Product, pk=request.POST["id"]) if request.POST.get("id") else None
    form = ProductForm(request.POST, instance=product)
    if not form.is_valid():
        return form_errors(form)
    form.save()
    return ok(created=product is None)


@admin_required
@require_POST
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    try:
        product.delete()
    except ProtectedError:
        return error("This product is on past orders, so it cannot be deleted. Mark it unavailable instead.")
    return ok()
