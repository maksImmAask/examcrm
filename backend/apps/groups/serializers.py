
from rest_framework import serializers

from apps.users.models import User
from .models import StudyGroup


class StudyGroupSerializer(serializers.ModelSerializer):
    teacher_name = serializers.CharField(
        source="teacher.get_full_name",
        read_only=True,
    )

    teachers = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role=User.Role.TEACHER),
        many=True,
        required=False,
    )

    teachers_names = serializers.SerializerMethodField()

    students_count = serializers.SerializerMethodField()

    class Meta:
        model = StudyGroup
        fields = [
            "id",
            "name",
            "description",
            "teacher",
            "teacher_name",
            "teachers",
            "teachers_names",
            "students",
            "students_count",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def get_students_count(self, obj):
        return obj.students.count()

    def get_teachers_names(self, obj):
        return [
            user.get_full_name() or user.username
            for user in obj.teachers.all()
        ]

    def validate_teacher(self, value):
        if value.role not in [
            User.Role.TEACHER,
            User.Role.ADMIN,
        ]:
            raise serializers.ValidationError(
                "Основным преподавателем должен быть преподаватель или администратор."
            )

        request = self.context.get("request")

        if (
            request
            and request.user.role == User.Role.TEACHER
            and self.instance
            and value.id != self.instance.teacher_id
        ):
            raise serializers.ValidationError(
                "Нельзя менять основного преподавателя группы."
            )

        return value

    def validate_teachers(self, value):
        for teacher in value:
            if teacher.role != User.Role.TEACHER:
                raise serializers.ValidationError(
                    "В список можно добавлять только преподавателей."
                )

        return value

    def validate_students(self, value):
        for student in value:
            if student.role != User.Role.STUDENT:
                raise serializers.ValidationError(
                    "В группу можно добавлять только студентов."
                )

        return value

    def validate(self, attrs):
        request = self.context.get("request")

        if (
            request
            and request.user.role == User.Role.TEACHER
            and "teachers" in attrs
        ):
            raise serializers.ValidationError({
                "teachers": "Дополнительных преподавателей может назначать только администратор."
            })

        return attrs

    def create(self, validated_data):
        assigned_teachers = validated_data.pop("teachers", [])

        group = StudyGroup.objects.create(**validated_data)

        # Основной преподаватель автоматически добавляется
        # в список преподавателей, если он имеет роль teacher.
        if group.teacher.role == User.Role.TEACHER:
            assigned_teachers.append(group.teacher)

        group.teachers.set(set(assigned_teachers))

        return group

    def update(self, instance, validated_data):
        assigned_teachers = validated_data.pop("teachers", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if assigned_teachers is not None:
            if instance.teacher.role == User.Role.TEACHER:
                assigned_teachers.append(instance.teacher)

            instance.teachers.set(set(assigned_teachers))

        elif instance.teacher.role == User.Role.TEACHER:
            instance.teachers.add(instance.teacher)

        return instance
