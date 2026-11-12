from django.db import models


class SiteSettings(models.Model):
    """The cafe's details, printed on receipts and shown in the top bar. Always a single row."""

    name = models.CharField(max_length=120, default="Cafe Billing System")
    email = models.EmailField(blank=True)
    contact = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=250, blank=True)
    currency_symbol = models.CharField(max_length=5, default="₹")
    receipt_footer = models.CharField(max_length=200, blank=True, default="Thank you, visit again!")

    class Meta:
        verbose_name_plural = "site settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSettings":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self) -> str:
        return self.name
