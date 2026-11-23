
from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .models import (
    Exam,
    ExamPublication,
    ExamGroup,
    ExamQuestion,
)
from .permissions import ExamPermission
from .serializers import (
    ExamReadSerializer,
    ExamWriteSerializer,
    ExamPublicationSerializer,
)
from .services.publication import (
    publish_exam,
    ExamPublicationError,
)


class ExamViewSet(viewsets.ModelViewSet):
    permission_classes = [ExamPermission]

    def get_queryset(self):
        user = self.request.user

        queryset = Exam.objects.select_related(
            "owner"
        ).prefetch_related(
            Prefetch(
                "exam_groups",
                queryset=ExamGroup.objects.select_related("group"),
            ),
            Prefetch(
                "exam_questions",
                queryset=ExamQuestion.objects.select_related("question"),
            ),
        )

        if user.role == "admin":
            return queryset

        return queryset.filter(owner=user)

    def get_serializer_class(self):
        if self.action in ["list", "retrieve"]:
            return ExamReadSerializer

        return ExamWriteSerializer

    def perform_create(self, serializer):
        serializer.save()

    @action(
        detail=True,
        methods=["post"],
        url_path="publish",
    )
    def publish(self, request, pk=None):
        exam = self.get_object()

        try:
            publication = publish_exam(
                exam_id=exam.pk,
                user=request.user,
            )
        except ExamPublicationError as exc:
            raise ValidationError(exc.args[0])

        return Response(
            {
                "message": "Экзамен опубликован.",
                "publication": ExamPublicationSerializer(
                    publication
                ).data,
            },
            status=status.HTTP_200_OK,
        )


class ExamPublicationViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ExamPublicationSerializer
    permission_classes = [ExamPermission]

    def get_queryset(self):
        user = self.request.user

        queryset = ExamPublication.objects.select_related(
            "exam",
            "exam__owner",
        )

        if user.role == "admin":
            return queryset

        return queryset.filter(exam__owner=user)
