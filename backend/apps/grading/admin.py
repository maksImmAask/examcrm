from django.contrib import admin

from .models import Grade


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "answer",
        "points_awarded",
        "max_points",
        "grading_type",
        "status",
        "graded_by",
        "graded_at",
    ]

    list_filter = [
        "status",
        "grading_type",
        "is_correct",
    ]

    search_fields = [
        "answer__attempt__assignment__student__username",
        "answer__question__title",
    ]

    readonly_fields = [
        "answer",
        "max_points",
        "grading_type",
        "created_at",
        "updated_at",
    ]