from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from orders import services

from .models import Category, Product


class MenuTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("boss", password="x-Strong-pass-1", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user("cashier", password="x-Strong-pass-1")
        cls.cat = Category.objects.create(name="Coffee")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_staff_cannot_manage_menu(self):
        self.client.force_login(self.staff)
        for url in (reverse("menu:categories"), reverse("menu:products")):
            self.assertEqual(self.client.get(url).status_code, 403)
        r = self.client.post(reverse("menu:category_save"), {"name": "Hack"})
        self.assertEqual(r.status_code, 403)

    def test_create_and_update_category(self):
        r = self.client.post(reverse("menu:category_save"), {"name": "  Fresh   Juice ", "description": "Cold"})
        self.assertEqual(r.status_code, 200)
        cat = Category.objects.get(name="Fresh Juice")
        r = self.client.post(reverse("menu:category_save"), {"id": cat.pk, "name": "Juices", "description": ""})
        self.assertEqual(r.status_code, 200)
        cat.refresh_from_db()
        self.assertEqual(cat.name, "Juices")

    def test_category_names_unique_ignoring_case(self):
        r = self.client.post(reverse("menu:category_save"), {"name": "coffee"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("already exists", str(r.json()["errors"]))

    def test_category_with_products_cannot_be_deleted(self):
        Product.objects.create(category=self.cat, name="Latte", price=10)
        r = self.client.post(reverse("menu:category_delete", args=[self.cat.pk]))
        self.assertEqual(r.status_code, 400)
        self.assertTrue(Category.objects.filter(pk=self.cat.pk).exists())

    def test_product_validation(self):
        r = self.client.post(reverse("menu:product_save"), {"category": self.cat.pk, "name": "Mocha", "price": "-1"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("price", r.json()["errors"])
        r = self.client.post(reverse("menu:product_save"), {"category": self.cat.pk, "name": "Mocha", "price": "170.50", "is_available": "on"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Product.objects.get(name="Mocha").price, Decimal("170.50"))

    def test_unchecked_available_switch_marks_unavailable(self):
        p = Product.objects.create(category=self.cat, name="Latte", price=10)
        self.client.post(reverse("menu:product_save"), {"id": p.pk, "category": self.cat.pk, "name": "Latte", "price": "10"})
        p.refresh_from_db()
        self.assertFalse(p.is_available)

    def test_product_on_an_order_cannot_be_deleted(self):
        p = Product.objects.create(category=self.cat, name="Latte", price=10)
        services.save_order(user=self.admin, order_number=1, lines=[{"product_id": p.pk, "qty": 1}])
        r = self.client.post(reverse("menu:product_delete", args=[p.pk]))
        self.assertEqual(r.status_code, 400)
        self.assertIn("Mark it unavailable", r.json()["error"])
