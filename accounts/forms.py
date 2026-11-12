from django import forms
from django.contrib.auth import password_validation

from .models import User


class UserForm(forms.ModelForm):
    """Admin creating or editing any user. The password is optional when editing."""

    password = forms.CharField(widget=forms.PasswordInput, required=False, strip=False)

    class Meta:
        model = User
        fields = ["full_name", "username", "role"]

    def __init__(self, *args, acting_user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.acting_user = acting_user
        if self.instance.pk is None:
            self.fields["password"].required = True

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def clean_role(self):
        role = self.cleaned_data["role"]
        if self.instance.pk and self.instance.is_admin and role != User.Role.ADMIN:
            if self.instance.pk == getattr(self.acting_user, "pk", None):
                raise forms.ValidationError("You cannot remove your own admin role.")
            if not User.objects.filter(role=User.Role.ADMIN, is_active=True).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("There must be at least one admin.")
        return role

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            candidate = User(username=cleaned.get("username", ""), full_name=cleaned.get("full_name", ""))
            try:
                password_validation.validate_password(password, candidate)
            except forms.ValidationError as e:
                self.add_error("password", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("password"):
            user.set_password(self.cleaned_data["password"])
        if commit:
            user.save()
        return user


class AccountForm(forms.ModelForm):
    """A user editing their own name, username and password."""

    current_password = forms.CharField(widget=forms.PasswordInput, required=False, strip=False)
    new_password = forms.CharField(widget=forms.PasswordInput, required=False, strip=False)

    class Meta:
        model = User
        fields = ["full_name", "username"]

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()

    def clean(self):
        cleaned = super().clean()
        new = cleaned.get("new_password")
        if new:
            if not self.instance.check_password(cleaned.get("current_password") or ""):
                self.add_error("current_password", "Your current password is not correct.")
            else:
                try:
                    password_validation.validate_password(new, self.instance)
                except forms.ValidationError as e:
                    self.add_error("new_password", e)
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        if self.cleaned_data.get("new_password"):
            user.set_password(self.cleaned_data["new_password"])
        if commit:
            user.save()
        return user
