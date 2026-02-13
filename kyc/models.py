import uuid

from django.conf import settings
from django.db import models


class Tenant(models.Model):
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=80, unique=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    plan = models.CharField(
        max_length=30,
        choices=[("free", "Free"), ("basic", "Basic"), ("enterprise", "Enterprise")],
        blank=True,
        null=True,
    )
    suspended_at = models.DateTimeField(blank=True, null=True)
    suspended_reason = models.TextField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="deleted_tenants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return self.name

    class Meta:
        db_table = "tenants"


class Customer(models.Model):
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, to_field="uuid", db_column="tenant_uuid")
    external_ref = models.CharField(max_length=255, blank=True, null=True)
    citizenship_type = models.CharField(
        max_length=20,
        choices=[("japanese", "Japanese"), ("foreign", "Foreign")],
        blank=True,
        null=True,
    )
    full_name = models.CharField(max_length=255)
    full_name_kana = models.CharField(max_length=255, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=20, blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True, null=True)

    postal_code = models.CharField(max_length=20, blank=True, null=True)
    prefecture = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    street_address = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=40, blank=True, null=True)
    status = models.CharField(max_length=30, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "customers"
        unique_together = ("tenant", "external_ref")


class VerificationSession(models.Model):
    id = models.UUIDField(primary_key=True, editable=False)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, null=True, blank=True)
    customer = models.ForeignKey("Customer", on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    status = models.CharField(max_length=50)
    current_step = models.IntegerField(default=1)

    front_image = models.CharField(max_length=255, blank=True, null=True)
    back_image = models.CharField(max_length=255, blank=True, null=True)
    selfie_image = models.CharField(max_length=255, blank=True, null=True)

    document_type = models.CharField(max_length=50, blank=True, null=True)
    document_data = models.JSONField(blank=True, null=True)

    residence_status = models.CharField(max_length=255, blank=True, null=True)
    residence_card_number = models.CharField(max_length=100, blank=True, null=True)
    residence_card_expiry = models.DateField(blank=True, null=True)

    verification_method = models.CharField(max_length=50, blank=True, null=True)
    verified_at = models.DateTimeField(blank=True, null=True)

    document_front_url = models.CharField(max_length=255, blank=True, null=True)
    document_back_url = models.CharField(max_length=255, blank=True, null=True)
    selfie_url = models.CharField(max_length=255, blank=True, null=True)

    liveness_running = models.BooleanField(default=False)
    liveness_completed = models.BooleanField(default=False)
    liveness_verified = models.BooleanField(default=False)
    liveness_confidence = models.FloatField(default=0)
    liveness_challenges = models.JSONField(blank=True, null=True)
    liveness_completed_count = models.IntegerField(blank=True, null=True)
    liveness_total_count = models.IntegerField(blank=True, null=True)

    verify_verified = models.BooleanField(default=False)
    verify_confidence = models.FloatField(default=0)
    verify_similarity = models.FloatField(default=0)

    review_status = models.CharField(max_length=20, default="pending")
    review_notes = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="reviewed_sessions",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)

    user_agent = models.TextField(blank=True, null=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self) -> str:
        return f"Session {self.id}"

    class Meta:
        db_table = "kyc_sessions"


class VerificationLink(models.Model):
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    tenant = models.ForeignKey("Tenant", on_delete=models.CASCADE, to_field="uuid", db_column="tenant_uuid")
    customer = models.ForeignKey("Customer", on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)
    used_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = "kyc_verification_links"
