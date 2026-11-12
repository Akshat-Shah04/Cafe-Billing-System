from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from core.http import error, form_errors, ok

from .decorators import admin_required
from .forms import AccountForm, UserForm
from .models import User


@admin_required
@require_GET
def user_list(request):
    return render(request, "accounts/users.html", {"users": User.objects.filter(is_active=True), "page": "users"})


@admin_required
@require_GET
def user_form(request):
    user = get_object_or_404(User, pk=request.GET["id"], is_active=True) if request.GET.get("id") else None
    form = UserForm(instance=user, acting_user=request.user)
    return render(request, "accounts/_user_form.html", {"form": form, "edit_user": user})


@admin_required
@require_POST
def user_save(request):
    user = get_object_or_404(User, pk=request.POST["id"], is_active=True) if request.POST.get("id") else None
    form = UserForm(request.POST, instance=user, acting_user=request.user)
    if not form.is_valid():
        return form_errors(form)
    saved = form.save()
    if saved.pk == request.user.pk:
        update_session_auth_hash(request, saved)
    return ok(id=saved.pk)


@admin_required
@require_POST
def user_delete(request, pk):
    user = get_object_or_404(User, pk=pk, is_active=True)
    if user.pk == request.user.pk:
        return error("You cannot delete your own account.")
    if user.is_admin and not User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=pk).exists():
        return error("There must be at least one admin.")
    # Deactivate rather than delete: orders keep pointing at the person who took them.
    user.is_active = False
    user.username = f"{user.username}__removed_{user.pk}"
    user.set_unusable_password()
    user.save()
    return ok()


@login_required
@require_GET
def account_form(request):
    return render(request, "accounts/_account_form.html", {"form": AccountForm(instance=request.user)})


@login_required
@require_POST
def account_save(request):
    form = AccountForm(request.POST, instance=request.user)
    if not form.is_valid():
        return form_errors(form)
    user = form.save()
    update_session_auth_hash(request, user)
    return ok()
