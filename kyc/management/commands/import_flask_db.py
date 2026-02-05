import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from kyc.models import VerificationSession


class Command(BaseCommand):
    help = "Import verification sessions from the Flask sqlite DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--path",
            default=str(Path(__file__).resolve().parents[3] / "kyc" / "db.sqlite3"),
            help="Path to the Flask sqlite DB (default: kyc/db.sqlite3)",
        )

    def handle(self, *args, **options):
        db_path = Path(options["path"]).expanduser().resolve()
        if not db_path.exists():
            self.stderr.write(self.style.ERROR(f"DB not found: {db_path}"))
            return

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='verification_sessions'")
        if cur.fetchone() is None:
            self.stderr.write(self.style.ERROR("verification_sessions table not found"))
            return

        cur.execute("SELECT * FROM verification_sessions")
        rows = cur.fetchall()
        count = 0

        for row in rows:
            row = dict(row)
            session_id = row.get("id")
            if not session_id:
                continue

            try:
                session_uuid = uuid.UUID(session_id)
            except Exception:
                continue

            created_at = _parse_dt(row.get("created_at"))
            updated_at = _parse_dt(row.get("updated_at"))

            defaults = {
                "status": row.get("status") or "started",
                "current_step": int(row.get("current_step") or 1),
                "front_image": row.get("front_image"),
                "back_image": row.get("back_image"),
                "selfie_image": row.get("selfie_image"),
                "liveness_running": bool(row.get("liveness_running") or 0),
                "liveness_completed": bool(row.get("liveness_completed") or 0),
                "liveness_verified": bool(row.get("liveness_verified") or 0),
                "liveness_confidence": float(row.get("liveness_confidence") or 0),
                "liveness_challenges": _maybe_json(row.get("liveness_challenges")),
                "liveness_completed_count": _maybe_int(row.get("liveness_completed_count")),
                "liveness_total_count": _maybe_int(row.get("liveness_total_count")),
                "verify_verified": bool(row.get("verify_verified") or 0),
                "verify_confidence": float(row.get("verify_confidence") or 0),
                "verify_similarity": float(row.get("verify_similarity") or 0),
                "user_agent": row.get("user_agent"),
                "ip_address": row.get("ip_address"),
                "created_at": created_at,
                "updated_at": updated_at,
            }

            VerificationSession.objects.update_or_create(
                id=session_uuid,
                defaults=defaults,
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {count} session(s)"))


def _parse_dt(value):
    if not value:
        return timezone.now()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return timezone.now()


def _maybe_int(value):
    if value is None:
        return None
    try:
        return int(value)
    except Exception:
        return None


def _maybe_json(value):
    if value is None:
        return None
    try:
        import json

        return json.loads(value)
    except Exception:
        return None
