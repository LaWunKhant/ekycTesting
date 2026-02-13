from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect

from kyc.models import Tenant
from .forms import UnifiedLoginForm, TenantStaffCreationForm, TenantSignupForm


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
                return render(
                    request,
                    "registration/login.html",
                    {"form": form, "invalid": True, "portal_title": portal_title, "portal_subtitle": portal_subtitle},
                )

            if subdomain == "admin" and not user.is_platform_admin():
                return render(
                    request,
                    "registration/login.html",
                    {"form": form, "invalid": True, "portal_title": portal_title, "portal_subtitle": portal_subtitle},
                )

            if subdomain and subdomain not in {"admin", "app"}:
                if not user.tenant or user.tenant.slug != subdomain:
                    return render(
                        request,
                        "registration/login.html",
                        {"form": form, "invalid": True, "portal_title": portal_title, "portal_subtitle": portal_subtitle},
                    )

            if user.tenant and (user.tenant.deleted_at or not user.tenant.is_active):
                return render(
                    request,
                    "registration/login.html",
                    {"form": form, "invalid": True, "portal_title": portal_title, "portal_subtitle": portal_subtitle},
                )

            login(request, user)

            if user.is_platform_admin():
                return redirect("platform_dashboard")
            return redirect("tenant_dashboard", tenant_slug=user.tenant.slug)
    else:
        form = UnifiedLoginForm(request)

    return render(
        request,
        "registration/login.html",
        {"form": form, "portal_title": portal_title, "portal_subtitle": portal_subtitle},
    )


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
