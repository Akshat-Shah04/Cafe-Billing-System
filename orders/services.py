"""Order business rules. Views stay thin and call these; all money maths happens here, on the
server, from prices in the database. Nothing the browser sends about prices or totals is used."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from menu.models import Product

from .models import InvoiceSequence, Order, OrderItem

MAX_LINES = 100
MAX_QTY = 999
MAX_TENDERED = Decimal("9999999.99")


class OrderError(Exception):
    """A rule was broken; the message is safe to show to the cashier."""


@dataclass(frozen=True)
class LineInput:
    product_id: int
    qty: int


def parse_lines(raw) -> list[LineInput]:
    if not isinstance(raw, list) or not raw:
        raise OrderError("Please add at least 1 product first.")
    if len(raw) > MAX_LINES:
        raise OrderError(f"An order can have at most {MAX_LINES} different products.")
    merged: dict[int, int] = {}
    for item in raw:
        try:
            product_id = int(item["product_id"])
            qty = int(item["qty"])
        except (KeyError, TypeError, ValueError):
            raise OrderError("An order line is not valid.") from None
        if qty < 1 or qty > MAX_QTY:
            raise OrderError(f"Quantity must be between 1 and {MAX_QTY}.")
        merged[product_id] = merged.get(product_id, 0) + qty
    if any(q > MAX_QTY for q in merged.values()):
        raise OrderError(f"Quantity must be between 1 and {MAX_QTY}.")
    return [LineInput(pid, q) for pid, q in merged.items()]


def parse_money(raw) -> Decimal | None:
    if raw in (None, ""):
        return None
    try:
        value = Decimal(str(raw).replace(",", "").strip())
    except InvalidOperation:
        raise OrderError("Amount tendered is not a valid amount.") from None
    if not value.is_finite() or value < 0 or value > MAX_TENDERED:
        raise OrderError("Amount tendered is not a valid amount.")
    return value.quantize(Decimal("0.01"))


def parse_order_number(raw) -> int:
    try:
        number = int(raw)
    except (TypeError, ValueError):
        raise OrderError("Order No. is required.") from None
    if not 1 <= number <= 9999:
        raise OrderError("Order No. must be between 1 and 9999.")
    return number


def suggest_order_number() -> int:
    """Next queue number for today, restarting at 1 each day (the till's local date)."""
    start = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    last = Order.objects.filter(created_at__gte=start).aggregate(m=Max("order_number"))["m"] or 0
    return last % 9999 + 1


def next_invoice_no(when) -> str:
    """Must be called inside a transaction."""
    year = timezone.localtime(when).year
    # INSERT ... ON CONFLICT DO NOTHING, so two tills starting a new year at once cannot collide.
    InvoiceSequence.objects.bulk_create([InvoiceSequence(year=year)], ignore_conflicts=True)
    seq = InvoiceSequence.objects.select_for_update().get(year=year)
    seq.last_number += 1
    seq.save(update_fields=["last_number"])
    return f"INV-{year}-{seq.last_number:06d}"


@transaction.atomic
def save_order(*, user, order_id=None, order_number, lines, tendered=None) -> Order:
    """Create or update an unpaid order, and pay it if money was tendered.

    Mirrors the till's two buttons: "Pay later" sends no tendered amount and leaves the order
    unpaid; "Pay" sends the amount the customer handed over, which must cover the total.
    """
    number = parse_order_number(order_number)
    items = parse_lines(lines)
    tendered = parse_money(tendered)

    if order_id:
        order = Order.objects.select_for_update().filter(pk=order_id).first()
        if order is None:
            raise OrderError("This order no longer exists.")
        if not order.is_open:
            raise OrderError("This order is already paid or voided and can no longer be changed.")
    else:
        order = Order(created_by=user)

    existing = {} if order.pk is None else {i.product_id: i for i in order.items.all()}
    products = Product.objects.in_bulk([i.product_id for i in items])

    new_lines: list[OrderItem] = []
    for item in items:
        product = products.get(item.product_id)
        if product is None:
            raise OrderError("A product on this order no longer exists.")
        kept = existing.get(product.pk)
        if kept is None and not product.is_available:
            raise OrderError(f"{product.name} is not available right now.")
        # A line already on an unpaid order keeps the price it was ordered at.
        unit_price = kept.unit_price if kept else product.price
        new_lines.append(
            OrderItem(
                product=product,
                product_name=kept.product_name if kept else product.name,
                unit_price=unit_price,
                qty=item.qty,
                line_total=unit_price * item.qty,
            )
        )

    order.order_number = number
    order.total_amount = sum((line.line_total for line in new_lines), Decimal("0.00"))

    if tendered is not None:
        if tendered < order.total_amount:
            raise OrderError("Amount tendered is less than the amount payable.")
        now = timezone.now()
        order.status = Order.Status.PAID
        order.amount_tendered = tendered
        order.paid_at = now
        order.paid_by = user
        order.invoice_no = next_invoice_no(now)

    order.save()
    order.items.all().delete()
    for line in new_lines:
        line.order = order
    OrderItem.objects.bulk_create(new_lines)
    return order


@transaction.atomic
def delete_order(order_id) -> None:
    order = Order.objects.select_for_update().filter(pk=order_id).first()
    if order is None:
        raise OrderError("This order no longer exists.")
    if not order.is_open:
        raise OrderError("Paid orders cannot be deleted. An admin can void it instead.")
    order.delete()


@transaction.atomic
def void_order(*, user, order_id, reason: str) -> Order:
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise OrderError("Please give a reason (at least 3 characters).")
    order = Order.objects.select_for_update().filter(pk=order_id).first()
    if order is None:
        raise OrderError("This order no longer exists.")
    if order.status != Order.Status.PAID:
        raise OrderError("Only paid orders can be voided. Unpaid orders can simply be deleted.")
    order.status = Order.Status.VOID
    order.voided_at = timezone.now()
    order.voided_by = user
    order.void_reason = reason[:200]
    order.save(update_fields=["status", "voided_at", "voided_by", "void_reason", "updated_at"])
    return order
