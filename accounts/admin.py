from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),
        ("Tenant", {"fields": ("role", "tenant", "company_id")}),
    )
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
        ("Tenant", {"fields": ("role", "tenant", "company_id")}),
    )
    list_display = ("email", "role", "tenant", "is_staff", "is_superuser")
    list_filter = ("role", "tenant", "is_staff", "is_superuser")
    ordering = ("email",)
    search_fields = ("email",)
