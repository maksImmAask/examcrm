
import uuid

from django.conf import settings
from django.db import models


class Answer(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    attempt = models.ForeignKey(
        "attempts.Attempt",
        on_delete=models.PROTECT,
        related_name="answers",
    )

    question = models.ForeignKey(
        "exams.PublishedQuestion",
        on_delete=models.PROTECT,
        related_name="answers",
    )

    value = models.JSONField(
        null=True,
        blank=True,
    )

    revision = models.PositiveBigIntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["question__position"]
        verbose_name = "Ответ студента"
        verbose_name_plural = "Ответы студентов"
        constraints = [
            models.UniqueConstraint(
                fields=["attempt", "question"],
                name="unique_attempt_question_answer",
            ),
        ]
        indexes = [
            models.Index(
                fields=["attempt", "updated_at"],
                name="answer_attempt_updated_idx",
            ),
        ]

    def __str__(self):
        return f"{self.attempt} — {self.question.position}"

class IdempotencyRecord(models.Model):

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="idempotency_records",
    )

    operation = models.CharField(max_length=100)

    resource_id = models.CharField(max_length=100)

    key = models.UUIDField()

    request_hash = models.CharField(max_length=64)

    response_data = models.JSONField()

    response_status = models.PositiveSmallIntegerField(default=200)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "operation", "resource_id", "key"],
                name="unique_idempotency_scope",
            ),
        ]
        indexes = [
            models.Index(
                fields=["created_at"],
                name="idempotency_created_idx",
            ),
        ]

    def __str__(self):
        return f"{self.operation} — {self.key}"
