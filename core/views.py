import csv

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from accounts.decorators import admin_required
from core.http import form_errors, ok
from orders.models import Order

from .forms import SiteSettingsForm
from .models import SiteSettings
from .reports import day_bounds, month_bounds, parse_month, sales_summary


@login_required
@require_GET
def dashboard(request):
    today = timezone.localdate()
    today_summary = sales_summary(*day_bounds(today))
    month_summary = sales_summary(*month_bounds(today))
    context = {
        "page": "home",
        "today_total": today_summary["total"],
        "today_count": today_summary["count"],
        "month_total": month_summary["total"],
        "unpaid_count": Order.objects.filter(status=Order.Status.OPEN).count(),
        "top_products": month_summary["top_products"],
        "recent_orders": Order.objects.order_by("-created_at")[:5],
    }
    return render(request, "core/dashboard.html", context)


@login_required
@require_GET
def sales_report(request):
    month = parse_month(request.GET.get("month"))
    summary = sales_summary(*month_bounds(month))
    return render(request, "core/sales_report.html", {"page": "sales_report", "month": month, **summary})


@login_required
@require_GET
def sales_report_csv(request):
    month = parse_month(request.GET.get("month"))
    summary = sales_summary(*month_bounds(month))
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="sales-%s.csv"' % month.strftime("%Y-%m")
    response.write("﻿")  # so Excel opens it as UTF-8
    writer = csv.writer(response)
    writer.writerow(["#", "Date paid", "Invoice", "Order Number", "Amount"])
    for i, order in enumerate(summary["orders"], start=1):
        paid = timezone.localtime(order.paid_at).strftime("%Y-%m-%d %H:%M")
        writer.writerow([i, paid, order.invoice_no, order.order_number, order.total_amount])
    writer.writerow(["", "", "", "Total", summary["total"]])
    return response


@admin_required
@require_http_methods(["GET", "POST"])
def site_settings(request):
    settings_obj = SiteSettings.load()
    if request.method == "POST":
        form = SiteSettingsForm(request.POST, instance=settings_obj)
        if not form.is_valid():
            return form_errors(form)
        form.save()
        return ok()
    form = SiteSettingsForm(instance=settings_obj)
    return render(request, "core/settings.html", {"page": "site_settings", "form": form})
