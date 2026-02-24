from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from accounts.views import home_redirect
from kyc import views as kyc_views

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("", home_redirect, name="home"),
    path("admin/dashboard/", kyc_views.platform_dashboard, name="platform_dashboard"),
    path("admin/tenants/<uuid:tenant_id>/", kyc_views.admin_tenant_detail, name="admin_tenant_detail"),
    path("admin/tenants/<uuid:tenant_id>/edit/", kyc_views.admin_tenant_edit, name="admin_tenant_edit"),
    path("admin/tenants/<uuid:tenant_id>/toggle/", kyc_views.admin_tenant_toggle, name="admin_tenant_toggle"),
    path("admin/tenants/<uuid:tenant_id>/delete/", kyc_views.admin_tenant_delete, name="admin_tenant_delete"),
    path("admin/tenants/<uuid:tenant_id>/impersonate/", kyc_views.admin_impersonate, name="admin_impersonate"),
    path("admin/impersonation/stop/", kyc_views.admin_stop_impersonation, name="admin_stop_impersonation"),
    path("admin/users/", kyc_views.admin_users, name="admin_users"),
    path("admin/users/<int:user_id>/toggle/", kyc_views.admin_user_toggle, name="admin_user_toggle"),
    path("admin/users/<int:user_id>/reset-password/", kyc_views.admin_user_reset_password, name="admin_user_reset_password"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("", include("kyc.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
