from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView,
)

from .views import CurrentUserAPIView


urlpatterns = [
    path(
        "auth/token/",
        TokenObtainPairView.as_view(),
        name="token-obtain",
    ),
    path(
        "auth/token/refresh/",
        TokenRefreshView.as_view(),
        name="token-refresh",
    ),
    path(
        "auth/token/verify/",
        TokenVerifyView.as_view(),
        name="token-verify",
    ),
    path(
        "auth/me/",
        CurrentUserAPIView.as_view(),
        name="current-user",
    ),
]