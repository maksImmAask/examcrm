
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

from apps.users.models import User
from .models import StudyGroup
from .serializers import StudyGroupSerializer
from .permissions import StudyGroupPermission


class StudyGroupViewSet(viewsets.ModelViewSet):
    serializer_class = StudyGroupSerializer
    permission_classes = [StudyGroupPermission]

    def get_queryset(self):
        user = self.request.user

        queryset = StudyGroup.objects.select_related(
            "teacher"
        ).prefetch_related(
            "students"
        )

        if user.role == User.Role.ADMIN:
            return queryset

        if user.role == User.Role.TEACHER:
            return queryset.filter(teacher=user)

        if user.role == User.Role.STUDENT:
            return queryset.filter(students=user)

        return queryset.none()

    def perform_create(self, serializer):
        user = self.request.user

        if user.role == User.Role.TEACHER:
            serializer.save(teacher=user)
            return

        if user.role == User.Role.ADMIN:
            serializer.save()
            return

        raise PermissionDenied(
            "Студент не может создавать учебные группы."
        )

    def perform_update(self, serializer):
        user = self.request.user

        if user.role == User.Role.TEACHER:
            serializer.save(teacher=user)
            return

        if user.role == User.Role.ADMIN:
            serializer.save()
            return

        raise PermissionDenied(
            "У вас нет прав на изменение группы."
        )

    def perform_destroy(self, instance):
        if self.request.user.role not in [
            User.Role.ADMIN,
            User.Role.TEACHER,
        ]:
            raise PermissionDenied(
                "У вас нет прав на удаление группы."
            )

        instance.delete()
