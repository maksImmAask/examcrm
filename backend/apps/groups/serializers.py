
from rest_framework import serializers

from apps.users.models import User
from .models import StudyGroup


class StudyGroupSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(
        source="teacher.get_full_name",
        read_only=True,
    )

    students_count = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "description",
            "teacher",
            "teacher_name",
            "students",
            "students_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def get_students_count(self, obj):
        return obj.students.count()

    def validate_teacher(self, value):
        if value.role not in [User.Role.TEACHER, User.Role.ADMIN]:
            raise serializers.ValidationError(
                "Пользователь должен быть преподавателем или администратором."
            )
        return value

    def validate_students(self, value):
        for student in value:
            if student.role != User.Role.STUDENT:
                raise serializers.ValidationError(
                    "В группу можно добавлять только студентов."
                )
        return value
