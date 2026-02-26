import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth import authenticate, login
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.decorators import login_required
import json
import os
import cv2
import numpy as np
import base64
from datetime import datetime, timezone
import subprocess
import time
from .models import VerificationSession, Tenant, Customer, VerificationLink
from accounts.models import User
from django import forms
from django.utils import timezone as dj_timezone
from datetime import timedelta
from django.conf import settings as django_settings
from django.core.mail import send_mail
from django.utils.text import slugify
from django.utils.crypto import get_random_string
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.db.models import Q

from .forms import TenantCreateForm, TenantUpdateForm
from .services.card_physical_check import analyze_card_physicality

# Global variable to track liveness process
liveness_process = None
logger = logging.getLogger(__name__)


def _generate_temp_password(length=12):
    # Alphanumeric temp password compatible with Django 6 (make_random_password removed).
    return get_random_string(length)


def _send_tenant_admin_temp_password_email(request, tenant, admin_user, temp_password):
    login_url = request.build_absolute_uri(getattr(django_settings, "LOGIN_URL", "/accounts/login/"))
    send_mail(
        subject=f"Your {tenant.name} admin account",
        message=(
            f"Hello {admin_user.first_name or admin_user.email},\n\n"
            f"Your tenant admin account for {tenant.name} has been created.\n\n"
            f"Login URL: {login_url}\n"
            f"Email: {admin_user.email}\n"
            f"Temporary password: {temp_password}\n\n"
            "Please log in and change your password after signing in."
        ),
        from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[admin_user.email],
        fail_silently=False,
    )


def index(request):
    """Render the main KYC verification page"""
    return render(request, 'kyc/index.html')


def liveness_page(request):
    """Render the liveness detection page"""
    return render(request, 'kyc/liveness.html')


def _role_denied():
    return HttpResponseForbidden("Access denied")


def _require_user_type(user, allowed_types):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return "super_admin" in allowed_types
    return user.role in allowed_types


@login_required
def platform_dashboard(request):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()

    tenants = Tenant.objects.all().order_by("name")
    pending_sessions = VerificationSession.objects.select_related("tenant", "customer").filter(
        review_status="pending"
    ).order_by("-created_at")[:50]
    users = User.objects.select_related("tenant").order_by("email")[:200]
    create_form = TenantCreateForm()
    created_admin_password = None
    create_error = None
    create_success = None

    if request.method == "POST" and request.POST.get("action") == "create_tenant":
        create_form = TenantCreateForm(request.POST)
        if create_form.is_valid():
            name = create_form.cleaned_data["name"]
            slug = slugify(name)
            admin_email = create_form.cleaned_data["admin_email"]
            admin_name = create_form.cleaned_data["admin_name"]
            plan = create_form.cleaned_data.get("plan") or None
            is_active = bool(create_form.cleaned_data.get("is_active"))

            if Tenant.objects.filter(slug=slug).exists():
                create_error = "Tenant slug already exists."
            else:
                tenant = Tenant.objects.create(
                    name=name,
                    slug=slug,
                    plan=plan,
                    is_active=is_active,
                    suspended_at=None if is_active else dj_timezone.now(),
                    suspended_reason=None if is_active else "Created inactive",
                )

                password = _generate_temp_password()
                admin_user = User.objects.create_user(
                    email=admin_email,
                    password=password,
                    role="owner",
                    tenant=tenant,
                    is_staff=True,
                )
                admin_user.first_name = admin_name
                admin_user.save(update_fields=["first_name"])
                try:
                    _send_tenant_admin_temp_password_email(request, tenant, admin_user, password)
                    create_success = f"Tenant created. Temporary password emailed to {admin_email}."
                except Exception as exc:
                    logger.exception("Failed to send tenant admin email for tenant=%s email=%s", tenant.slug, admin_email)
                    created_admin_password = password
                    create_error = "Tenant created, but email could not be sent. Share the temporary password shown below manually."
                    if django_settings.DEBUG:
                        create_error = f"{create_error} ({exc})"
        else:
            create_error = "Please correct the form errors."

    context = {
        "tenants": tenants,
        "tenant_count": Tenant.objects.filter(deleted_at__isnull=True).count(),
        "user_count": User.objects.count(),
        "session_count": VerificationSession.objects.count(),
        "pending_reviews": VerificationSession.objects.filter(review_status="pending").count(),
        "pending_sessions": pending_sessions,
        "users": users,
        "create_form": create_form,
        "create_error": create_error,
        "create_success": create_success,
        "created_admin_password": created_admin_password,
    }
    return render(request, "kyc/platform_dashboard.html", context)


def platform_dashboard_legacy(request):
    return redirect("platform_dashboard")


