
from rest_framework.permissions import BasePermission


class QuestionPermission(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in ["admin", "teacher"]
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "admin":
            return True

        if user.role == "teacher":
            return obj.teacher_id == user.id

        return False
