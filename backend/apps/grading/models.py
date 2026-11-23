from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q


class Grade(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает проверки"
        COMPLETED = "completed", "Проверен"

    class GradingType(models.TextChoices):
        AUTOMATIC = "automatic", "Автоматическая"
        MANUAL = "manual", "Ручная"

    answer = models.OneToOneField(
        "answers.Answer",
        on_delete=models.PROTECT,
        related_name="grade",
    )

    points_awarded = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
    )

    max_points = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    is_correct = models.BooleanField(
        null=True,
        blank=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
        db_index=True,
    )

    grading_type = models.CharField(
        max_length=20,
        choices=GradingType.choices,
    )

    feedback = models.TextField(
        blank=True,
        max_length=5000,
    )

    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="graded_answers",
    )

    graded_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Оценка ответа"
        verbose_name_plural = "Оценки ответов"
        constraints = [
            models.CheckConstraint(
                condition=Q(points_awarded__gte=0)
                & Q(points_awarded__lte=F("max_points")),
                name="grade_points_within_limit",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "grading_type"],
                name="grade_status_type_idx",
            ),
        ]

    def __str__(self):
        return f"{self.answer_id}: {self.points_awarded}/{self.max_points}"