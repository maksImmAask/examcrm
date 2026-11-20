
from django.conf import settings
from django.core.exceptions import ValidationError
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
    )

    title = models.CharField(
        max_length=500,
        verbose_name="Текст вопроса",
    )

    question_type = models.CharField(
        max_length=30,
        choices=QuestionType.choices,
        verbose_name="Тип вопроса",
    )

    points = models.PositiveIntegerField(
        default=1,
        verbose_name="Баллы",
    )

    explanation = models.TextField(
        blank=True,
        verbose_name="Объяснение ответа",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"

    def __str__(self):
        return self.title


class QuestionOption(models.Model):

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="options",
        verbose_name="Вопрос",
    )

    text = models.CharField(
        max_length=1000,
        verbose_name="Текст варианта",
    )

    is_correct = models.BooleanField(
        default=False,
        verbose_name="Правильный ответ",
    )

    order = models.PositiveIntegerField(
        default=0,
        verbose_name="Порядок",
    )

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"

    def __str__(self):
        return self.text
