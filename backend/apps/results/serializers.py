from rest_framework import serializers

from .models import ExamResult


class ExamResultSerializer(serializers.ModelSerializer):

    exam_name = serializers.CharField(
        source="attempt.assignment.publication.name",
        read_only=True,
    )

    student_username = serializers.CharField(
        source="attempt.assignment.student.username",
        read_only=True,
    )

    class Meta:
        model = ExamResult
        fields = [
            "id",
            "exam_name",
            "student_username",
            "total_points",
            "earned_points",
            "percentage",
            "is_passed",
            "status",
            "calculated_at",
            "released_at",
        ]
        read_only_fields = fields