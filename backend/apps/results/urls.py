from django.urls import path

from .views import (
    StudentResultsAPIView,
    StudentResultDetailAPIView,
)


urlpatterns = [
    path(
        "results/",
        StudentResultsAPIView.as_view(),
        name="student-results",
    ),
    path(
        "results/<uuid:result_id>/",
        StudentResultDetailAPIView.as_view(),
        name="student-result-detail",
    ),
]