@login_required
def admin_tenant_detail(request, tenant_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    tenant = get_object_or_404(Tenant, uuid=tenant_id)
    users = User.objects.filter(tenant=tenant).order_by("email")
    sessions = VerificationSession.objects.filter(tenant=tenant).order_by("-created_at")[:100]
    context = {
        "tenant": tenant,
        "users": users,
        "sessions": sessions,
    }
    return render(request, "kyc/admin_tenant_detail.html", context)


@login_required
def admin_tenant_edit(request, tenant_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    tenant = get_object_or_404(Tenant, uuid=tenant_id)
    error = None

    if request.method == "POST":
        form = TenantUpdateForm(request.POST)
        if form.is_valid():
            slug = form.cleaned_data["slug"]
            if Tenant.objects.exclude(uuid=tenant.uuid).filter(slug=slug).exists():
                error = "Tenant slug already exists."
            else:
                tenant.name = form.cleaned_data["name"]
                tenant.slug = slug
                tenant.plan = form.cleaned_data.get("plan") or None
                tenant.is_active = bool(form.cleaned_data.get("is_active"))
                tenant.suspended_reason = form.cleaned_data.get("suspended_reason") or None
                tenant.suspended_at = None if tenant.is_active else (tenant.suspended_at or dj_timezone.now())
                tenant.save()
                return redirect("admin_tenant_detail", tenant_id=tenant.uuid)
    else:
        form = TenantUpdateForm(
            initial={
                "name": tenant.name,
                "slug": tenant.slug,
                "plan": tenant.plan or "",
                "is_active": tenant.is_active,
                "suspended_reason": tenant.suspended_reason or "",
            }
        )

    return render(
        request,
        "kyc/admin_tenant_edit.html",
        {"tenant": tenant, "form": form, "error": error},
    )


@login_required
def admin_tenant_toggle(request, tenant_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    if request.method != "POST":
        return redirect("platform_dashboard")

    tenant = get_object_or_404(Tenant, uuid=tenant_id)
    reason = request.POST.get("suspended_reason") or None
    if tenant.is_active:
        tenant.is_active = False
        tenant.suspended_at = dj_timezone.now()
        tenant.suspended_reason = reason or "Suspended by admin"
    else:
        tenant.is_active = True
        tenant.suspended_at = None
        tenant.suspended_reason = None
    tenant.save(update_fields=["is_active", "suspended_at", "suspended_reason"])
    return redirect("platform_dashboard")


@login_required
def admin_tenant_delete(request, tenant_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    if request.method != "POST":
        return redirect("platform_dashboard")

    tenant = get_object_or_404(Tenant, uuid=tenant_id)
    tenant.is_active = False
    tenant.deleted_at = dj_timezone.now()
    tenant.deleted_by = request.user
    if not tenant.suspended_at:
        tenant.suspended_at = dj_timezone.now()
    if not tenant.suspended_reason:
        tenant.suspended_reason = "Soft deleted"
    tenant.save(update_fields=["is_active", "deleted_at", "deleted_by", "suspended_at", "suspended_reason"])
    return redirect("platform_dashboard")


@login_required
def admin_users(request):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    users = User.objects.select_related("tenant").order_by("email")
    reset_notice = request.session.pop("reset_password_notice", None)
    return render(request, "kyc/admin_users.html", {"users": users, "reset_notice": reset_notice})


@login_required
def admin_user_toggle(request, user_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    if request.method != "POST":
        return redirect("admin_users")
    user = get_object_or_404(User, id=user_id)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    return redirect("admin_users")


@login_required
def admin_user_reset_password(request, user_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    if request.method != "POST":
        return redirect("admin_users")
    user = get_object_or_404(User, id=user_id)
    temp_password = _generate_temp_password()
    user.set_password(temp_password)
    user.save(update_fields=["password"])
    request.session["reset_password_notice"] = {
        "email": user.email,
        "password": temp_password,
    }
    return redirect("admin_users")


def _clear_impersonation(request):
    request.session.pop("impersonator_id", None)
    request.session.pop("impersonated_at", None)


def _impersonation_context(request):
    impersonator_id = request.session.get("impersonator_id")
    started_at = request.session.get("impersonated_at")
    if not impersonator_id:
        return {"is_impersonating": False}

    if started_at and (dj_timezone.now().timestamp() - float(started_at)) > 3600:
        _clear_impersonation(request)
        return {"is_impersonating": False}

    try:
        impersonator = User.objects.get(id=impersonator_id)
    except User.DoesNotExist:
        _clear_impersonation(request)
        return {"is_impersonating": False}

    return {
        "is_impersonating": True,
        "impersonator": impersonator,
    }


@login_required
def admin_impersonate(request, tenant_id):
    if not _require_user_type(request.user, {"super_admin"}):
        return _role_denied()
    if request.method != "POST":
        return redirect("platform_dashboard")

    password = request.POST.get("password") or ""
    if not authenticate(request, username=request.user.email, password=password):
        return redirect("platform_dashboard")

    tenant = get_object_or_404(Tenant, uuid=tenant_id)
    target = User.objects.filter(tenant=tenant, role="owner", is_active=True).first()
    if target is None:
        target = User.objects.filter(tenant=tenant, role="admin", is_active=True).first()
    if target is None:
        target = User.objects.filter(tenant=tenant, is_active=True).first()
    if target is None:
        return redirect("platform_dashboard")

    request.session["impersonator_id"] = request.user.id
    request.session["impersonated_at"] = dj_timezone.now().timestamp()
    request.session.set_expiry(3600)
    login(request, target)
    return redirect("tenant_dashboard", tenant_slug=tenant.slug)


@login_required
def admin_stop_impersonation(request):
    impersonator_id = request.session.get("impersonator_id")
    if not impersonator_id:
        return redirect("platform_dashboard")
    try:
        impersonator = User.objects.get(id=impersonator_id)
    except User.DoesNotExist:
        _clear_impersonation(request)
        return redirect("platform_dashboard")

    _clear_impersonation(request)
    login(request, impersonator)
    return redirect("platform_dashboard")


@login_required
def tenant_dashboard(request, tenant_slug):
    if not _require_user_type(request.user, {"owner", "admin", "staff"}):
        return _role_denied()
    if not request.user.tenant:
        return HttpResponseForbidden("No tenant assigned")
    if request.user.tenant.deleted_at or not request.user.tenant.is_active:
        return HttpResponseForbidden("Tenant is inactive")
    if tenant_slug != request.user.tenant.slug:
        return HttpResponseForbidden("Access denied for tenant")
    if request.user.tenant.deleted_at or not request.user.tenant.is_active:
        return HttpResponseForbidden("Tenant is inactive")

    tenant = request.user.tenant
    latest_link = None

    if request.method == "POST" and request.POST.get("action") == "create_customer":
        customer_form = CustomerCreateForm(request.POST)
        if customer_form.is_valid():
            customer = Customer.objects.create(
                tenant=tenant,
                full_name=customer_form.cleaned_data["full_name"],
                email=customer_form.cleaned_data["email"] or None,
                phone=customer_form.cleaned_data["phone"] or None,
                external_ref=customer_form.cleaned_data["external_ref"] or None,
            )
            expires_at = dj_timezone.now() + timedelta(days=2)
            latest_link = VerificationLink.objects.create(
                tenant=tenant,
                customer=customer,
                expires_at=expires_at,
            )
            if customer.email:
                link_url = ""
                public_base = getattr(django_settings, "PUBLIC_BASE_URL", "").rstrip("/")
                if public_base:
                    link_url = f"{public_base}/verify/start/{latest_link.token}/"
                else:
                    link_url = f"{request.scheme}://{request.get_host()}/verify/start/{latest_link.token}/"

                send_mail(
                    subject="Your KYC Verification",
                    message=(
                        f"Hello {customer.full_name},\n\n"
                        f"Please complete your verification using this link:\n{link_url}\n\n"
                        "This link expires in 48 hours."
                    ),
                    from_email=getattr(django_settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[customer.email],
                    fail_silently=True,
                )
    else:
        customer_form = CustomerCreateForm()

    context = {
        "tenant": tenant,
        "session_count": VerificationSession.objects.filter(tenant=tenant).count(),
        "pending_reviews": VerificationSession.objects.filter(tenant=tenant, review_status="pending").count(),
        "customer_form": customer_form,
        "latest_link": latest_link,
        "public_base_url": getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/"),
        "media_url": settings.MEDIA_URL,
        **_impersonation_context(request),
    }
    return render(request, "kyc/tenant_dashboard.html", context)


def _tenant_sessions_panel_context(tenant, request):
    search_query = (request.GET.get("q") or "").strip()
    review_status_filter = (request.GET.get("review_status") or "").strip()

    sessions_qs = VerificationSession.objects.select_related("customer").filter(tenant=tenant)
    if review_status_filter in {"pending", "approved", "rejected", "needs_info"}:
        sessions_qs = sessions_qs.filter(review_status=review_status_filter)
    if search_query:
        sessions_qs = sessions_qs.filter(
            Q(customer__full_name__icontains=search_query) |
            Q(customer__email__icontains=search_query)
        )
    sessions_qs = sessions_qs.order_by("-created_at")

    paginator = Paginator(sessions_qs, 10)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_params = request.GET.copy()
    if "page" in query_params:
        query_params.pop("page")
    if "partial" in query_params:
        query_params.pop("partial")

    return {
        "tenant": tenant,
        "sessions": page_obj.object_list,
        "page_obj": page_obj,
        "search_query": search_query,
        "review_status_filter": review_status_filter,
        "query_string_without_page": query_params.urlencode(),
    }


@login_required
def tenant_sessions(request, tenant_slug):
    if not _require_user_type(request.user, {"owner", "admin", "staff"}):
        return _role_denied()
    if not request.user.tenant:
        return HttpResponseForbidden("No tenant assigned")
    if request.user.tenant.deleted_at or not request.user.tenant.is_active:
        return HttpResponseForbidden("Tenant is inactive")
    if tenant_slug != request.user.tenant.slug:
        return HttpResponseForbidden("Access denied for tenant")

    tenant = request.user.tenant
    context = {
        **_tenant_sessions_panel_context(tenant, request),
        "session_count": VerificationSession.objects.filter(tenant=tenant).count(),
        "pending_reviews": VerificationSession.objects.filter(tenant=tenant, review_status="pending").count(),
        **_impersonation_context(request),
    }
    if request.GET.get("partial") == "sessions" or request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return render(request, "kyc/_tenant_sessions_panel.html", context)
    return render(request, "kyc/tenant_sessions.html", context)


def tenant_dashboard_legacy(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.is_platform_admin():
        return redirect("platform_dashboard")
    if request.user.tenant:
        return redirect("tenant_dashboard", tenant_slug=request.user.tenant.slug)
    return HttpResponseForbidden("No tenant assigned")


class StaffCreateForm(forms.Form):
    email = forms.EmailField()
    role = forms.ChoiceField(choices=[("owner", "Owner"), ("admin", "Admin"), ("staff", "Staff")])
    password = forms.CharField(widget=forms.PasswordInput)


class CustomerCreateForm(forms.Form):
    full_name = forms.CharField(max_length=255)
    email = forms.EmailField(required=False)
    phone = forms.CharField(required=False)
    external_ref = forms.CharField(required=False)


@login_required
def tenant_team(request):
    if not _require_user_type(request.user, {"owner", "admin"}):
        return _role_denied()
    if not request.user.tenant:
        return HttpResponseForbidden("No tenant assigned")

    tenant = request.user.tenant
    staff_qs = User.objects.filter(tenant=tenant).order_by("role", "email")

    if request.method == "POST":
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            role = form.cleaned_data["role"]
            if role == "owner" and request.user.role != "owner":
                return HttpResponseForbidden("Only owners can create other owners.")
            User.objects.create_user(
                email=form.cleaned_data["email"],
                password=form.cleaned_data["password"],
                role=role,
                tenant=tenant,
                is_staff=True,
            )
            return redirect("tenant_team")
    else:
        form = StaffCreateForm()

    context = {
        "tenant": tenant,
        "staff": staff_qs,
        "form": form,
        **_impersonation_context(request),
    }
    return render(request, "kyc/tenant_team.html", context)


@login_required
def customer_start(request):
    if request.method == "POST":
        company_id = request.POST.get("company_id")
        full_name = request.POST.get("full_name")
        email = request.POST.get("email")
        phone = request.POST.get("phone")

        if not company_id or not full_name:
            return render(request, "kyc/customer_start.html", {"error": "Company ID and name are required."})

        try:
            tenant = Tenant.objects.get(slug=company_id)
        except Tenant.DoesNotExist:
            return render(request, "kyc/customer_start.html", {"error": "Company ID not found."})

        customer = Customer.objects.create(
            tenant=tenant,
            full_name=full_name,
            email=email or None,
            phone=phone or None,
        )

        return redirect(f"/verify/?tenant_slug={tenant.slug}&customer_id={customer.id}")

    return render(request, "kyc/customer_start.html")


def customer_verify(request):
    tenant_slug = request.GET.get("tenant_slug")
    customer_id = request.GET.get("customer_id")
    if not tenant_slug or not customer_id:
        return redirect("/customer/start/")
    return render(request, "kyc/index.html", {"tenant_slug": tenant_slug, "customer_id": customer_id})


def bug_liveness_check(request):
    """
    Temporary debug route for liveness flow.
    Creates a throwaway customer when customer_id is not provided.
    """
    tenant_slug = request.GET.get("tenant_slug") or request.GET.get("tenant")
    customer_id = request.GET.get("customer_id")

    if tenant_slug:
        tenant = Tenant.objects.filter(slug=tenant_slug, deleted_at__isnull=True).first()
    else:
        tenant = Tenant.objects.filter(is_active=True, deleted_at__isnull=True).order_by("created_at").first()

    if not tenant:
        return JsonResponse(
            {"success": False, "error": "No active tenant found. Provide ?tenant_slug=<slug>."},
            status=400,
        )

    customer = None
    if customer_id:
        customer = Customer.objects.filter(id=customer_id, tenant=tenant).first()
        if not customer:
            return JsonResponse(
                {"success": False, "error": "customer_id not found for the selected tenant."},
                status=400,
            )
    else:
        stamp = dj_timezone.now().strftime("%Y%m%d%H%M%S")
        customer = Customer.objects.create(
            tenant=tenant,
            full_name=f"Liveness Debug {stamp}",
            email=None,
            phone=None,
        )

    query = {
        "tenant_slug": tenant.slug,
        "customer_id": customer.id,
        "debug": "liveness",
    }
    if str(request.GET.get("autostart", "")).lower() in {"1", "true", "yes"}:
        query["autostart"] = "1"

    return redirect(f"/verify/?{urlencode(query)}")


def verify_link(request, token):
    try:
        link = VerificationLink.objects.select_related("tenant", "customer").get(token=token)
    except VerificationLink.DoesNotExist:
        return HttpResponseForbidden("Invalid or expired link")

    if link.expires_at and link.expires_at < dj_timezone.now():
        return HttpResponseForbidden("Link expired")

    return redirect(f"/verify/?tenant_slug={link.tenant.slug}&customer_id={link.customer.id}")


@login_required
def review_sessions(request):
    tenant_slug = request.GET.get("tenant")
    status = request.GET.get("status")
    review_status = request.GET.get("review_status")

    if not _require_user_type(request.user, {"super_admin", "owner", "admin", "staff"}):
        return _role_denied()

    qs = VerificationSession.objects.select_related("tenant", "reviewed_by", "customer").order_by("-created_at")

    user_tenant = _get_user_tenant(request.user)
    if not request.user.is_superuser:
        if user_tenant is None:
            return HttpResponseForbidden("No tenant membership")
        qs = qs.filter(tenant=user_tenant)
    elif tenant_slug:
        qs = qs.filter(tenant__slug=tenant_slug)

    if status:
        qs = qs.filter(status=status)
    if review_status:
        qs = qs.filter(review_status=review_status)

    context = {
        "sessions": qs[:200],
        "tenant_slug": tenant_slug or "",
        "status": status or "",
        "review_status": review_status or "",
        "is_superuser": request.user.is_superuser,
        "user_tenant": user_tenant,
        **_impersonation_context(request),
    }
    return render(request, "kyc/admin_sessions.html", context)


@login_required
def review_session_detail(request, session_id):
    session = get_object_or_404(
        VerificationSession.objects.select_related("tenant", "reviewed_by", "customer"), id=session_id
    )

    if not _require_user_type(request.user, {"super_admin", "owner", "admin", "staff"}):
        return _role_denied()

    user_tenant = _get_user_tenant(request.user)
    if not request.user.is_superuser:
        if user_tenant is None:
            return HttpResponseForbidden("No tenant membership")
        if session.tenant_id != user_tenant.id:
            return HttpResponseForbidden("Access denied for tenant")

    if request.method == "POST":
        session.review_status = request.POST.get("review_status", session.review_status)
        session.review_notes = request.POST.get("review_notes", session.review_notes)
        session.reviewed_by = request.user
        session.reviewed_at = datetime.now(timezone.utc)
        session.save(update_fields=["review_status", "review_notes", "reviewed_by", "reviewed_at"])
        return redirect("review_session_detail", session_id=session.id)

    context = {
        "session": session,
        "customer": session.customer,
        "front_url": _media_url(session.document_front_url or session.front_image),
        "back_url": _media_url(session.document_back_url or session.back_image),
        "thickness_url": _media_url(session.thickness_card or ((session.tilt_frames or [None])[-1] if session.tilt_frames else None)),
        "selfie_url": _media_url(session.selfie_url or session.selfie_image),
        **_impersonation_context(request),
    }
    if request.user.is_superuser:
        context["back_link"] = redirect("review_sessions").url
    else:
        context["back_link"] = redirect("tenant_dashboard", tenant_slug=request.user.tenant.slug).url
    return render(request, "kyc/admin_session_detail.html", context)


@csrf_exempt
def start_liveness(request):
    """
    Marks liveness as started for the session.
    Endpoint: /start-liveness/
    """
    if request.method == 'POST':
        try:
            data = json.loads(request.body or "{}")
            session_id = data.get("session_id")

            if session_id:
                try:
                    session = VerificationSession.objects.get(id=session_id)
                    session.liveness_running = True
                    session.updated_at = datetime.now(timezone.utc)
                    session.save(update_fields=["liveness_running", "updated_at"])
                except VerificationSession.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'error': 'Session not found'
                    }, status=404)

            return JsonResponse({
                'success': True,
                'message': 'Liveness detection started'
            })

        except Exception as e:
            print(f"❌ Error starting liveness: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': f'Failed to start liveness detection: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method. Use POST.'
    }, status=405)


@csrf_exempt
def check_liveness(request):
    """
    Polls for liveness detection results
    Endpoint: /check-liveness/
    """
    try:
        result_file = 'liveness_result.json'

        # Check if the result file exists
        if os.path.exists(result_file):
            print(f"✓ Found liveness result file")

            # Read the result
            with open(result_file, 'r') as f:
                result = json.load(f)

            print(f"Liveness result: {result}")

            # Clean up the file after reading
            try:
                os.remove(result_file)
                print("✓ Liveness result file cleaned up")
            except Exception as e:
                print(f"⚠️ Could not remove result file: {e}")

            return JsonResponse({
                'completed': True,
                'verified': result.get('verified', False),
                'confidence': result.get('confidence', 0),
                'challenges': result.get('challenges', {}),
                'timestamp': result.get('timestamp', time.time())
            })
        else:
            # Still processing
            return JsonResponse({
                'completed': False,
                'message': 'Liveness detection in progress...'
            })

    except json.JSONDecodeError as e:
        print(f"❌ JSON decode error: {str(e)}")
        return JsonResponse({
            'completed': False,
            'error': f'Invalid JSON in result file: {str(e)}'
        }, status=500)

    except Exception as e:
        print(f"❌ Error checking liveness: {str(e)}")
        import traceback
        traceback.print_exc()
        return JsonResponse({
            'completed': False,
            'error': f'Failed to check liveness status: {str(e)}'
        }, status=500)


@csrf_exempt
def cancel_liveness(request):
    """
    Cancels the running liveness detection process
    Endpoint: /cancel-liveness/
    """
    global liveness_process

    if request.method == 'POST':
        try:
            # Terminate the process if it's running
            if liveness_process and liveness_process.poll() is None:
                liveness_process.terminate()
                try:
                    liveness_process.wait(timeout=5)
                    print("✓ Liveness process terminated gracefully")
                except subprocess.TimeoutExpired:
                    liveness_process.kill()
                    print("⚠️ Liveness process killed forcefully")
            else:
                print("⚠️ No active liveness process to cancel")

            # Clean up result file
            result_file = 'liveness_result.json'
            if os.path.exists(result_file):
                os.remove(result_file)
                print("✓ Cleaned up liveness result file")

            return JsonResponse({
                'success': True,
                'message': 'Liveness detection cancelled'
            })

        except Exception as e:
            print(f"❌ Error cancelling liveness: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': f'Failed to cancel liveness: {str(e)}'
            }, status=500)

    return JsonResponse({
        'success': False,
        'error': 'Invalid request method. Use POST.'
    }, status=405)


@csrf_exempt
def capture_document(request):
    """Handle document capture from camera"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            image_data = data.get('image')
            doc_type = data.get('type')

            if not image_data or not doc_type:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing image data or document type'
                }, status=400)

            # Decode base64 image
            image_data = image_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)

            # Convert to numpy array for OpenCV
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            # Basic quality checks
            quality_check = check_image_quality(img)
            if not quality_check['passed']:
                return JsonResponse({
                    'success': False,
                    'error': quality_check['message']
                }, status=400)

            # Save image
            os.makedirs('documents/captured', exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"documents/captured/{doc_type}_{timestamp}.jpg"

            # Save with higher quality for better face detection
            cv2.imwrite(filename, img, [cv2.IMWRITE_JPEG_QUALITY, 95])

            print(f"✓ Saved {doc_type}: {filename}")

            return JsonResponse({
                'success': True,
                'filename': filename,
                'type': doc_type,
                'quality': quality_check
            })

        except Exception as e:
            print(f"❌ Capture error: {str(e)}")
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only POST requests allowed'}, status=400)


@csrf_exempt
def verify_kyc(request):
    """Process complete KYC verification"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            session_id = data.get('session_id')
            tenant = _resolve_tenant(data)
            front_path = data.get('front_image')
            back_path = data.get('back_image')
            selfie_path = data.get('selfie_image')
            tilt_images = data.get('tilt_images') or []
            liveness_verified = data.get('liveness_verified', False)  # NEW: Get liveness status

            print(f"\n{'=' * 70}")
            print("Starting KYC Verification...")
            print(f"Front: {front_path}")
            print(f"Back: {back_path}")
            print(f"Selfie: {selfie_path}")
            print(f"Tilt frames: {len(tilt_images)}")
            print(f"Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
            print(f"{'=' * 70}\n")

            if session_id and tenant is None:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing or invalid tenant'
                }, status=400)

            if not front_path or not selfie_path:
                return JsonResponse({
                    'success': False,
                    'error': 'Missing required images (front and selfie)'
                }, status=400)

            # Check if files exist
            front_path = _resolve_media_path(front_path)
            back_path = _resolve_media_path(back_path)
            selfie_path = _resolve_media_path(selfie_path)
            tilt_paths = [_resolve_media_path(path) for path in tilt_images if path]

            card_detection = None
            if session_id and tenant is not None:
                session_for_card = VerificationSession.objects.filter(id=session_id, tenant=tenant).first()
                if session_for_card:
                    session_tilt = session_for_card.tilt_frames or []
                    if tilt_images and not session_tilt:
                        session_for_card.tilt_frames = tilt_images
                        session_for_card.save(update_fields=["tilt_frames"])
                        session_tilt = tilt_images
                    for p in session_tilt:
                        rp = _resolve_media_path(p)
                        if rp and rp not in tilt_paths:
                            tilt_paths.append(rp)
                    thickness_path = _resolve_media_path(session_for_card.thickness_card)
                    if thickness_path and thickness_path not in tilt_paths:
                        tilt_paths.append(thickness_path)
                    if session_for_card.document_type:
                        card_detection = {
                            "document_type": session_for_card.document_type,
                            "label": {
                                "driver_license": "Driver License",
                                "my_number": "My Number Card",
                                "passport": "Passport",
                                "residence_card": "Residence Card",
                            }.get(session_for_card.document_type, session_for_card.document_type),
                        }

            if not os.path.exists(front_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Front image not found: {front_path}'
                }, status=400)

            if not os.path.exists(selfie_path):
                return JsonResponse({
                    'success': False,
                    'error': f'Selfie image not found: {selfie_path}'
                }, status=400)

            # Import DeepFace here
            from deepface import DeepFace

            print("Step 1: Extracting face from ID card...")

            # Extract face from ID card
            try:
                faces = DeepFace.extract_faces(
                    img_path=front_path,
                    detector_backend='opencv',
                    enforce_detection=False,
                    align=True
                )

                if not faces or len(faces) == 0:
                    print("❌ No face detected in ID card")
                    return JsonResponse({
                        'success': False,
                        'error': 'No face found in ID card. Please ensure the photo on the ID is clear and visible.'
                    }, status=400)

                print(f"✓ Found {len(faces)} face(s) in ID")

                # Get the largest face
                largest_face = max(faces, key=lambda x: x['facial_area']['w'] * x['facial_area']['h'])

                # Save extracted face
                doc_image = cv2.imread(front_path)
                facial_area = largest_face['facial_area']
                x, y, w, h = facial_area['x'], facial_area['y'], facial_area['w'], facial_area['h']

                # Add padding
                padding = 20
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(doc_image.shape[1] - x, w + 2 * padding)
                h = min(doc_image.shape[0] - y, h + 2 * padding)

                id_face = doc_image[y:y + h, x:x + w]

                # Save derived face crop under MEDIA_ROOT for consistent runtime storage.
                extracted_faces_dir = os.path.join(settings.MEDIA_ROOT, "extracted_faces")
                os.makedirs(extracted_faces_dir, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                id_face_path = os.path.join(extracted_faces_dir, f"id_face_{timestamp}.jpg")
                cv2.imwrite(id_face_path, id_face, [cv2.IMWRITE_JPEG_QUALITY, 95])

                print(f"✓ Extracted ID face: {id_face_path}")

            except Exception as e:
                print(f"❌ Face extraction failed: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Could not extract face from ID: {str(e)}'
                }, status=400)

            print("\nStep 2: Comparing faces...")

            # Compare faces
            try:
                models = ["VGG-Face", "Facenet"]
                results = []

                for model in models:
                    print(f"Running {model}...")
                    result = DeepFace.verify(
                        img1_path=id_face_path,
                        img2_path=selfie_path,
                        model_name=model,
                        enforce_detection=False
                    )

                    distance = result['distance']
                    similarity = (1 - distance) * 100
                    verified = result['verified']

                    results.append({
                        'model': model,
                        'similarity': similarity,
                        'verified': verified,
                        'distance': distance
                    })

                    status = "✓ MATCH" if verified else "✗ NO MATCH"
                    print(f"  {model}: {similarity:.1f}% - {status}")

                # Calculate final decision
                votes_yes = sum(1 for r in results if r['verified'])
                avg_similarity = sum(r['similarity'] for r in results) / len(results)
                final_match = votes_yes >= 1  # At least 1 model says match

                print(f"\n{'=' * 70}")
                print(f"VERIFICATION RESULT:")
                print(f"  Average Similarity: {avg_similarity:.1f}%")
                print(f"  Models Agree: {votes_yes}/{len(results)}")
                print(f"  Liveness: {'✓ Verified' if liveness_verified else '✗ Not verified'}")
                print(f"  Final Decision: {'✅ VERIFIED' if final_match else '❌ REJECTED'}")
                print(f"{'=' * 70}\n")

                result_payload = {
                    'success': True,
                    'verified': final_match,
                    'similarity': avg_similarity,
                    'confidence': avg_similarity,
                    'votes': votes_yes,
                    'total_models': len(results),
                    'liveness_verified': liveness_verified,  # NEW: Include liveness status
                    'details': {
                        'id_face_path': id_face_path,
                        'models': results,
                        'liveness_status': 'verified' if liveness_verified else 'skipped',
                    }
                }

                physical_result = analyze_card_physicality(tilt_paths)
                result_payload["physical_card_check"] = physical_result
                if card_detection:
                    result_payload["detected_card"] = card_detection
                result_payload["details"]["tilt_frames_used"] = physical_result.get("frames_used", 0)

                if session_id:
                    _update_session_verification(
                        session_id=session_id,
                        tenant=tenant,
                        verified=final_match,
                        confidence=avg_similarity,
                        similarity=avg_similarity,
                        liveness_verified=liveness_verified,
                        physical_result=physical_result,
                        card_detection=card_detection,
                    )

                return JsonResponse(result_payload)

            except Exception as e:
                print(f"❌ Face comparison failed: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Face comparison failed: {str(e)}'
                }, status=500)

        except Exception as e:
            print(f"❌ Verification error: {str(e)}")
            import traceback
            traceback.print_exc()
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'error': 'Only POST requests allowed'}, status=400)


