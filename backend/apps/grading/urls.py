from django.urls import path

from .views import (
    TeacherGradingAPIView,
    GradeTextAnswerAPIView,
    ReleaseExamResultAPIView,
)


urlpatterns = [
    path(
        "grading/pending/",
        TeacherGradingAPIView.as_view(),
        name="grading-pending",
    ),
    path(
        "grading/<uuid:grade_id>/",
        GradeTextAnswerAPIView.as_view(),
        name="grading-grade",
    ),
    path(
        "results/<uuid:result_id>/release/",
        ReleaseExamResultAPIView.as_view(),
        name="result-release",
    ),
]