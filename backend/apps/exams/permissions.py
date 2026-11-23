
from rest_framework.permissions import BasePermission, SAFE_METHODS

from .models import Exam


class ExamPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        if not user or not user.is_authenticated:
            return False

        if user.role == "admin":
            return True

        if user.role == "teacher":
            return True

        return False

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "admin":
            return True

        if user.role == "teacher":
            return obj.owner_id == user.id

        return False


class ExamPublicationPermission(BasePermission):

    def has_permission(self, request, view):
        user = request.user

        return (
            user
            and user.is_authenticated
            and user.role in ["admin", "teacher"]
        )

    def has_object_permission(self, request, view, obj):
        user = request.user

        if user.role == "admin":
            return True

        if user.role == "teacher":
            return obj.exam.owner_id == user.id

        return False
