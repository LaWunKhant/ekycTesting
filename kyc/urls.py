from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Main page
    path('', views.index, name='index'),
    path('liveness', views.liveness_page, name='liveness_page'),
    path('review/', views.review_sessions, name='review_sessions'),
    path('review/<uuid:session_id>/', views.review_session_detail, name='review_session_detail'),
    path('platform/', views.platform_dashboard, name='platform_dashboard'),
    path('dashboard/', views.tenant_dashboard, name='tenant_dashboard'),
    path('verify/', views.customer_verify, name='customer_verify'),
    path('customer/start/', views.customer_start, name='customer_start'),

    # Session API (Flask parity)
    path('session/start', api_views.start_session, name='start_session'),
    path('session/status/<uuid:session_id>', api_views.session_status, name='session_status'),
    path('liveness-result', api_views.save_liveness_result, name='liveness_result'),
    path('capture/', api_views.capture_image, name='capture_image'),

    # Document capture (legacy UI endpoint)
    path('capture-document/', views.capture_document, name='capture_document'),

    # Liveness detection endpoints (NEW)
    path('start-liveness/', views.start_liveness, name='start_liveness'),
    path('check-liveness/', views.check_liveness, name='check_liveness'),
    path('cancel-liveness/', views.cancel_liveness, name='cancel_liveness'),

    # Final verification
    path('verify/', views.verify_kyc, name='verify_kyc'),
]
