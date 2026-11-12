from django.test import TestCase
from django.urls import reverse

from .models import User

PW = "x-Strong-pass-1"


class AuthTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("boss", password=PW, full_name="Boss", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user("cashier", password=PW, full_name="Cashier")

    def test_login_and_logout(self):
        r = self.client.post(reverse("accounts:login"), {"username": "cashier", "password": PW})
        self.assertRedirects(r, reverse("core:dashboard"))
        r = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(r, reverse("accounts:login"))

    def test_wrong_password(self):
        r = self.client.post(reverse("accounts:login"), {"username": "cashier", "password": "nope"})
        self.assertContains(r, "Username or password is incorrect")

    def test_passwords_are_hashed(self):
        self.assertTrue(self.staff.password.startswith("pbkdf2_sha256$"))

    def test_username_is_case_insensitive(self):
        self.client.force_login(self.admin)
        r = self.client.post(reverse("accounts:user_save"), {"full_name": "X", "username": "CASHIER", "password": PW, "role": "staff"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("username", r.json()["errors"])


class UserManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user("boss", password=PW, full_name="Boss", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user("cashier", password=PW, full_name="Cashier")

    def setUp(self):
        self.client.force_login(self.admin)

    def test_staff_cannot_manage_users(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("accounts:users")).status_code, 403)
        r = self.client.post(reverse("accounts:user_save"), {"id": self.staff.pk, "full_name": "C", "username": "cashier", "role": "admin"})
        self.assertEqual(r.status_code, 403)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_admin)

    def test_create_user_requires_strong_password(self):
        r = self.client.post(reverse("accounts:user_save"), {"full_name": "New", "username": "new", "password": "123", "role": "staff"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse("accounts:user_save"), {"full_name": "New", "username": "new", "password": PW, "role": "staff"})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(User.objects.get(username="new").check_password(PW))

    def test_edit_without_password_keeps_it(self):
        r = self.client.post(reverse("accounts:user_save"), {"id": self.staff.pk, "full_name": "Renamed", "username": "cashier", "role": "staff"})
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.full_name, "Renamed")
        self.assertTrue(self.staff.check_password(PW))

    def test_cannot_delete_self_or_last_admin(self):
        r = self.client.post(reverse("accounts:user_delete", args=[self.admin.pk]))
        self.assertEqual(r.status_code, 400)
        r = self.client.post(reverse("accounts:user_save"), {"id": self.admin.pk, "full_name": "Boss", "username": "boss", "role": "staff"})
        self.assertEqual(r.status_code, 400)

    def test_delete_deactivates_and_frees_username(self):
        r = self.client.post(reverse("accounts:user_delete", args=[self.staff.pk]))
        self.assertEqual(r.status_code, 200)
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_active)
        self.assertFalse(self.staff.has_usable_password())
        r = self.client.post(reverse("accounts:user_save"), {"full_name": "Again", "username": "cashier", "password": PW, "role": "staff"})
        self.assertEqual(r.status_code, 200)


class AccountTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("cashier", password=PW, full_name="Cashier")
        self.client.force_login(self.user)

    def test_change_password_needs_current_password(self):
        url = reverse("accounts:account_save")
        r = self.client.post(url, {"full_name": "Cashier", "username": "cashier", "current_password": "wrong", "new_password": "N3w-strong-pass"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post(url, {"full_name": "Cashier", "username": "cashier", "current_password": PW, "new_password": "N3w-strong-pass"})
        self.assertEqual(r.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("N3w-strong-pass"))
        # still logged in after changing the password
        self.assertEqual(self.client.get(reverse("core:dashboard")).status_code, 200)
