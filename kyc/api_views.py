import base64
import json
import os
from datetime import datetime, timezone

import cv2
import numpy as np
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from django.core.mail import send_mail
from django.utils import timezone as dj_timezone
from django.utils.dateparse import parse_date

from .models import VerificationSession, Tenant, Customer


CARD_TYPE_LABELS = {
    "driver_license": "Driver License",
    "my_number": "My Number Card",
    "passport": "Passport",
    "residence_card": "Residence Card",
}


@csrf_exempt
def start_session(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST requests allowed"}, status=405)

    import uuid

    session_uuid = uuid.uuid4()

    user_agent = request.headers.get("User-Agent", "unknown")
    ip_address = request.META.get("REMOTE_ADDR")
    now = datetime.now(timezone.utc)

    try:
        data = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    tenant = _resolve_tenant(data, request)
    if tenant is None:
        return JsonResponse({"success": False, "error": "Missing or invalid tenant"}, status=400)

    customer_id = data.get("customer_id")
    customer = None
    if customer_id:
        try:
            customer = Customer.objects.get(id=customer_id, tenant=tenant)
        except Customer.DoesNotExist:
            return JsonResponse({"success": False, "error": "Customer not found"}, status=404)

    VerificationSession.objects.create(
        id=session_uuid,
        tenant=tenant,
        customer=customer,
        status="started",
        current_step=1,
        user_agent=user_agent,
        ip_address=ip_address,
        created_at=now,
        updated_at=now,
    )

    return JsonResponse({"success": True, "session_id": str(session_uuid), "status": "started"})


@csrf_exempt
def submit_session(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST requests allowed"}, status=405)

    try:
        data = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    session_id = data.get("session_id")
    if not session_id:
        return JsonResponse({"success": False, "error": "Missing session_id"}, status=400)

    tenant = _resolve_tenant(data, request)
    if tenant is None:
        return JsonResponse({"success": False, "error": "Missing or invalid tenant"}, status=400)

    try:
        session = VerificationSession.objects.select_related("customer").get(id=session_id, tenant=tenant)
    except VerificationSession.DoesNotExist:
        return JsonResponse({"success": False, "error": "Session not found"}, status=404)

    customer_data = data.get("customer") or {}
    document_data = data.get("document") or {}

    customer = session.customer
    if customer is None:
        customer = Customer(tenant=tenant)

    customer.external_ref = customer_data.get("external_ref") or customer.external_ref
    customer.citizenship_type = customer_data.get("citizenship_type") or customer.citizenship_type
    customer.full_name = customer_data.get("full_name") or customer.full_name
    customer.full_name_kana = customer_data.get("full_name_kana") or customer.full_name_kana

    dob = customer_data.get("date_of_birth")
    if dob:
        customer.date_of_birth = parse_date(dob)

    customer.gender = customer_data.get("gender") or customer.gender
    customer.nationality = customer_data.get("nationality") or customer.nationality
    customer.postal_code = customer_data.get("postal_code") or customer.postal_code
    customer.prefecture = customer_data.get("prefecture") or customer.prefecture
    customer.city = customer_data.get("city") or customer.city
    customer.street_address = customer_data.get("street_address") or customer.street_address
    customer.email = customer_data.get("email") or customer.email
    customer.phone = customer_data.get("phone") or customer.phone
    customer.save()

    session.customer = customer
    session.document_type = document_data.get("document_type") or session.document_type
    session.detected_card_type = CARD_TYPE_LABELS.get(session.document_type, session.document_type)
    session.document_data = document_data.get("document_data") or session.document_data
    session.residence_status = document_data.get("residence_status") or session.residence_status
    session.residence_card_number = document_data.get("residence_card_number") or session.residence_card_number

    expiry = document_data.get("residence_card_expiry")
    if expiry:
        session.residence_card_expiry = parse_date(expiry)

    session.status = "submitted"
    session.updated_at = dj_timezone.now()
    session.save(update_fields=[
        "customer",
        "document_type",
        "detected_card_type",
        "document_data",
        "residence_status",
        "residence_card_number",
        "residence_card_expiry",
        "status",
        "updated_at",
    ])

    if customer.email:
        send_mail(
            subject="KYC Submission Received",
            message=(
                f"Hello {customer.full_name},\n\n"
                "We received your verification details. Our team is reviewing your submission and will update you soon.\n\n"
                "Thank you."
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[customer.email],
            fail_silently=True,
        )

    return JsonResponse({"success": True, "customer_id": customer.id, "status": session.status})


@csrf_exempt
def session_status(request, session_id):
    if request.method != "GET":
        return JsonResponse({"success": False, "error": "Only GET requests allowed"}, status=405)

    tenant = _resolve_tenant({}, request)
    if tenant is None:
        return JsonResponse({"success": False, "error": "Missing or invalid tenant"}, status=400)

    try:
        session = VerificationSession.objects.get(id=session_id, tenant=tenant)
    except VerificationSession.DoesNotExist:
        return JsonResponse({"success": False, "error": "session not found"}, status=404)

    data = {
        "id": str(session.id),
        "tenant_id": session.tenant_id,
        "tenant_slug": session.tenant.slug if session.tenant else None,
        "customer_id": session.customer_id,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "status": session.status,
        "current_step": session.current_step,
        "front_image": session.front_image,
        "back_image": session.back_image,
        "selfie_image": session.selfie_image,
        "tilt_frames": session.tilt_frames,
        "liveness_running": session.liveness_running,
        "liveness_completed": session.liveness_completed,
        "liveness_verified": session.liveness_verified,
        "liveness_confidence": session.liveness_confidence,
        "liveness_challenges": session.liveness_challenges,
        "liveness_completed_count": session.liveness_completed_count,
        "liveness_total_count": session.liveness_total_count,
        "verify_verified": session.verify_verified,
        "verify_confidence": session.verify_confidence,
        "verify_similarity": session.verify_similarity,
        "physical_card_verified": session.physical_card_verified,
        "physical_card_score": session.physical_card_score,
        "edge_consistency_score": session.edge_consistency_score,
        "depth_variation_score": session.depth_variation_score,
        "tilt_analysis": session.tilt_analysis,
        "detected_card_type": session.detected_card_type,
        "user_agent": session.user_agent,
        "ip_address": session.ip_address,
    }

    return JsonResponse({"success": True, "session": data})


@csrf_exempt
def save_liveness_result(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST requests allowed"}, status=405)

    try:
        data = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    session_id = data.get("session_id")
    if not session_id:
        return JsonResponse({"success": False, "error": "Missing session_id"}, status=400)

    tenant = _resolve_tenant(data, request)
    if tenant is None:
        return JsonResponse({"success": False, "error": "Missing or invalid tenant"}, status=400)

    try:
        session = VerificationSession.objects.get(id=session_id, tenant=tenant)
    except VerificationSession.DoesNotExist:
        return JsonResponse({"success": False, "error": "Session not found"}, status=404)

    verified = bool(data.get("verified", False))
    confidence = float(data.get("confidence", 0.0))

    challenges = data.get("challenges") or {}
    completed_count = int(sum(1 for v in challenges.values() if v))
    total_count = int(len(challenges)) if challenges else 0

    session.liveness_running = False
    session.liveness_completed = True
    session.liveness_verified = verified
    session.liveness_confidence = confidence
    session.liveness_challenges = challenges
    session.liveness_completed_count = completed_count
    session.liveness_total_count = total_count
    session.updated_at = datetime.now(timezone.utc)
    session.save(update_fields=[
        "liveness_running",
        "liveness_completed",
        "liveness_verified",
        "liveness_confidence",
        "liveness_challenges",
        "liveness_completed_count",
        "liveness_total_count",
        "updated_at",
    ])

    return JsonResponse({"success": True})


@csrf_exempt
def capture_image(request):
    if request.method == "OPTIONS":
        response = JsonResponse({"success": True})
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Headers"] = "Content-Type"
        response["Access-Control-Allow-Methods"] = "POST"
        return response

    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Only POST requests allowed"}, status=405)

    try:
        data = _parse_json(request)
    except ValueError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    image_data = data.get("image")
    image_type = data.get("type")
    session_id = data.get("session_id")

    if not image_data or not image_type or not session_id:
        return JsonResponse({"success": False, "error": "Missing image, type, or session_id"}, status=400)

    tenant = _resolve_tenant(data, request)
    if tenant is None:
        return JsonResponse({"success": False, "error": "Missing or invalid tenant"}, status=400)

    if "base64," in image_data:
        image_data = image_data.split("base64,")[1]

    try:
        image_bytes = base64.b64decode(image_data)
    except Exception as exc:
        return JsonResponse({"success": False, "error": f"Invalid base64 data: {exc}"}, status=400)

    try:
        session = VerificationSession.objects.get(id=session_id, tenant=tenant)
    except VerificationSession.DoesNotExist:
        return JsonResponse({"success": False, "error": "Session not found"}, status=404)

    # Verify image quality
    img = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return JsonResponse({"success": False, "error": "Invalid image data"}, status=400)

    height, width = img.shape[:2]
    if width < 200 or height < 200:
        return JsonResponse({
            "success": False,
            "error": f"Image too small ({width}x{height}). Please retake with better quality.",
        }, status=400)

    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{image_type}_{timestamp}.jpg"
    filepath = os.path.join(settings.MEDIA_ROOT, filename)

    with open(filepath, "wb") as f:
        f.write(image_bytes)

    col_map = {
        "front": "front_image",
        "back": "back_image",
        "selfie": "selfie_image",
    }
    doc_col_map = {
        "front": "document_front_url",
        "back": "document_back_url",
        "selfie": "selfie_url",
    }
    step_map = {"front": 2, "back": 3, "selfie": 4}

    col = col_map.get(image_type)
    is_tilt_frame = image_type.startswith("tilt_")

    if not col and not is_tilt_frame:
        return JsonResponse({"success": False, "error": "Invalid image type"}, status=400)

    new_step = step_map.get(image_type, 1)
    update_fields = ["updated_at"]

    if is_tilt_frame:
        frames = list(session.tilt_frames or [])
        frames.append(filename)
        session.tilt_frames = frames[-5:]
        session.current_step = max(session.current_step, 5)
        update_fields.extend(["tilt_frames", "current_step"])
    else:
        setattr(session, col, filename)
        doc_col = doc_col_map.get(image_type)
        if doc_col:
            setattr(session, doc_col, filename)
        if session.current_step < new_step:
            session.current_step = new_step
        update_fields.extend([col, "current_step"])
        if doc_col:
            update_fields.append(doc_col)

    session.updated_at = datetime.now(timezone.utc)
    session.save(update_fields=update_fields)

    return JsonResponse({
        "success": True,
        "filename": filename,
        "path": filepath,
        "size": len(image_bytes),
    })


def _parse_json(request):
    body = request.body.decode("utf-8").strip()
    if not body:
        return {}
    try:
        return json.loads(body)
    except Exception as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc


def _resolve_tenant(data, request):
    tenant_id = data.get("tenant_id") or request.GET.get("tenant_id") or request.headers.get("X-Tenant-Id")
    tenant_slug = data.get("tenant_slug") or request.GET.get("tenant_slug") or request.headers.get("X-Tenant-Slug")

    if not tenant_id and not tenant_slug:
        return None

    try:
        if tenant_id:
            return Tenant.objects.get(id=tenant_id)
        return Tenant.objects.get(slug=tenant_slug)
    except Tenant.DoesNotExist:
        return None
