
from django.contrib import admin

from .models import Answer, IdempotencyRecord


@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "get_student",
        "get_exam",
        "get_question",
        "revision",
        "updated_at",
    )

    search_fields = (
        "attempt__assignment__student__username",
        "attempt__assignment__publication__name",
        "question__title",
    )

    list_filter = (
        "updated_at",
    )

    readonly_fields = (
        "id",
        "attempt",
        "question",
        "value",
        "revision",
        "created_at",
        "updated_at",
    )

    def get_student(self, obj):
        return obj.attempt.assignment.student

    get_student.short_description = "Студент"

    def get_exam(self, obj):
        return obj.attempt.assignment.publication.name

    get_exam.short_description = "Экзамен"

    def get_question(self, obj):
        return obj.question.title

    get_question.short_description = "Вопрос"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "operation",
        "resource_id",
        "key",
        "created_at",
    )

    search_fields = (
        "user__username",
        "operation",
        "resource_id",
    )

    list_filter = (
        "operation",
        "created_at",
    )

    readonly_fields = (
        "id",
        "user",
        "operation",
        "resource_id",
        "key",
        "request_hash",
        "response_data",
        "response_status",
        "created_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
