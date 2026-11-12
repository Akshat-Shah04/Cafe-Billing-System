from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q


class Order(models.Model):
    """A customer's order.

    An order starts OPEN (the "pay later" case from the original system), becomes PAID when the
    cashier takes the money, and a paid order can only be VOIDED by an admin, never edited or
    deleted, so the sales report always matches the receipts that were handed out.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Unpaid"
        PAID = "paid", "Paid"
        VOID = "void", "Voided"

    order_number = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(9999)],
        help_text="The queue number called out to the customer.",
    )
    status = models.CharField(max_length=4, choices=Status.choices, default=Status.OPEN, db_index=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    amount_tendered = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    # Assigned only when an order is paid: gap-free per calendar year, e.g. INV-2026-000042.
    invoice_no = models.CharField(max_length=20, unique=True, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    voided_at = models.DateTimeField(null=True, blank=True)
    void_reason = models.CharField(max_length=200, blank=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "paid_at"])]
        constraints = [
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="order_total_not_negative"),
            # A paid order always has an invoice number and enough money tendered.
            models.CheckConstraint(
                condition=~Q(status="paid")
                | (Q(invoice_no__isnull=False) & Q(paid_at__isnull=False) & Q(amount_tendered__gte=F("total_amount"))),
                name="order_paid_is_complete",
            ),
        ]

    @property
    def change(self) -> Decimal:
        if self.amount_tendered is None:
            return Decimal("0.00")
        return self.amount_tendered - self.total_amount

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN

    def __str__(self) -> str:
        return self.invoice_no or f"Order #{self.order_number}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey("menu.Product", on_delete=models.PROTECT, related_name="order_items")
    # Snapshots: renaming or repricing a product later never changes an old receipt.
    product_name = models.CharField(max_length=120)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    qty = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(999)])
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="orderitem_one_line_per_product"),
            models.CheckConstraint(condition=Q(qty__gte=1), name="orderitem_qty_positive"),
            models.CheckConstraint(condition=Q(line_total=F("unit_price") * F("qty")), name="orderitem_total_matches"),
        ]

    def __str__(self) -> str:
        return f"{self.qty} x {self.product_name}"


class InvoiceSequence(models.Model):
    """Last invoice number used in each year. Rows are locked while numbering, so two tills
    paying at the same moment can never get the same number or leave a gap."""

    year = models.PositiveIntegerField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)
