from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """A till user. Admins manage the menu, users and settings; staff take orders."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        STAFF = "staff", "Staff"

    full_name = models.CharField(max_length=150)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.STAFF)

    class Meta:
        ordering = ["full_name"]
        constraints = [
            models.UniqueConstraint(
                Lower("username"), name="user_username_ci_unique",
                violation_error_message="Username already exists.",
            ),
        ]

    def save(self, *args, **kwargs):
        self.username = self.username.strip().lower()
        if self.is_superuser:
            self.role = self.Role.ADMIN
        if not self.full_name:
            self.full_name = self.get_full_name() or self.username
        super().save(*args, **kwargs)

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    def __str__(self) -> str:
        return self.full_name or self.username
