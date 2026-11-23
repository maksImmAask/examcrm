from django.contrib import admin

from .models import ExamResult


@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):

    list_display = [
        "id",
        "attempt",
        "total_points",
        "earned_points",
        "percentage",
        "is_passed",
        "status",
        "released_at",
    ]

    list_filter = [
        "status",
        "is_passed",
    ]

    search_fields = [
        "attempt__assignment__student__username",
        "attempt__assignment__publication__name",
    ]

    readonly_fields = [
        "attempt",
        "total_points",
        "earned_points",
        "percentage",
        "is_passed",
        "calculated_at",
        "released_at",
        "released_by",
        "created_at",
        "updated_at",
    ]

    def has_delete_permission(self, request, obj=None):
        return False