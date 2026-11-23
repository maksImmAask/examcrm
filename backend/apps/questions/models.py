
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Question(models.Model):

    class QuestionType(models.TextChoices):
        SINGLE_CHOICE = "single_choice", "Один вариант"
        MULTIPLE_CHOICE = "multiple_choice", "Несколько вариантов"
        TEXT = "text", "Текстовый ответ"

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="questions",
        verbose_name="Автор вопроса",
        limit_choices_to={"role": "teacher"},
    )

    title = models.CharField(
        max_length=5000,
        verbose_name="Текст вопроса",
    )

    question_type = models.CharField(
        max_length=30,
        choices=QuestionType.choices,
    )

    points = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    explanation = models.TextField(
        blank=True,
        max_length=5000,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
        indexes = [
            models.Index(fields=["teacher", "is_active"]),
            models.Index(fields=["question_type", "is_active"]),
        ]

    def __str__(self):
        return self.title


class QuestionOption(models.Model):

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
    )

    text = models.CharField(max_length=500)

    is_correct = models.BooleanField(default=False)

    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "order"],
                name="unique_question_option_order",
            ),
        ]

    def __str__(self):
        return self.text
