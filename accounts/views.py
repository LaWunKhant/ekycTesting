from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from kyc.models import Tenant
from .forms import UnifiedLoginForm, TenantStaffCreationForm, TenantSignupForm


def _render_login(request, form, portal_title, portal_subtitle, invalid=False):
    # Force a fresh token into the response context/cookie for this shared login page.
    get_token(request)
    context = {
        "form": form,
        "portal_title": portal_title,
        "portal_subtitle": portal_subtitle,
    }
    if invalid:
        context["invalid"] = True
    return render(request, "registration/login.html", context)


@never_cache
@ensure_csrf_cookie
@csrf_protect
def login_view(request):
    host = request.get_host().split(":")[0]
    portal_title = "MoonKYC Business"
    portal_subtitle = "Sign in to your workspace"
    subdomain = None
    if host.replace(".", "").isdigit() or host in {"localhost"}:
        subdomain = None
    else:
        parts = host.split(".")
        if len(parts) > 2:
            subdomain = parts[0].lower()

    if subdomain == "admin":
        portal_title = "MoonKYC Admin"
        portal_subtitle = "Sign in to the admin console"

    if request.method == "POST":
        form = UnifiedLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username")
            password = form.cleaned_data.get("password")

            user = authenticate(request, username=username, password=password)
            if user is None:
                return _render_login(request, form, portal_title, portal_subtitle, invalid=True)

            if subdomain == "admin" and not user.is_platform_admin():
                return _render_login(request, form, portal_title, portal_subtitle, invalid=True)

            if subdomain and subdomain not in {"admin", "app"}:
                if not user.tenant or user.tenant.slug != subdomain:
                    return _render_login(request, form, portal_title, portal_subtitle, invalid=True)

            if user.tenant and (user.tenant.deleted_at or not user.tenant.is_active):
                return _render_login(request, form, portal_title, portal_subtitle, invalid=True)

            login(request, user)

            if user.is_platform_admin():
                return redirect("platform_dashboard")
            return redirect("tenant_dashboard", tenant_slug=user.tenant.slug)
    else:
        form = UnifiedLoginForm(request)

    return _render_login(request, form, portal_title, portal_subtitle)


def home_redirect(request):
    return redirect("login")


def logout_view(request):
    logout(request)
    return redirect("login")


@csrf_protect
def signup_view(request):
    if request.method == "POST":
        form = TenantSignupForm(request.POST)
        if form.is_valid():
            tenant_name = form.cleaned_data.get("tenant_name")
            tenant_slug = form.cleaned_data.get("tenant_slug")
            tenant = Tenant.objects.create(name=tenant_name, slug=tenant_slug)

            user = form.save(commit=False)
            user.role = "owner"
            user.tenant = tenant
            user.company_id = tenant_slug
            user.is_staff = True
            user.save()
            login(request, user)
            return redirect("tenant_dashboard", tenant_slug=tenant.slug)
    else:
        form = TenantSignupForm()

    return render(request, "registration/signup.html", {"form": form})
