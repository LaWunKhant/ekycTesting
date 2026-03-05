from django.urls import path

from .views import login_view, logout_view, signup_view, password_change_view

urlpatterns = [
    path("login/", login_view, name="login"),
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),
    path("password/change/", password_change_view, name="password_change"),
]
