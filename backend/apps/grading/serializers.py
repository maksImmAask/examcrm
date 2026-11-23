from rest_framework import serializers

from .models import Grade


class PendingGradeSerializer(serializers.ModelSerializer):

    student_username = serializers.CharField(
        source="answer.attempt.assignment.student.username",
        read_only=True,
    )

    exam_name = serializers.CharField(
        source="answer.attempt.assignment.publication.name",
        read_only=True,
    )

    question_title = serializers.CharField(
        source="answer.question.title",
        read_only=True,
    )

    question_points = serializers.IntegerField(
        source="max_points",
        read_only=True,
    )

    answer_value = serializers.JSONField(
        source="answer.value",
        read_only=True,
    )

    attempt_id = serializers.UUIDField(
        source="answer.attempt_id",
        read_only=True,
    )

    class Meta:
        model = Grade
        fields = [
            "id",
            "student_username",
            "exam_name",
            "question_title",
            "question_points",
            "answer_value",
            "attempt_id",
            "points_awarded",
            "max_points",
            "status",
            "feedback",
            "created_at",
        ]


class GradeTextAnswerSerializer(serializers.Serializer):

    points_awarded = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0,
    )

    feedback = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=5000,
    )