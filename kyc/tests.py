from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User
from .models import Tenant


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    EMAIL_HOST="sandbox.smtp.mailtrap.io",
    DEFAULT_FROM_EMAIL="noreply@example.com",
)
class PlatformDashboardTenantCreateTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpass123",
        )
        self.client.force_login(self.admin)

    def test_create_tenant_creates_owner_user_and_sends_email(self):
        response = self.client.post(
            reverse("platform_dashboard"),
            {
                "action": "create_tenant",
                "name": "Acme Corp",
                "owner_email": "owner@example.com",
                "plan": "basic",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 200)
        tenant = Tenant.objects.get(slug="acme-corp")
        owner = User.objects.get(email="owner@example.com")

        self.assertEqual(owner.tenant, tenant)
        self.assertEqual(owner.role, "owner")
        self.assertEqual(owner.company_id, tenant.slug)
        self.assertTrue(owner.check_password("adminpass123") is False)
        self.assertContains(response, "Tenant created and welcome email sent")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["owner@example.com"])
        self.assertIn("Tenant name: Acme Corp", mail.outbox[0].body)
        self.assertIn("Temporary password:", mail.outbox[0].body)

    def test_create_tenant_rolls_back_when_email_send_fails(self):
        with patch("kyc.views.send_mail", side_effect=OSError("SMTP unavailable")):
            response = self.client.post(
                reverse("platform_dashboard"),
                {
                    "action": "create_tenant",
                    "name": "Broken Mail Co",
                    "owner_email": "broken@example.com",
                    "plan": "free",
                    "is_active": "on",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Tenant creation email failed")
        self.assertFalse(Tenant.objects.filter(slug="broken-mail-co").exists())
        self.assertFalse(User.objects.filter(email="broken@example.com").exists())
