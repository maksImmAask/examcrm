
from django.contrib import admin

from .models import Attempt


@admin.register(Attempt)
class AttemptAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "get_student",
        "get_exam",
        "status",
        "started_at",
        "deadline_at",
        "finished_at",
        "finish_reason",
    )

    list_filter = (
        "status",
        "finish_reason",
        "started_at",
    )

    search_fields = (
        "assignment__student__username",
        "assignment__student__first_name",
        "assignment__student__last_name",
        "assignment__publication__name",
    )

    readonly_fields = (
        "id",
        "assignment",
        "status",
        "started_at",
        "deadline_at",
        "finished_at",
        "finish_reason",
        "event_version",
        "created_at",
        "updated_at",
    )

    ordering = ("-started_at",)

    def get_student(self, obj):
        return obj.assignment.student

    get_student.short_description = "Студент"

    def get_exam(self, obj):
        return obj.assignment.publication.name

    get_exam.short_description = "Экзамен"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
