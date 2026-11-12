from django import forms

from .models import Category, Product


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["category", "name", "description", "price", "is_available"]

    def clean_name(self):
        return " ".join(self.cleaned_data["name"].split())
