from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_protect

from kyc.models import Tenant
from .forms import UnifiedLoginForm, TenantStaffCreationForm, TenantSignupForm


@csrf_protect
def login_view(request):
    if request.method == "POST":
        form = UnifiedLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get("username" )
            password = form.cleaned_data.get("password")
            company_id = form.cleaned_data.get("company_id")

            user = authenticate(request, username=username, password=password)
            if user is None:
                return render(request, "registration/login.html", {"form": form, "invalid": True})

            if not user.is_superuser:
                if not user.tenant:
                    return render(request, "registration/login.html", {"form": form, "invalid": True})
                if not company_id or user.tenant.slug != company_id:
                    return render(request, "registration/login.html", {"form": form, "invalid": True})

            login(request, user)

            if user.is_platform_admin():
                return redirect("platform_dashboard")
            return redirect("tenant_dashboard")
    else:
        form = UnifiedLoginForm(request)

    return render(request, "registration/login.html", {"form": form})


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
            return redirect("tenant_dashboard")
    else:
        form = TenantSignupForm()

    return render(request, "registration/signup.html", {"form": form})
