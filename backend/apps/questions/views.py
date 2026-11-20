
from rest_framework import viewsets

from apps.users.models import User
from .models import Question
from .serializers import QuestionSerializer
from .permissions import QuestionPermission


class QuestionViewSet(viewsets.ModelViewSet):

    serializer_class = QuestionSerializer
    permission_classes = [QuestionPermission]

    def get_queryset(self):
        queryset = Question.objects.select_related(
            "teacher"
        ).prefetch_related(
            "options"
        )

        user = self.request.user

        if user.role == User.Role.ADMIN:
            return queryset

        if user.role == User.Role.TEACHER:
            return queryset.filter(teacher=user)

        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == User.Role.TEACHER:
            serializer.save(teacher=user)
        else:
            serializer.save()
    def perform_update(self, serializer):
        user = self.request.user

        if user.role == User.Role.TEACHER:
            serializer.save(teacher=user)
        else:
            serializer.save()