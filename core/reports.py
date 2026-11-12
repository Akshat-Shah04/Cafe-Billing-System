"""Sales figures, computed in the database rather than by looping over rows in Python."""

from datetime import date, datetime, time, timedelta

from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from orders.models import Order, OrderItem


def _aware(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min), timezone.get_current_timezone())


def day_bounds(day: date):
    return _aware(day), _aware(day + timedelta(days=1))


def month_bounds(month: date):
    first = month.replace(day=1)
    nxt = date(first.year + (first.month == 12), first.month % 12 + 1, 1)
    return _aware(first), _aware(nxt)


def parse_month(raw: str | None) -> date:
    try:
        return datetime.strptime(raw or "", "%Y-%m").date()
    except ValueError:
        return timezone.localdate().replace(day=1)


def paid_orders(start, end):
    """Sales are counted on the day the money was taken, and voided orders are left out."""
    return Order.objects.filter(status=Order.Status.PAID, paid_at__gte=start, paid_at__lt=end)


def sales_summary(start, end):
    orders = paid_orders(start, end)
    totals = orders.aggregate(total=Sum("total_amount"), count=Count("id"))
    daily = (
        orders.annotate(day=TruncDate("paid_at", tzinfo=timezone.get_current_timezone()))
        .values("day")
        .annotate(total=Sum("total_amount"), count=Count("id"))
        .order_by("day")
    )
    top_products = (
        OrderItem.objects.filter(order__in=orders)
        .values("product_name")
        .annotate(qty=Sum("qty"), amount=Sum("line_total"))
        .order_by("-amount", "product_name")[:5]
    )
    return {
        "orders": orders.order_by("paid_at"),
        "total": totals["total"] or 0,
        "count": totals["count"],
        "daily": list(daily),
        "top_products": list(top_products),
    }