def _resolve_media_path(path_or_name):
    if not path_or_name:
        return path_or_name
    if os.path.exists(path_or_name):
        return path_or_name
    media_path = os.path.join(settings.MEDIA_ROOT, path_or_name)
    if os.path.exists(media_path):
        return media_path

    # Backward-compatibility during MEDIA_ROOT migration (legacy files in kyc/uploads).
    legacy_media_path = os.path.join(settings.BASE_DIR, "kyc", "uploads", path_or_name)
    if os.path.exists(legacy_media_path):
        return legacy_media_path

    return media_path


def _media_url(filename):
    if not filename:
        return ""
    return f"{settings.MEDIA_URL}{filename}"


def _get_user_tenant(user):
    if not user.is_authenticated:
        return None
    return user.tenant


def _update_session_verification(
    session_id,
    tenant,
    verified,
    confidence,
    similarity,
    liveness_verified,
    physical_result=None,
    card_detection=None,
):
    try:
        if tenant is None:
            return
        session = VerificationSession.objects.get(id=session_id, tenant=tenant)
    except VerificationSession.DoesNotExist:
        return

    session.verify_verified = bool(verified)
    session.verify_confidence = float(confidence or 0)
    session.verify_similarity = float(similarity or 0)
    session.liveness_verified = bool(liveness_verified)
    if physical_result:
        session.physical_card_verified = bool(physical_result.get("verified"))
        session.physical_card_score = float(physical_result.get("physical_card_score") or 0)
        session.edge_consistency_score = float(physical_result.get("edge_consistency_score") or 0)
        session.depth_variation_score = float(physical_result.get("depth_variation_score") or 0)
        session.tilt_analysis = physical_result
    if card_detection:
        session.detected_card_type = card_detection.get("label")
    session.updated_at = datetime.now(timezone.utc)
    session.save(update_fields=[
        "verify_verified",
        "verify_confidence",
        "verify_similarity",
        "liveness_verified",
        "physical_card_verified",
        "physical_card_score",
        "edge_consistency_score",
        "depth_variation_score",
        "tilt_analysis",
        "detected_card_type",
        "updated_at",
    ])


def _resolve_tenant(data):
    tenant_id = data.get("tenant_id")
    tenant_slug = data.get("tenant_slug")
    if not tenant_id and not tenant_slug:
        return None
    try:
        if tenant_id:
            return Tenant.objects.get(id=tenant_id)
        return Tenant.objects.get(slug=tenant_slug)
    except Tenant.DoesNotExist:
        return None


def check_image_quality(img):
    """Check if image quality is acceptable"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)

    if brightness < 40:
        return {
            'passed': False,
            'message': 'Image too dark. Please ensure good lighting.',
            'brightness': float(brightness)
        }

    if brightness > 220:
        return {
            'passed': False,
            'message': 'Image too bright. Reduce lighting or avoid glare.',
            'brightness': float(brightness)
        }

    # Check for blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()

    if laplacian_var < 50:  # Lowered threshold for mobile cameras
        return {
            'passed': False,
            'message': 'Image is blurry. Please hold steady and focus.',
            'sharpness': float(laplacian_var)
        }

    return {
        'passed': True,
        'message': 'Image quality is good',
        'brightness': float(brightness),
        'sharpness': float(laplacian_var)
    }
