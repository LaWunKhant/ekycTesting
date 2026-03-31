from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.http import HttpResponse
from django.middleware.csrf import get_token
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from .forms import UnifiedLoginForm


def health_check(request):
    return HttpResponse("ok", content_type="text/plain")


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

            if not (user.is_superuser or user.role == "super_admin"):
                return _render_login(request, form, portal_title, portal_subtitle, invalid=True)

            login(request, user)
            return redirect("platform_dashboard")
    else:
        form = UnifiedLoginForm(request)

    return _render_login(request, form, portal_title, portal_subtitle)


def home_redirect(request):
    return redirect("login")


def logout_view(request):
    logout(request)
    return redirect("login")


@login_required
@csrf_protect
def password_change_view(request):
    success = False
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            success = True
            form = PasswordChangeForm(request.user)
    else:
        form = PasswordChangeForm(request.user)

    for field in form.fields.values():
        field.widget.attrs.update({
            "class": "mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 focus:border-cyan-500 focus:outline-none",
        })

    next_url = None
    if request.user.is_platform_admin():
        next_url = "platform_dashboard"

    context = {
        "form": form,
        "success": success,
        "next_url_name": next_url,
    }
    return render(request, "registration/password_change.html", context)
