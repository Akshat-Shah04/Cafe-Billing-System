from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from menu.models import Category, Product
from orders import services
from orders.models import Order

from .models import SiteSettings


class SalesReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("boss", password="x-Strong-pass-1", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user("cashier", password="x-Strong-pass-1")
        cat = Category.objects.create(name="Coffee")
        cls.latte = Product.objects.create(category=cat, name="Latte", price=Decimal("150.00"))

    def order(self, qty, tendered="10000"):
        return services.save_order(
            user=self.staff, order_number=1, lines=[{"product_id": self.latte.pk, "qty": qty}], tendered=tendered
        )

    def test_report_counts_paid_orders_in_month_only(self):
        self.order(1)
        self.order(2)
        services.save_order(user=self.staff, order_number=3, lines=[{"product_id": self.latte.pk, "qty": 5}])  # unpaid
        voided = self.order(4)
        services.void_order(user=self.admin, order_id=voided.pk, reason="Mistake")
        old = self.order(10)
        Order.objects.filter(pk=old.pk).update(paid_at=timezone.now() - timedelta(days=62))

        self.client.force_login(self.staff)
        r = self.client.get(reverse("core:sales_report"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["count"], 2)
        self.assertEqual(r.context["total"], Decimal("450.00"))
        self.assertEqual(r.context["top_products"][0]["qty"], 3)

    def test_csv_export(self):
        paid = self.order(2)
        self.client.force_login(self.staff)
        r = self.client.get(reverse("core:sales_report_csv"), {"month": timezone.localdate().strftime("%Y-%m")})
        self.assertEqual(r["Content-Type"], "text/csv; charset=utf-8")
        body = r.content.decode("utf-8-sig")
        self.assertIn(paid.invoice_no, body)
        self.assertIn("300.00", body)

    def test_bad_month_falls_back_to_current(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("core:sales_report"), {"month": "garbage"})
        self.assertEqual(r.context["month"], timezone.localdate().replace(day=1))

    def test_dashboard(self):
        self.order(2)
        self.client.force_login(self.staff)
        r = self.client.get(reverse("core:dashboard"))
        self.assertEqual(r.context["today_total"], Decimal("300.00"))
        self.assertEqual(r.context["today_count"], 1)


class SettingsTests(TestCase):
    def test_only_admin_can_change_settings(self):
        staff = User.objects.create_user("cashier", password="x-Strong-pass-1")
        admin = User.objects.create_user("boss", password="x-Strong-pass-1", role=User.Role.ADMIN)
        self.client.force_login(staff)
        self.assertEqual(self.client.post(reverse("core:settings"), {"name": "Hacked"}).status_code, 403)
        self.client.force_login(admin)
        r = self.client.post(reverse("core:settings"), {"name": "Brew Cafe", "currency_symbol": "Rs", "receipt_footer": "Bye"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(SiteSettings.load().name, "Brew Cafe")
        self.assertEqual(SiteSettings.objects.count(), 1)
