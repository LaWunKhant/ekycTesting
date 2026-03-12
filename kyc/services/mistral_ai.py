import base64
import json
import os
import itertools
import queue
import re
import ssl
import threading
import time
import logging
from datetime import datetime, timezone
from urllib import error, request

from django.conf import settings
import certifi

logger = logging.getLogger(__name__)


_RATE_LIMIT_LOCK = threading.Lock()
_LAST_MISTRAL_CALL_AT = 0.0
_OCR_QUEUE = queue.PriorityQueue()
_WORKER_THREAD = None
_WORKER_LOCK = threading.Lock()
_JOB_SEQ = itertools.count()
_POSTAL_ONLY_RE = re.compile(r"^\s*〒?\s*\d{3}-?\d{4,}\s*$")
_ADDRESS_LOW_DETAIL_RE = re.compile(r"^[\d\s\-〒,./]+$")


def _json_dumps(payload):
    return json.dumps(payload, ensure_ascii=True).encode("utf-8")


def _safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_postal_code(value):
    raw = str(value or "").strip()
    if not raw:
        return ""
    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 7:
        return f"{digits[:3]}-{digits[3:]}"
    return raw


def _sanitize_address_fields(extracted):
    address = str((extracted or {}).get("address") or "").strip()
    postal_code = _normalize_postal_code((extracted or {}).get("postal_code"))
    prefecture = str((extracted or {}).get("prefecture") or "").strip()
    city = str((extracted or {}).get("city") or "").strip()
    street_address = str((extracted or {}).get("street_address") or "").strip()
    address_raw = str((extracted or {}).get("address_raw") or "").strip()

    if not postal_code and _POSTAL_ONLY_RE.match(address):
        postal_code = _normalize_postal_code(address)
    if _POSTAL_ONLY_RE.match(address):
        address = ""

    if not address:
        merged = " ".join(part for part in [prefecture, city, street_address] if part).strip()
        if merged:
            address = merged

    return {
        "address": address,
        "postal_code": postal_code,
        "prefecture": prefecture,
        "city": city,
        "street_address": street_address,
        "address_raw": address_raw,
    }


def _assess_extraction_quality(extracted, side_hint):
    side = str(side_hint or "unknown").strip().lower()
    missing_core_fields = []
    required_fields = ["document_number", "expiry_date"]
    if side == "front":
        required_fields = ["full_name", "date_of_birth", "document_number", "expiry_date"]
    for field in required_fields:
        if not str((extracted or {}).get(field) or "").strip():
            missing_core_fields.append(field)

    address = str((extracted or {}).get("address") or "").strip()
    postal_code = str((extracted or {}).get("postal_code") or "").strip()
    city = str((extracted or {}).get("city") or "").strip()
    street_address = str((extracted or {}).get("street_address") or "").strip()
    prefecture = str((extracted or {}).get("prefecture") or "").strip()

    address_missing = not bool(address)
    address_only_postal = bool(postal_code) and not any([address, city, street_address, prefecture])
    address_low_detail = bool(address) and (_ADDRESS_LOW_DETAIL_RE.match(address) is not None)

    penalty = 0
    penalty += min(30, len(missing_core_fields) * 8)
    if address_only_postal:
        penalty += 15
    if address_low_detail:
        penalty += 10

    return {
        "missing_core_fields": missing_core_fields,
        "address_missing": address_missing,
        "address_only_postal": address_only_postal,
        "address_low_detail": address_low_detail,
        "confidence_penalty": penalty,
    }


def _gather_quality_issues(front_result, back_result, address_summary, back_ocr_enabled):
    issues = []
    front_flags = ((front_result or {}).get("quality_flags") or {}) if isinstance(front_result, dict) else {}
    back_flags = ((back_result or {}).get("quality_flags") or {}) if isinstance(back_result, dict) else {}

    if front_flags.get("missing_core_fields"):
        issues.append("front_missing_core_fields")
    if front_flags.get("address_low_detail"):
        issues.append("front_low_detail_address")
    if front_flags.get("address_only_postal"):
        issues.append("front_postal_only_address")

    if back_ocr_enabled:
        if not (isinstance(back_result, dict) and back_result.get("ok")):
            issues.append("back_ocr_unavailable")
        elif back_flags.get("address_missing"):
            issues.append("back_missing_address")

    if not str((address_summary or {}).get("selected_address") or "").strip():
        issues.append("no_selected_address")
    return issues


def _parse_json_block(text):
    if not text:
        return {}
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 3:
            text = "\n".join(lines[1:-1]).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return {}


