from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from kyc.models import Tenant
from .models import User


class UnifiedLoginForm(AuthenticationForm):
    company_id = forms.CharField(required=False, label="Company ID")


class TenantStaffCreationForm(UserCreationForm):
    company_id = forms.CharField(required=True, label="Company ID")
    email = forms.EmailField(required=True)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)

    class Meta:
        model = User
        fields = ("username", "email", "company_id", "role", "password1", "password2")

    def clean_company_id(self):
        company_id = self.cleaned_data.get("company_id")
        if not Tenant.objects.filter(slug=company_id).exists():
            raise forms.ValidationError("Company ID not found.")
        return company_id
