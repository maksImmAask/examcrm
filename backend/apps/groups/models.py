
from django.conf import settings
from django.db import models


class StudyGroup(models.Model):
    name = models.CharField(
        max_length=150,
        verbose_name="Название группы",
    )

    description = models.TextField(
        blank=True,
        verbose_name="Описание",
    )

    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="teaching_groups",
        limit_choices_to={"role__in": ["teacher", "admin"]},
        verbose_name="Преподаватель",
    )

    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="study_groups",
        limit_choices_to={"role": "student"},
        verbose_name="Студенты",
    )

    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Учебная группа"
        verbose_name_plural = "Учебные группы"

    def __str__(self):
        return self.name