def _to_base64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


def _build_ssl_context():
    verify_ssl = bool(getattr(settings, "MISTRAL_SSL_VERIFY", True))
    if not verify_ssl:
        return ssl._create_unverified_context()

    explicit_bundle = (getattr(settings, "MISTRAL_CA_BUNDLE", "") or "").strip()
    if explicit_bundle:
        return ssl.create_default_context(cafile=explicit_bundle)

    return ssl.create_default_context(cafile=certifi.where())


def _request_mistral_ocr(image_path, document_type, side_hint="unknown"):
    api_key = getattr(settings, "MISTRAL_API_KEY", "").strip()
    base_url = getattr(settings, "MISTRAL_BASE_URL", "https://api.mistral.ai/v1").rstrip("/")
    model = getattr(settings, "MISTRAL_OCR_MODEL", "mistral-ocr-latest").strip()
    timeout = int(getattr(settings, "MISTRAL_REQUEST_TIMEOUT", 25))

    if not api_key:
        return {"ok": False, "error": "MISTRAL_API_KEY is not configured"}
    if not os.path.exists(image_path):
        return {"ok": False, "error": "document image not found"}

    image_b64 = _to_base64(image_path)
    prompt = (
        "You are an eKYC OCR assistant. Extract document fields from the image.\n"
        "Rules:\n"
        "- Extract only what is visible.\n"
        "- Never use MRZ/id-number/random digits as an address.\n"
        "- If only postal code is visible, set address to empty string and set postal_code.\n"
        "- For residence card back side, if multiple address history rows exist, use the latest/current row.\n"
        "Return strict JSON only with this schema:\n"
        "{"
        "\"full_name\":\"\","
        "\"date_of_birth\":\"\","
        "\"document_number\":\"\","
        "\"expiry_date\":\"\","
        "\"nationality\":\"\","
        "\"address\":\"\","
        "\"postal_code\":\"\","
        "\"prefecture\":\"\","
        "\"city\":\"\","
        "\"street_address\":\"\","
        "\"address_raw\":\"\","
        "\"residence_status\":\"\","
        "\"confidence\":0,"
        "\"notes\":\"\""
        "}\n"
        "confidence must be an integer from 0 to 100. "
        f"Document type hint: {document_type or 'unknown'}. "
        f"Image side hint: {side_hint or 'unknown'}."
    )
    payload = {
        "model": model,
        "document": {
            "type": "image_url",
            "image_url": f"data:image/jpeg;base64,{image_b64}",
        },
        "include_image_base64": False,
        "document_annotation_prompt": prompt,
        "document_annotation_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "kyc_document_extraction",
                "schema": {
                    "type": "object",
                    "properties": {
                        "full_name": {"type": "string"},
                        "date_of_birth": {"type": "string"},
                        "document_number": {"type": "string"},
                        "expiry_date": {"type": "string"},
                        "nationality": {"type": "string"},
                        "address": {"type": "string"},
                        "postal_code": {"type": "string"},
                        "prefecture": {"type": "string"},
                        "city": {"type": "string"},
                        "street_address": {"type": "string"},
                        "address_raw": {"type": "string"},
                        "residence_status": {"type": "string"},
                        "confidence": {"type": "number"},
                        "notes": {"type": "string"},
                    },
                    "required": [
                        "full_name",
                        "date_of_birth",
                        "document_number",
                        "expiry_date",
                        "nationality",
                        "address",
                        "confidence",
                        "notes",
                    ],
                    "additionalProperties": False,
                },
            },
        },
    }

    req = request.Request(
        url=f"{base_url}/ocr",
        data=_json_dumps(payload),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    ssl_context = _build_ssl_context()
    try:
        with request.urlopen(req, timeout=timeout, context=ssl_context) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"Mistral HTTP {exc.code}", "details": body[:500]}
    except error.URLError as exc:
        reason = exc.reason
        if isinstance(reason, Exception):
            reason_text = f"{type(reason).__name__}: {reason}"
        else:
            reason_text = str(reason or "network error")
        return {"ok": False, "error": "Mistral network error", "details": reason_text[:500]}
    except TimeoutError:
        return {
            "ok": False,
            "error": "Mistral timeout",
            "details": f"No response within {timeout}s. Increase MISTRAL_REQUEST_TIMEOUT or check network.",
        }
    except Exception as exc:
        msg = str(exc).strip() or repr(exc)
        return {"ok": False, "error": f"Mistral request failed ({type(exc).__name__})", "details": msg[:500]}

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"ok": False, "error": "Invalid JSON response from Mistral"}

    extracted = {}
    annotation = parsed.get("document_annotation")
    if isinstance(annotation, dict):
        extracted = annotation
    elif isinstance(annotation, str):
        extracted = _parse_json_block(annotation)

    pages = parsed.get("pages") or []
    page_markdown = ""
    if pages and isinstance(pages, list):
        first = pages[0] or {}
        page_markdown = str(first.get("markdown") or "").strip()

    if not extracted and page_markdown:
        extracted = {
            "notes": page_markdown[:5000],
            "confidence": 25,
        }

    raw_confidence = max(0.0, min(100.0, _safe_float(extracted.get("confidence"), default=0.0)))
    address_fields = _sanitize_address_fields(extracted)
    quality_flags = _assess_extraction_quality(
        {
            "full_name": (extracted.get("full_name") or "").strip(),
            "date_of_birth": (extracted.get("date_of_birth") or "").strip(),
            "document_number": (extracted.get("document_number") or "").strip(),
            "expiry_date": (extracted.get("expiry_date") or "").strip(),
            "address": address_fields["address"],
            "postal_code": address_fields["postal_code"],
            "prefecture": address_fields["prefecture"],
            "city": address_fields["city"],
            "street_address": address_fields["street_address"],
        },
        side_hint=side_hint,
    )
    confidence = max(0.0, min(100.0, raw_confidence - _safe_float(quality_flags.get("confidence_penalty"), default=0.0)))
    return {
        "ok": True,
        "provider": "mistral",
        "model": model,
        "endpoint": "ocr",
        "document_type": document_type,
        "side": side_hint or "unknown",
        "extracted": {
            "full_name": (extracted.get("full_name") or "").strip(),
            "date_of_birth": (extracted.get("date_of_birth") or "").strip(),
            "document_number": (extracted.get("document_number") or "").strip(),
            "expiry_date": (extracted.get("expiry_date") or "").strip(),
            "nationality": (extracted.get("nationality") or "").strip(),
            "address": address_fields["address"],
            "postal_code": address_fields["postal_code"],
            "prefecture": address_fields["prefecture"],
            "city": address_fields["city"],
            "street_address": address_fields["street_address"],
            "address_raw": address_fields["address_raw"],
            "residence_status": (extracted.get("residence_status") or "").strip(),
            "notes": (extracted.get("notes") or page_markdown or "").strip(),
        },
        "quality_flags": quality_flags,
        "raw_confidence": raw_confidence,
        "confidence": confidence,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def _normalized_text(value):
    return " ".join(str(value or "").strip().lower().split())


def _build_address_summary(front_result, back_result):
    def _entry(result, source):
        if not isinstance(result, dict) or not result.get("ok"):
            return None
        extracted = result.get("extracted") or {}
        address = str(extracted.get("address") or "").strip()
        if not address:
            return None
        return {
            "source": source,
            "address": address,
            "confidence": max(0.0, min(100.0, _safe_float(result.get("confidence"), default=0.0))),
        }

    front_entry = _entry(front_result, "front")
    back_entry = _entry(back_result, "back")
    candidates = []
    seen = set()
    for entry in (front_entry, back_entry):
        if not entry:
            continue
        normalized = _normalized_text(entry["address"])
        if normalized in seen:
            continue
        seen.add(normalized)
        candidates.append(entry)

    selected = {"address": "", "source": ""}
    if back_entry:
        selected = {"address": back_entry["address"], "source": "back"}
    elif front_entry:
        selected = {"address": front_entry["address"], "source": "front"}

    return {
        "selected_address": selected["address"],
        "selected_source": selected["source"],
        "has_conflict": bool(front_entry and back_entry and _normalized_text(front_entry["address"]) != _normalized_text(back_entry["address"])),
        "candidates": candidates,
    }


def _pick_identity_ocr_result(front_result, back_result):
    if isinstance(front_result, dict) and front_result.get("ok"):
        return front_result
    if isinstance(back_result, dict) and back_result.get("ok"):
        return back_result
    return {}


def build_identity_assist(face_similarity, liveness_verified, customer, ocr_result, quality_issues=None):
    ocr_data = (ocr_result or {}).get("extracted") or {}
    has_ocr = bool((ocr_result or {}).get("ok"))
    face_score = max(0.0, min(100.0, _safe_float(face_similarity, default=0.0)))
    ocr_conf = max(0.0, min(100.0, _safe_float((ocr_result or {}).get("confidence"), default=0.0))) if has_ocr else 0.0
    liveness_score = 100.0 if liveness_verified else 35.0

    name_match = False
    dob_match = False
    if customer is not None and has_ocr:
        customer_name = _normalized_text(getattr(customer, "full_name", ""))
        ocr_name = _normalized_text(ocr_data.get("full_name"))
        if customer_name and ocr_name:
            name_match = customer_name in ocr_name or ocr_name in customer_name

        customer_dob = getattr(customer, "date_of_birth", None)
        customer_dob_text = str(customer_dob) if customer_dob else ""
        ocr_dob = _normalized_text(ocr_data.get("date_of_birth"))
        if customer_dob_text and ocr_dob:
            dob_match = customer_dob_text in ocr_dob or ocr_dob in customer_dob_text

    profile_match_score = 0.0
    if name_match:
        profile_match_score += 60.0
    if dob_match:
        profile_match_score += 40.0

    weights = {
        "face": 0.60,
        "liveness": 0.10,
        "ocr": 0.20 if has_ocr else 0.0,
        "profile": 0.10 if has_ocr else 0.0,
    }
    active_weight = sum(weights.values()) or 1.0
    combined = (
        (weights["face"] * face_score)
        + (weights["liveness"] * liveness_score)
        + (weights["ocr"] * ocr_conf)
        + (weights["profile"] * profile_match_score)
    ) / active_weight
    combined = max(0.0, min(100.0, combined))

    if combined >= 80:
        recommendation = "high_match_manual_confirm"
    elif combined >= 60:
        recommendation = "medium_match_manual_review"
    else:
        recommendation = "low_match_investigate"

    normalized_issues = [issue for issue in (quality_issues or []) if issue]
    requires_additional_info = bool(
        normalized_issues and any(
            issue in {"no_selected_address", "back_ocr_unavailable", "front_missing_core_fields", "back_missing_address"}
            for issue in normalized_issues
        )
    )
    if requires_additional_info:
        recommendation = "needs_info_manual_review"

    return {
        "score": round(combined, 2),
        "face_similarity_score": round(face_score, 2),
        "ocr_confidence_score": round(ocr_conf, 2),
        "liveness_score": round(liveness_score, 2),
        "profile_match_score": round(profile_match_score, 2),
        "name_match": bool(name_match),
        "dob_match": bool(dob_match),
        "recommendation": recommendation,
        "quality_issues": normalized_issues,
        "requires_additional_info": requires_additional_info,
        "scoring_mode": "with_ocr" if has_ocr else "fallback_without_ocr",
    }


def _respect_mistral_interval():
    global _LAST_MISTRAL_CALL_AT
    min_interval = max(0.0, float(getattr(settings, "MISTRAL_MIN_INTERVAL_SECONDS", 1.0)))
    if min_interval <= 0:
        return
    with _RATE_LIMIT_LOCK:
        now = time.monotonic()
        wait_for = (_LAST_MISTRAL_CALL_AT + min_interval) - now
        if wait_for > 0:
            time.sleep(wait_for)
        _LAST_MISTRAL_CALL_AT = time.monotonic()


def _is_rate_limited(result):
    if not isinstance(result, dict):
        return False
    err = (result.get("error") or "").lower()
    details = (result.get("details") or "").lower()
    return ("http 429" in err) or ("rate limit" in err) or ('"code":"1300"' in details)


def extract_with_mistral(image_path, document_type, side_hint="unknown"):
    max_retries = max(0, int(getattr(settings, "MISTRAL_MAX_RETRIES", 2)))
    retry_base = max(0.1, float(getattr(settings, "MISTRAL_RETRY_BASE_SECONDS", 1.0)))

    last_result = None
    for attempt in range(max_retries + 1):
        _respect_mistral_interval()
        result = _request_mistral_ocr(image_path=image_path, document_type=document_type, side_hint=side_hint)
        last_result = result
        if result.get("ok"):
            return result
        if not _is_rate_limited(result) or attempt >= max_retries:
            return result
        time.sleep(retry_base * (2 ** attempt))
    return last_result or {"ok": False, "error": "Mistral request failed", "details": "unknown error"}


def _process_ocr_job(job):
    from kyc.models import VerificationSession

    session_id = job.get("session_id")
    tenant_id = job.get("tenant_id")
    front_path = job.get("front_path")
    back_path = job.get("back_path")
    document_type = job.get("document_type")
    enable_back_ocr = bool(job.get("enable_back_ocr", False))

    front_result = extract_with_mistral(front_path, document_type=document_type, side_hint="front")
    back_result = None
    if enable_back_ocr and back_path and os.path.exists(back_path):
        back_result = extract_with_mistral(back_path, document_type=document_type, side_hint="back")

    rate_limited = _is_rate_limited(front_result) or _is_rate_limited(back_result or {})
    queue_attempt = int(job.get("queue_attempt", 0))
    queue_max_attempts = max(0, int(getattr(settings, "MISTRAL_QUEUE_MAX_ATTEMPTS", 6)))
    queue_retry_base = max(1.0, float(getattr(settings, "MISTRAL_QUEUE_RETRY_BASE_SECONDS", 30.0)))

    try:
        session = VerificationSession.objects.select_related("customer").get(id=session_id, tenant_id=tenant_id)
    except VerificationSession.DoesNotExist:
        return

    if rate_limited and queue_attempt < queue_max_attempts:
        retry_in = queue_retry_base * (2 ** queue_attempt)
        address_summary = _build_address_summary(front_result, back_result)
        session_document_data = session.document_data or {}
        session_document_data["ai_document_extraction"] = {
            "status": "rate_limited_retry",
            "front": front_result,
            "back": back_result,
            "address_summary": address_summary,
            "queued_at": job.get("queued_at"),
            "processed_at": datetime.now(timezone.utc).isoformat(),
            "retry_in_seconds": round(retry_in, 2),
            "queue_attempt": queue_attempt + 1,
            "queue_max_attempts": queue_max_attempts,
        }
        session.document_data = session_document_data
        session.updated_at = datetime.now(timezone.utc)
        session.save(update_fields=["document_data", "updated_at"])
        enqueue_session_ocr(
            session_id=session_id,
            tenant_id=tenant_id,
            front_path=front_path,
            back_path=back_path,
            document_type=document_type,
            enable_back_ocr=enable_back_ocr,
            queue_attempt=queue_attempt + 1,
            delay_seconds=retry_in,
            queued_at=job.get("queued_at"),
        )
        return

    address_summary = _build_address_summary(front_result, back_result)
    quality_issues = _gather_quality_issues(
        front_result=front_result,
        back_result=back_result,
        address_summary=address_summary,
        back_ocr_enabled=enable_back_ocr,
    )
    identity_assist = build_identity_assist(
        face_similarity=session.verify_similarity,
        liveness_verified=session.liveness_verified,
        customer=session.customer,
        ocr_result=_pick_identity_ocr_result(front_result, back_result),
        quality_issues=quality_issues,
    )
    session_document_data = session.document_data or {}
    session_document_data["ai_document_extraction"] = {
        "status": "completed",
        "front": front_result,
        "back": back_result,
        "address_summary": address_summary,
        "queued_at": job.get("queued_at"),
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    session_document_data["identity_assist"] = identity_assist
    session.document_data = session_document_data
    session.updated_at = datetime.now(timezone.utc)
    session.save(update_fields=["document_data", "updated_at"])


def _worker_loop():
    while True:
        next_run_at, _, job = _OCR_QUEUE.get()
        try:
            now = time.time()
            if next_run_at > now:
                _OCR_QUEUE.put((next_run_at, next(_JOB_SEQ), job))
                time.sleep(min(next_run_at - now, 2.0))
                continue
            _process_ocr_job(job)
        except Exception:
            # Keep worker alive on job-level failures.
            logger.exception("Mistral OCR worker job failed")
        finally:
            _OCR_QUEUE.task_done()


def _ensure_worker_started():
    global _WORKER_THREAD
    with _WORKER_LOCK:
        if _WORKER_THREAD and _WORKER_THREAD.is_alive():
            return
        _WORKER_THREAD = threading.Thread(target=_worker_loop, daemon=True, name="mistral-ocr-worker")
        _WORKER_THREAD.start()


def enqueue_session_ocr(
    session_id,
    tenant_id,
    front_path,
    back_path,
    document_type,
    enable_back_ocr=False,
    queue_attempt=0,
    delay_seconds=0.0,
    queued_at=None,
):
    _ensure_worker_started()
    job = {
        "session_id": session_id,
        "tenant_id": tenant_id,
        "front_path": front_path,
        "back_path": back_path,
        "document_type": document_type,
        "enable_back_ocr": bool(enable_back_ocr),
        "queue_attempt": int(queue_attempt),
        "queued_at": queued_at or datetime.now(timezone.utc).isoformat(),
    }
    run_at = time.time() + max(0.0, float(delay_seconds))
    _OCR_QUEUE.put((run_at, next(_JOB_SEQ), job))
