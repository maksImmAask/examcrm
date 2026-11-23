from django.shortcuts import render

# Create your views here.
from django.db.models import Q

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import APIException, PermissionDenied
from rest_framework import status

from .models import Grade
from .serializers import (
    PendingGradeSerializer,
    GradeTextAnswerSerializer,
)
from .services import (
    GradingError,
    grade_text_answer,
    release_exam_result,
)


class GradingAPIException(APIException):

    def __init__(self, error):
        self.status_code = error.status_code

        super().__init__(
            detail={
                "code": error.code,
                "detail": error.detail,
            }
        )


class TeacherGradingAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def check_teacher(self, user):
        if not user.is_active or user.role != "teacher":
            raise PermissionDenied(
                "Доступ разрешён только преподавателям."
            )

    def get(self, request):
        self.check_teacher(request.user)

        grades = (
            Grade.objects
            .filter(
                status=Grade.Status.PENDING,
                grading_type=Grade.GradingType.MANUAL,
                answer__question__question_type="text",
                answer__attempt__assignment__publication__exam__owner=request.user,
            )
            .select_related(
                "answer",
                "answer__attempt",
                "answer__attempt__assignment",
                "answer__attempt__assignment__student",
                "answer__attempt__assignment__publication",
                "answer__question",
            )
            .order_by("created_at")
        )

        serializer = PendingGradeSerializer(
            grades,
            many=True,
        )

        return Response(serializer.data)


class GradeTextAnswerAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, grade_id):
        if (
            not request.user.is_active
            or request.user.role != "teacher"
        ):
            raise PermissionDenied(
                "Доступ разрешён только преподавателям."
            )

        serializer = GradeTextAnswerSerializer(
            data=request.data,
        )

        serializer.is_valid(raise_exception=True)

        try:
            grade_text_answer(
                grade_id=grade_id,
                teacher=request.user,
                points_awarded=serializer.validated_data[
                    "points_awarded"
                ],
                feedback=serializer.validated_data.get(
                    "feedback",
                    "",
                ),
            )
        except GradingError as error:
            raise GradingAPIException(error)

        grade = Grade.objects.select_related(
            "answer",
            "answer__question",
        ).get(pk=grade_id)

        return Response(
            PendingGradeSerializer(grade).data,
            status=status.HTTP_200_OK,
        )


class ReleaseExamResultAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, result_id):
        if (
            not request.user.is_active
            or request.user.role != "teacher"
        ):
            raise PermissionDenied(
                "Доступ разрешён только преподавателям."
            )

        try:
            result = release_exam_result(
                result_id=result_id,
                teacher=request.user,
            )
        except GradingError as error:
            raise GradingAPIException(error)

        from apps.results.serializers import ExamResultSerializer

        return Response(
            ExamResultSerializer(result).data,
            status=status.HTTP_200_OK,
        )