
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from apps.groups.models import StudyGroup
from apps.questions.models import Question


class Exam(models.Model):

    class Status(models.TextChoices):
        DRAFT = "draft", "Черновик"
        PUBLISHED = "published", "Опубликован"
        ARCHIVED = "archived", "В архиве"

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_exams",
        limit_choices_to={"role": "teacher"},
        verbose_name="Владелец экзамена",
    )

    name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name="Название",
    )

    instructions = models.TextField(
        blank=True,
        max_length=5000,
        verbose_name="Инструкция",
    )

    opens_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Начало экзамена",
    )

    closes_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Окончание экзамена",
    )

    duration_minutes = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(1),
            MaxValueValidator(180),
        ],
        verbose_name="Длительность в минутах",
    )

    pass_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[
            MinValueValidator(0),
            MaxValueValidator(100),
        ],
        verbose_name="Проходной процент",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
        verbose_name="Статус",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата публикации",
    )

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата архивации",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Экзамен"
        verbose_name_plural = "Экзамены"
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["opens_at", "closes_at"]),
        ]

    def clean(self):
        super().clean()

        if (
            self.opens_at
            and self.closes_at
            and self.opens_at >= self.closes_at
        ):
            raise ValidationError({
                "closes_at": "Окончание должно быть позже начала."
            })

    def __str__(self):
        return self.name or f"Экзамен {self.pk}"


class ExamGroup(models.Model):
    """Группы, выбранные для черновика экзамена."""

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_groups",
    )

    group = models.ForeignKey(
        StudyGroup,
        on_delete=models.PROTECT,
        related_name="exam_links",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Группа экзамена"
        verbose_name_plural = "Группы экзамена"
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "group"],
                name="unique_exam_group",
            ),
        ]

    def __str__(self):
        return f"{self.exam} — {self.group}"


class ExamQuestion(models.Model):
    """Связь вопроса из банка с черновиком экзамена."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    exam = models.ForeignKey(
        Exam,
        on_delete=models.CASCADE,
        related_name="exam_questions",
    )

    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="exam_links",
    )

    position = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(100),
        ],
        verbose_name="Позиция",
    )

    points = models.PositiveSmallIntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(100),
        ],
        verbose_name="Баллы за вопрос",
    )

    class Meta:
        ordering = ["position"]
        verbose_name = "Вопрос экзамена"
        verbose_name_plural = "Вопросы экзамена"
        constraints = [
            models.UniqueConstraint(
                fields=["exam", "question"],
                name="unique_exam_question",
            ),
            models.UniqueConstraint(
                fields=["exam", "position"],
                name="unique_exam_question_position",
            ),
        ]

    def __str__(self):
        return f"{self.exam} — вопрос {self.position}"


class ExamPublication(models.Model):
    """
    Неизменяемый снимок настроек экзамена на момент публикации.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    exam = models.OneToOneField(
        Exam,
        on_delete=models.PROTECT,
        related_name="publication",
    )

    name = models.CharField(max_length=200)

    instructions = models.TextField(
        blank=True,
        max_length=5000,
    )

    opens_at = models.DateTimeField()
    closes_at = models.DateTimeField()

    duration_minutes = models.PositiveSmallIntegerField()
    pass_percent = models.PositiveSmallIntegerField()

    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Публикация экзамена"
        verbose_name_plural = "Публикации экзаменов"

    def __str__(self):
        return f"Снимок: {self.name}"


class PublishedQuestion(models.Model):
    """Копия вопроса, которая больше не зависит от банка вопросов."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    publication = models.ForeignKey(
        ExamPublication,
        on_delete=models.CASCADE,
        related_name="questions",
    )

    source_question = models.ForeignKey(
        Question,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_copies",
    )

    title = models.CharField(max_length=5000)

    question_type = models.CharField(
        max_length=30,
        choices=Question.QuestionType.choices,
    )

    explanation = models.TextField(blank=True)

    position = models.PositiveSmallIntegerField()

    points = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        verbose_name = "Опубликованный вопрос"
        verbose_name_plural = "Опубликованные вопросы"
        constraints = [
            models.UniqueConstraint(
                fields=["publication", "position"],
                name="unique_published_question_position",
            ),
        ]

    def __str__(self):
        return f"{self.publication.name} — вопрос {self.position}"


class PublishedOption(models.Model):
    """Копия варианта ответа, включая ключ правильности."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    question = models.ForeignKey(
        PublishedQuestion,
        on_delete=models.CASCADE,
        related_name="options",
    )

    source_option_id = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    text = models.CharField(max_length=500)

    is_correct = models.BooleanField(default=False)

    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]
        verbose_name = "Опубликованный вариант"
        verbose_name_plural = "Опубликованные варианты"

    def __str__(self):
        return self.text


class ExamAssignment(models.Model):
    """
    Индивидуальное назначение опубликованного экзамена студенту.

    Один студент получает только одно назначение,
    даже если входит в несколько выбранных групп.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    publication = models.ForeignKey(
        ExamPublication,
        on_delete=models.CASCADE,
        related_name="assignments",
    )

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="exam_assignments",
        limit_choices_to={"role": "student"},
    )

    # ID групп, через которые студент получил назначение.
    # Список фиксируется при публикации.
    source_group_ids = models.JSONField(default=list, blank=True)

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Назначение экзамена"
        verbose_name_plural = "Назначения экзамена"
        constraints = [
            models.UniqueConstraint(
                fields=["publication", "student"],
                name="unique_exam_student_assignment",
            ),
        ]
        indexes = [
            models.Index(fields=["student", "assigned_at"]),
        ]

    def __str__(self):
        return f"{self.student} — {self.publication.name}"
