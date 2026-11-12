"""Loads a sample cafe menu so a fresh install has something to click on.

    python manage.py seed_demo                # menu only
    python manage.py seed_demo --admin admin  # also create an admin (asks for the password)
"""

import getpass
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import User
from core.models import SiteSettings
from menu.models import Category, Product

MENU = {
    "Coffee": [("Espresso", "90"), ("Cappuccino", "140"), ("Cafe Latte", "150"), ("Cold Coffee", "160")],
    "Tea": [("Masala Chai", "40"), ("Green Tea", "60"), ("Iced Lemon Tea", "90")],
    "Snacks": [("Veg Sandwich", "110"), ("Cheese Garlic Bread", "130"), ("French Fries", "100"), ("Paneer Wrap", "150")],
    "Meals": [("Veg Thali", "220"), ("Pav Bhaji", "160"), ("Veg Biryani", "190")],
    "Desserts": [("Chocolate Brownie", "120"), ("Blueberry Cheesecake", "180")],
}


class Command(BaseCommand):
    help = "Create a sample menu (and optionally an admin user)."

    def add_arguments(self, parser):
        parser.add_argument("--admin", metavar="USERNAME", help="Also create an admin with this username.")
        parser.add_argument("--password", help="Admin password (asked for if left out).")

    @transaction.atomic
    def handle(self, *args, **opts):
        settings_obj = SiteSettings.load()
        if settings_obj.name == "Cafe Billing System":
            settings_obj.name = "Brew & Bite Cafe"
            settings_obj.address = "Ahmedabad, Gujarat"
            settings_obj.save()

        created = 0
        for cat_name, items in MENU.items():
            category, _ = Category.objects.get_or_create(name=cat_name, defaults={"description": f"{cat_name} menu"})
            for name, price in items:
                _, new = Product.objects.get_or_create(
                    name=name, defaults={"category": category, "price": Decimal(price), "description": name}
                )
                created += new
        self.stdout.write(self.style.SUCCESS(f"Menu ready ({created} new products)."))

        if opts["admin"]:
            username = opts["admin"].strip().lower()
            if User.objects.filter(username=username).exists():
                raise CommandError(f'User "{username}" already exists.')
            password = opts["password"] or getpass.getpass("Password for the admin: ")
            User.objects.create_user(username=username, password=password, full_name="Administrator", role=User.Role.ADMIN)
            self.stdout.write(self.style.SUCCESS(f'Admin "{username}" created.'))
