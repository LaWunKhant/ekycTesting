from django import forms
from django.utils.text import slugify


class TenantCreateForm(forms.Form):
    name = forms.CharField(max_length=255, label="Company name")
    admin_email = forms.EmailField(label="Admin email")
    admin_name = forms.CharField(max_length=255, label="Admin name")
    plan = forms.ChoiceField(
        choices=[("", "Select plan"), ("free", "Free"), ("basic", "Basic"), ("enterprise", "Enterprise")],
        required=False,
    )
    is_active = forms.BooleanField(required=False, initial=True, label="Active")


class TenantUpdateForm(forms.Form):
    name = forms.CharField(max_length=255, label="Company name")
    slug = forms.SlugField(max_length=80, label="Slug")
    plan = forms.ChoiceField(
        choices=[("", "None"), ("free", "Free"), ("basic", "Basic"), ("enterprise", "Enterprise")],
        required=False,
    )
    is_active = forms.BooleanField(required=False, label="Active")
    suspended_reason = forms.CharField(required=False, widget=forms.Textarea, label="Suspended reason")

    def clean_slug(self):
        slug = self.cleaned_data.get("slug")
        return slugify(slug)
