from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class Category(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [models.UniqueConstraint(
                Lower("name"), name="category_name_ci_unique",
                violation_error_message="A category with this name already exists.",
            )]

    def __str__(self) -> str:
        return self.name


class Product(models.Model):
    # PROTECT: a category that still has products cannot be deleted by accident.
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"), name="product_name_ci_unique",
                violation_error_message="A product with this name already exists.",
            ),
            models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_not_negative"),
        ]
        indexes = [models.Index(fields=["is_available", "name"])]

    def __str__(self) -> str:
        return self.name
