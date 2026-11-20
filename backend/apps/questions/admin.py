
from django.contrib import admin

from .models import Question, QuestionOption


class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    extra = 2


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "title",
        "teacher",
        "question_type",
        "points",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "question_type",
        "is_active",
        "created_at",
    ]

    search_fields = [
        "title",
        "teacher__username",
    ]

    inlines = [
        QuestionOptionInline,
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]
