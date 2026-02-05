from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ("super_admin", "Super Admin"),
        ("support", "Support"),
        ("owner", "Tenant Owner"),
        ("admin", "Tenant Admin"),
        ("staff", "Tenant Staff"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="staff")
    tenant = models.ForeignKey(
        "kyc.Tenant",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="users",
    )
    company_id = models.CharField(max_length=80, blank=True, null=True)

    def is_platform_admin(self) -> bool:
        return self.is_superuser or self.role in {"super_admin", "support"}

    def is_tenant_admin(self) -> bool:
        return self.role in {"owner", "admin"}

    class Meta:
        db_table = "staff_users"
