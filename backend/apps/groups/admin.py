
from django.contrib import admin

from .models import StudyGroup


@admin.register(StudyGroup)
class StudyGroupAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "teacher",
        "is_active",
        "created_at",
    ]

    list_filter = [
        "is_active",
        "created_at",
    ]

    search_fields = [
        "name",
        "teacher__username",
        "teacher__first_name",
        "teacher__last_name",
    ]

    filter_horizontal = [
        "students",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
    ]
