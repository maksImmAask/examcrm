from django.db import models
from django.db.models import F, Q


class ExamResult(models.Model):

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает проверки"
        READY = "ready", "Готов к публикации"
        RELEASED = "released", "Опубликован"

    attempt = models.OneToOneField(
        "attempts.Attempt",
        on_delete=models.PROTECT,
        related_name="result",
    )

    total_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    earned_points = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
    )

    is_passed = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    calculated_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    released_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    released_by = models.ForeignKey(
        "users.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="released_exam_results",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Результат экзамена"
        verbose_name_plural = "Результаты экзаменов"
        constraints = [
            models.CheckConstraint(
                condition=Q(earned_points__gte=0)
                & Q(earned_points__lte=F("total_points")),
                name="result_earned_points_within_limit",
            ),
            models.CheckConstraint(
                condition=Q(percentage__gte=0)
                & Q(percentage__lte=100),
                name="result_percentage_within_limit",
            ),
        ]
        indexes = [
            models.Index(
                fields=["status", "created_at"],
                name="result_status_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.attempt_id}: {self.percentage}%"