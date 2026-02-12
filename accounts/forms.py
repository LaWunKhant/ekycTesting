from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from kyc.models import Tenant
from .models import User


class UnifiedLoginForm(AuthenticationForm):
    company_id = forms.CharField(required=False, label="Company ID")

    username = forms.EmailField(label="Email")


class TenantStaffCreationForm(UserCreationForm):
    company_id = forms.CharField(required=True, label="Company ID")
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ("email", "company_id", "role", "password1", "password2")

    def clean_company_id(self):
        company_id = self.cleaned_data.get("company_id")
        if not Tenant.objects.filter(slug=company_id).exists():
            raise forms.ValidationError("Company ID not found.")
        return company_id


class TenantSignupForm(UserCreationForm):
    tenant_name = forms.CharField(required=True, label="Company Name")
    tenant_slug = forms.SlugField(required=True, label="Company ID")
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("email", "tenant_name", "tenant_slug", "password1", "password2")

    def clean_tenant_slug(self):
        slug = self.cleaned_data.get("tenant_slug")
        if Tenant.objects.filter(slug=slug).exists():
            raise forms.ValidationError("Company ID already exists.")
        return slug
