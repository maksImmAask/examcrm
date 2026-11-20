
from django.db import transaction
from rest_framework import serializers

from apps.users.models import User
from .models import Question, QuestionOption


class QuestionOptionSerializer(serializers.ModelSerializer):

    class Meta:
        model = QuestionOption
        fields = [
            "id",
            "text",
            "is_correct",
            "order",
        ]
        read_only_fields = ["id"]


class QuestionSerializer(serializers.ModelSerializer):

    options = QuestionOptionSerializer(
        many=True,
        required=False,
    )

    teacher_name = serializers.CharField(
        source="teacher.username",
        read_only=True,
    )

    class Meta:
        model = Question
        fields = [
            "id",
            "teacher",
            "teacher_name",
            "title",
            "question_type",
            "points",
            "explanation",
            "options",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
        ]

    def validate_points(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Количество баллов должно быть не меньше 1."
            )
        return value

    def validate(self, attrs):
        question_type = attrs.get(
            "question_type",
            getattr(
                self.instance,
                "question_type",
                None,
            ),
        )

        options_data = attrs.get("options")

        if options_data is None:
            if self.instance:
                options_data = list(
                    self.instance.options.values(
                        "text",
                        "is_correct",
                        "order",
                    )
                )
            else:
                options_data = []

        correct_count = sum(
            1 for option in options_data
            if option.get("is_correct", False)
        )

        if question_type == Question.QuestionType.SINGLE_CHOICE:
            if len(options_data) < 2:
                raise serializers.ValidationError({
                    "options": "Добавьте минимум два варианта ответа."
                })

            if correct_count != 1:
                raise serializers.ValidationError({
                    "options": "Должен быть ровно один правильный вариант."
                })

        elif question_type == Question.QuestionType.MULTIPLE_CHOICE:
            if len(options_data) < 2:
                raise serializers.ValidationError({
                    "options": "Добавьте минимум два варианта ответа."
                })

            if correct_count < 1:
                raise serializers.ValidationError({
                    "options": "Укажите хотя бы один правильный вариант."
                })

        elif question_type == Question.QuestionType.TEXT:
            if options_data:
                raise serializers.ValidationError({
                    "options": "Текстовый вопрос не должен иметь вариантов."
                })

        if options_data:
            texts = [
                option.get("text", "").strip().casefold()
                for option in options_data
            ]

            if any(not text for text in texts):
                raise serializers.ValidationError({
                    "options": "Текст варианта не может быть пустым."
                })

            if len(texts) != len(set(texts)):
                raise serializers.ValidationError({
                    "options": "Варианты ответов не должны повторяться."
                })

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        options_data = validated_data.pop("options", [])

        question = Question.objects.create(
            **validated_data
        )

        QuestionOption.objects.bulk_create([
            QuestionOption(
                question=question,
                **option_data,
            )
            for option_data in options_data
        ])

        return question

    @transaction.atomic
    def update(self, instance, validated_data):
        options_data = validated_data.pop(
            "options",
            None,
        )

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        if options_data is not None:
            instance.options.all().delete()

            QuestionOption.objects.bulk_create([
                QuestionOption(
                    question=instance,
                    **option_data,
                )
                for option_data in options_data
            ])

        return instance

    def validate_teacher(self, value):
        if value.role not in [
            User.Role.TEACHER,
            User.Role.ADMIN,
        ]:
            raise serializers.ValidationError(
                "Автором вопроса должен быть преподаватель или администратор."
            )

        return value
