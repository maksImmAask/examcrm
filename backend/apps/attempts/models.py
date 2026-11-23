
import uuid

from django.db import models
from django.db.models import F, Q


class Attempt(models.Model):

    class Status(models.TextChoices):
        IN_PROGRESS = "in_progress", "В процессе"
        SUBMITTED = "submitted", "Сдана"

    class FinishReason(models.TextChoices):
        MANUAL = "manual", "Сдана студентом"
        TIMEOUT = "timeout", "Истекло время"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    assignment = models.OneToOneField(
        "exams.ExamAssignment",
        on_delete=models.PROTECT,
        related_name="attempt",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.IN_PROGRESS,
        db_index=True,
    )

    started_at = models.DateTimeField()

    deadline_at = models.DateTimeField(db_index=True)

    finished_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    finalized_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    finish_reason = models.CharField(
        max_length=20,
        choices=FinishReason.choices,
        null=True,
        blank=True,
    )

    event_version = models.PositiveBigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "Попытка экзамена"
        verbose_name_plural = "Попытки экзамена"
        indexes = [
            models.Index(
                fields=["status", "deadline_at"],
                name="attempt_status_deadline_idx",
            ),
            models.Index(
                fields=["started_at"],
                name="attempt_started_at_idx",
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(deadline_at__gt=F("started_at")),
                name="attempt_deadline_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.assignment.student} — {self.assignment.publication.name}"

    @property
    def is_active(self):
        return self.status == self.Status.IN_PROGRESS
