
from rest_framework.permissions import BasePermission, SAFE_METHODS


class StudyGroupPermission(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "admin":
            return True

        if user.role == "teacher":
            return (
                obj.teacher_id == user.id
                or obj.teachers.filter(id=user.id).exists()
            )

        if user.role == "student":
            return (
                request.method in SAFE_METHODS
                and obj.students.filter(id=user.id).exists()
            )

        return False
