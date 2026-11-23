from django.contrib import admin

from .models import (
    Exam,
    ExamGroup,
    ExamQuestion,
    ExamPublication,
    PublishedQuestion,
    PublishedOption,
    ExamAssignment,
)

class ExamGroupInline(admin.TabularInline):
    model = ExamGroup
    extra = 0
    fields = ("group",)

    def has_change_permission(self, request, obj=None):
        if obj and obj.status != Exam.Status.DRAFT:
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status != Exam.Status.DRAFT:
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != Exam.Status.DRAFT:
            return False
        return super().has_delete_permission(request, obj)

class ExamQuestionInline(admin.TabularInline):
    model = ExamQuestion
    extra = 0
    fields = ("question", "position", "points")
    ordering = ("position",)

    def has_change_permission(self, request, obj=None):
        if obj and obj.status != Exam.Status.DRAFT:
            return False
        return super().has_change_permission(request, obj)

    def has_add_permission(self, request, obj=None):
        if obj and obj.status != Exam.Status.DRAFT:
            return False
        return super().has_add_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.status != Exam.Status.DRAFT:
            return False
        return super().has_delete_permission(request, obj)

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "owner",
        "status",
        "opens_at",
        "closes_at",
        "duration_minutes",
        "created_at",
    )

    list_filter = (
        "status",
        "created_at",
    )

    search_fields = (
        "name",
        "owner__username",
        "owner__first_name",
        "owner__last_name",
    )

    ordering = ("-created_at",)

    readonly_fields = (
        "id",
        "published_at",
        "archived_at",
        "created_at",
        "updated_at",
    )

    inlines = (
        ExamGroupInline,
        ExamQuestionInline,
    )

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "id",
                    "owner",
                    "name",
                    "instructions",
                    "status",
                )
            },
        ),
        (
            "Расписание",
            {
                "fields": (
                    "opens_at",
                    "closes_at",
                    "duration_minutes",
                    "pass_percent",
                )
            },
        ),
        (
            "Даты",
            {
                "fields": (
                    "published_at",
                    "archived_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))

        if obj and obj.status != Exam.Status.DRAFT:
            readonly.extend(
                [
                    "owner",
                    "name",
                    "instructions",
                    "status",
                    "opens_at",
                    "closes_at",
                    "duration_minutes",
                    "pass_percent",
                ]
            )

        return tuple(set(readonly))

class ReadOnlySnapshotAdmin(admin.ModelAdmin):

    def get_readonly_fields(self, request, obj=None):
        return tuple(
            field.name
            for field in self.model._meta.concrete_fields
        )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(ExamPublication)
class ExamPublicationAdmin(ReadOnlySnapshotAdmin):
    list_display = (
        "name",
        "exam",
        "opens_at",
        "closes_at",
        "duration_minutes",
        "pass_percent",
        "published_at",
    )

    search_fields = (
        "name",
        "exam__name",
    )

    list_filter = (
        "published_at",
        "opens_at",
        "closes_at",
    )

    ordering = ("-published_at",)

@admin.register(PublishedQuestion)
class PublishedQuestionAdmin(ReadOnlySnapshotAdmin):
    list_display = (
        "title",
        "publication",
        "question_type",
        "position",
        "points",
    )

    list_filter = (
        "question_type",
    )

    search_fields = (
        "title",
        "publication__name",
    )

    ordering = (
        "publication",
        "position",
    )

@admin.register(PublishedOption)
class PublishedOptionAdmin(ReadOnlySnapshotAdmin):
    list_display = (
        "text",
        "question",
        "is_correct",
        "order",
    )

    list_filter = (
        "is_correct",
    )

    search_fields = (
        "text",
        "question__title",
    )

    ordering = (
        "question",
        "order",
    )


@admin.register(ExamAssignment)
class ExamAssignmentAdmin(ReadOnlySnapshotAdmin):
    list_display = (
        "student",
        "publication",
        "assigned_at",
    )

    search_fields = (
        "student__username",
        "student__first_name",
        "student__last_name",
        "publication__name",
    )

    list_filter = (
        "assigned_at",
    )

    ordering = ("-assigned_at",)