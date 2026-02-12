from django.contrib import admin
from .models import VerificationSession, Tenant, Customer


@admin.register(VerificationSession)
class VerificationSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tenant",
        "status",
        "current_step",
        "liveness_verified",
        "verify_verified",
        "review_status",
        "created_at",
        "updated_at",
    )
    search_fields = ("id", "status", "ip_address", "user_agent", "tenant__name", "tenant__slug")
    list_filter = ("tenant", "status", "review_status")


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("id", "uuid", "name", "slug", "created_at")
    search_fields = ("name", "slug", "uuid")


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "full_name", "email", "phone", "status", "created_at")
    search_fields = ("full_name", "email", "phone", "external_ref", "tenant__name", "tenant__slug")
