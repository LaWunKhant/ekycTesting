from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Tenant", {"fields": ("role", "tenant", "company_id")}),
    )
    list_display = ("username", "email", "role", "tenant", "is_staff", "is_superuser")
    list_filter = ("role", "tenant", "is_staff", "is_superuser")
