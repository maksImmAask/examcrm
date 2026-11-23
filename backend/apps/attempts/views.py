
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException, PermissionDenied
from django.utils import timezone
from .models import Attempt
from .services import (
    AttemptFlowError,
    start_attempt,
    get_attempt_for_student,
    get_attempt_snapshot,
    save_answer,
    submit_attempt,
    finalize_attempt_locked,
)
from django.db import transaction
from django.utils import timezone

class AttemptFlowAPIException(APIException):

    def __init__(self, error):
        self.status_code = error.status_code
        self.detail = {
            "code": error.code,
            "detail": error.detail,
            "meta": error.meta,
        }


class StudentAttemptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def check_student(self, request):
        if not request.user.is_active:
            raise PermissionDenied("Аккаунт неактивен.")

        if request.user.role != "student":
            raise PermissionDenied(
                "Эта операция доступна только студентам."
            )


class StartAttemptView(StudentAttemptAPIView):

    def post(self, request, exam_id):
        self.check_student(request)

        try:
            attempt, created = start_attempt(
                exam_id=exam_id,
                student=request.user,
            )
        except AttemptFlowError as error:
            raise AttemptFlowAPIException(error)

        snapshot = get_attempt_snapshot(attempt)

        return Response(
            snapshot,
            status=201 if created else 200,
        )


class AttemptDetailView(StudentAttemptAPIView):

    def get(self, request, attempt_id):
        self.check_student(request)

        try:
            with transaction.atomic():
                attempt = get_attempt_for_student(
                    attempt_id,
                    request.user,
                    lock=True,
                )

                if (
                    attempt.status == Attempt.Status.IN_PROGRESS
                    and timezone.now() >= attempt.deadline_at
                ):
                    finalize_attempt_locked(attempt)

                snapshot = get_attempt_snapshot(attempt)

        except AttemptFlowError as error:
            raise AttemptFlowAPIException(error)

        return Response(snapshot)


class SaveAnswerView(StudentAttemptAPIView):

    def put(self, request, attempt_id, question_id):
        self.check_student(request)

        idempotency_key = request.headers.get(
            "Idempotency-Key"
        )

        if not idempotency_key:
            return Response(
                {
                    "code": "invalid_idempotency_key",
                    "detail": "Передайте заголовок Idempotency-Key.",
                },
                status=400,
            )

        if "value" not in request.data:
            return Response(
                {
                    "code": "validation_error",
                    "detail": "Поле value обязательно. Для очистки передайте null.",
                },
                status=400,
            )

        if "base_revision" not in request.data:
            return Response(
                {
                    "code": "validation_error",
                    "detail": "Поле base_revision обязательно.",
                },
                status=400,
            )

        try:
            result, result_status = save_answer(
                attempt_id=attempt_id,
                question_id=question_id,
                student=request.user,
                value=request.data.get("value"),
                base_revision=request.data.get("base_revision"),
                idempotency_key=idempotency_key,
            )
        except AttemptFlowError as error:
            raise AttemptFlowAPIException(error)

        return Response(result, status=result_status)


class SubmitAttemptView(StudentAttemptAPIView):

    def post(self, request, attempt_id):
        self.check_student(request)

        try:
            result = submit_attempt(
                attempt_id=attempt_id,
                student=request.user,
            )
        except AttemptFlowError as error:
            raise AttemptFlowAPIException(error)

        return Response(result)
