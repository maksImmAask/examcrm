from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import get_object_or_404

from .models import ExamResult
from .serializers import ExamResultSerializer


class StudentResultsAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        if (
            not request.user.is_active
            or request.user.role != "student"
        ):
            raise PermissionDenied(
                "Доступ разрешён только студентам."
            )

        results = (
            ExamResult.objects
            .filter(
                attempt__assignment__student=request.user,
                status=ExamResult.Status.RELEASED,
            )
            .select_related(
                "attempt__assignment__publication",
                "attempt__assignment__student",
            )
            .order_by("-released_at")
        )

        serializer = ExamResultSerializer(
            results,
            many=True,
        )

        return Response(serializer.data)


class StudentResultDetailAPIView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, result_id):
        if (
            not request.user.is_active
            or request.user.role != "student"
        ):
            raise PermissionDenied(
                "Доступ разрешён только студентам."
            )

        result = get_object_or_404(
            ExamResult.objects.select_related(
                "attempt__assignment__publication",
                "attempt__assignment__student",
            ),
            pk=result_id,
            attempt__assignment__student=request.user,
            status=ExamResult.Status.RELEASED,
        )

        return Response(
            ExamResultSerializer(result).data,
        )