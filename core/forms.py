from django import forms

from .models import SiteSettings


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = ["name", "email", "contact", "address", "currency_symbol", "receipt_footer"]
