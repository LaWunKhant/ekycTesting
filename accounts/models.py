from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", "super_admin")

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
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

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "staff_users"
