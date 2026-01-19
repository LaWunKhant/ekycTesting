from django.urls import path
from . import views

urlpatterns = [
    # Main page
    path('', views.index, name='index'),

    # Document capture
    path('capture/', views.capture_document, name='capture_document'),

    # Liveness detection endpoints (NEW)
    path('start-liveness/', views.start_liveness, name='start_liveness'),
    path('check-liveness/', views.check_liveness, name='check_liveness'),
    path('cancel-liveness/', views.cancel_liveness, name='cancel_liveness'),

    # Final verification
    path('verify/', views.verify_kyc, name='verify_kyc'),
]