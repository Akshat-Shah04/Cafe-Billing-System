import json
import threading
from decimal import Decimal

from django.db import connection
from django.test import TestCase, TransactionTestCase
from django.urls import reverse

from accounts.models import User
from menu.models import Category, Product

from . import services
from .models import Order


class OrderTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("boss", password="x-Strong-pass-1", full_name="Boss", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user("cashier", password="x-Strong-pass-1", full_name="Cashier")
        cat = Category.objects.create(name="Coffee")
        cls.latte = Product.objects.create(category=cat, name="Latte", price=Decimal("150.00"))
        cls.tea = Product.objects.create(category=cat, name="Tea", price=Decimal("40.50"))
        cls.off = Product.objects.create(category=cat, name="Seasonal", price=Decimal("99.00"), is_available=False)

    def save(self, user=None, **kw):
        kw.setdefault("order_number", 1)
        kw.setdefault("lines", [{"product_id": self.latte.pk, "qty": 2}, {"product_id": self.tea.pk, "qty": 1}])
        return services.save_order(user=user or self.staff, **kw)


class SaveOrderTests(OrderTestBase):
    def test_pay_later_creates_unpaid_order_with_server_side_total(self):
        order = self.save()
        self.assertEqual(order.status, Order.Status.OPEN)
        self.assertEqual(order.total_amount, Decimal("340.50"))
        self.assertIsNone(order.invoice_no)
        self.assertEqual(order.items.count(), 2)

    def test_pay_now_assigns_invoice_and_change(self):
        order = self.save(tendered="500")
        self.assertEqual(order.status, Order.Status.PAID)
        self.assertEqual(order.change, Decimal("159.50"))
        self.assertRegex(order.invoice_no, r"^INV-\d{4}-000001$")
        self.assertEqual(order.paid_by, self.staff)

    def test_invoice_numbers_are_sequential(self):
        first = self.save(tendered="1000")
        second = self.save(order_number=2, tendered="1000")
        self.save(order_number=3)  # unpaid: takes no number
        third = self.save(order_number=4, tendered="1000")
        nums = [int(o.invoice_no.rsplit("-", 1)[1]) for o in (first, second, third)]
        self.assertEqual(nums, [1, 2, 3])

    def test_tendered_less_than_total_is_rejected(self):
        with self.assertRaisesMessage(services.OrderError, "less than the amount payable"):
            self.save(tendered="100")
        self.assertFalse(Order.objects.exists())

    def test_client_cannot_set_price(self):
        order = self.save(lines=[{"product_id": self.latte.pk, "qty": 1, "price": "1", "amount": "1"}])
        self.assertEqual(order.total_amount, Decimal("150.00"))

    def test_duplicate_lines_are_merged(self):
        order = self.save(lines=[{"product_id": self.tea.pk, "qty": 1}, {"product_id": self.tea.pk, "qty": 2}])
        self.assertEqual(order.items.get().qty, 3)

    def test_unavailable_product_cannot_be_added(self):
        with self.assertRaisesMessage(services.OrderError, "not available"):
            self.save(lines=[{"product_id": self.off.pk, "qty": 1}])

    def test_validation(self):
        for bad in ([], [{"product_id": self.tea.pk, "qty": 0}], [{"product_id": self.tea.pk, "qty": 1000}], [{"qty": 1}], "x"):
            with self.subTest(lines=bad), self.assertRaises(services.OrderError):
                self.save(lines=bad)
        for bad in (None, "", 0, 10000, "abc"):
            with self.subTest(order_number=bad), self.assertRaises(services.OrderError):
                self.save(order_number=bad)
        for bad in ("-5", "abc", "1e99", "NaN"):
            with self.subTest(tendered=bad), self.assertRaises(services.OrderError):
                self.save(tendered=bad)

    def test_editing_unpaid_order_keeps_original_prices(self):
        order = self.save(lines=[{"product_id": self.latte.pk, "qty": 1}])
        Product.objects.filter(pk=self.latte.pk).update(price=Decimal("999.00"), name="Latte (new)")
        order = self.save(order_id=order.pk, lines=[{"product_id": self.latte.pk, "qty": 2}, {"product_id": self.tea.pk, "qty": 1}])
        latte_line = order.items.get(product=self.latte)
        self.assertEqual(latte_line.unit_price, Decimal("150.00"))
        self.assertEqual(latte_line.product_name, "Latte")
        self.assertEqual(order.total_amount, Decimal("340.50"))

    def test_bill_out_saved_order(self):
        order = self.save()
        paid = self.save(order_id=order.pk, tendered="340.50")
        self.assertEqual(paid.pk, order.pk)
        self.assertEqual(paid.status, Order.Status.PAID)
        self.assertEqual(paid.change, Decimal("0.00"))

    def test_paid_order_is_locked(self):
        order = self.save(tendered="500")
        with self.assertRaisesMessage(services.OrderError, "can no longer be changed"):
            self.save(order_id=order.pk)
        with self.assertRaisesMessage(services.OrderError, "cannot be deleted"):
            services.delete_order(order.pk)

    def test_void_only_paid_orders_with_reason(self):
        open_order = self.save()
        with self.assertRaises(services.OrderError):
            services.void_order(user=self.admin, order_id=open_order.pk, reason="mistake")
        paid = self.save(order_number=2, tendered="500")
        with self.assertRaises(services.OrderError):
            services.void_order(user=self.admin, order_id=paid.pk, reason="")
        voided = services.void_order(user=self.admin, order_id=paid.pk, reason="Customer cancelled")
        self.assertEqual(voided.status, Order.Status.VOID)
        self.assertEqual(voided.invoice_no, paid.invoice_no)

    def test_suggested_order_number_counts_up(self):
        self.assertEqual(services.suggest_order_number(), 1)
        self.save(order_number=7)
        self.assertEqual(services.suggest_order_number(), 8)


class OrderViewTests(OrderTestBase):
    def post_json(self, data):
        return self.client.post(reverse("orders:save"), json.dumps(data), content_type="application/json")

    def test_login_required(self):
        for url in (reverse("orders:list"), reverse("orders:pos"), reverse("core:dashboard")):
            self.assertEqual(self.client.get(url).status_code, 302)
        self.assertEqual(self.post_json({}).status_code, 302)

    def test_save_endpoint(self):
        self.client.force_login(self.staff)
        r = self.post_json({"order_number": 5, "items": [{"product_id": self.tea.pk, "qty": 2}], "tendered": "100"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["status"], "paid")
        self.assertEqual(body["change"], "19.00")
        r = self.client.get(body["receipt_url"])
        self.assertContains(r, body["invoice_no"])
        self.assertContains(r, "Tea")

    def test_save_endpoint_errors(self):
        self.client.force_login(self.staff)
        r = self.client.post(reverse("orders:save"), "not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.post_json({"order_number": 5, "items": []})
        self.assertEqual(r.status_code, 400)
        self.assertIn("at least 1 product", r.json()["error"])

    def test_csrf_enforced(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.staff)
        r = client.post(reverse("orders:save"), json.dumps({}), content_type="application/json")
        self.assertEqual(r.status_code, 403)

    def test_staff_cannot_void(self):
        order = self.save(tendered="500")
        self.client.force_login(self.staff)
        r = self.client.post(reverse("orders:void", args=[order.pk]), {"reason": "test"})
        self.assertEqual(r.status_code, 403)
        self.client.force_login(self.admin)
        r = self.client.post(reverse("orders:void", args=[order.pk]), {"reason": "Wrong order"})
        self.assertEqual(r.status_code, 200)

    def test_pos_redirects_for_paid_order(self):
        order = self.save(tendered="500")
        self.client.force_login(self.staff)
        r = self.client.get(reverse("orders:pos_edit", args=[order.pk]))
        self.assertRedirects(r, reverse("orders:list"))

    def test_pos_page_lists_only_available_products(self):
        self.client.force_login(self.staff)
        r = self.client.get(reverse("orders:pos"))
        self.assertContains(r, "Latte")
        self.assertNotContains(r, "Seasonal")

    def test_product_name_is_escaped(self):
        Product.objects.create(category=self.latte.category, name="<script>alert(1)</script>", price=1)
        self.client.force_login(self.staff)
        r = self.client.get(reverse("orders:pos"))
        self.assertNotContains(r, "<script>alert(1)</script>")


class ConcurrentPaymentTests(TransactionTestCase):
    """Two tills paying at the same moment must get different, consecutive invoice numbers."""

    def test_parallel_payments_get_unique_numbers(self):
        user = User.objects.create_user("till", password="x-Strong-pass-1")
        cat = Category.objects.create(name="Coffee")
        product = Product.objects.create(category=cat, name="Latte", price=Decimal("10.00"))
        results, errors = [], []

        def pay(n):
            try:
                order = services.save_order(
                    user=user, order_number=n, lines=[{"product_id": product.pk, "qty": 1}], tendered="10"
                )
                results.append(order.invoice_no)
            except Exception as e:  # pragma: no cover - reported below
                errors.append(e)
            finally:
                connection.close()

        threads = [threading.Thread(target=pay, args=(n,)) for n in range(1, 9)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        numbers = sorted(int(no.rsplit("-", 1)[1]) for no in results)
        self.assertEqual(numbers, list(range(1, 9)))
