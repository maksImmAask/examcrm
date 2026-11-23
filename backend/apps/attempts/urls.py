
from django.urls import path

from .views import (
    StartAttemptView,
    AttemptDetailView,
    SaveAnswerView,
    SubmitAttemptView,
)


urlpatterns = [
    path(
        "exams/<uuid:exam_id>/attempts/start/",
        StartAttemptView.as_view(),
        name="attempt-start",
    ),
    path(
        "attempts/<uuid:attempt_id>/",
        AttemptDetailView.as_view(),
        name="attempt-detail",
    ),
    path(
        "attempts/<uuid:attempt_id>/answers/<uuid:question_id>/",
        SaveAnswerView.as_view(),
        name="attempt-save-answer",
    ),
    path(
        "attempts/<uuid:attempt_id>/submit/",
        SubmitAttemptView.as_view(),
        name="attempt-submit",
    ),
]
