from django.core.management.base import BaseCommand
from django.utils import timezone

from kyc.models import VerificationLink


class Command(BaseCommand):
    help = "Delete expired verification links."

    def handle(self, *args, **options):
        now = timezone.now()
        qs = VerificationLink.objects.filter(expires_at__isnull=False, expires_at__lt=now)
        count = qs.count()
        qs.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {count} expired link(s)"))
