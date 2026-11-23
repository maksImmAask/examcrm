
from django.db import transaction
from rest_framework import serializers

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

    def validate_text(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Текст варианта не может быть пустым."
            )

        if len(value) > 500:
            raise serializers.ValidationError(
                "Максимальная длина варианта — 500 символов."
            )

        return value


class QuestionSerializer(serializers.ModelSerializer):

    options = QuestionOptionSerializer(
        many=True,
        required=False,
    )

    teacher_username = serializers.CharField(
        source="teacher.username",
        read_only=True,
    )

    class Meta:
        model = Question
        fields = [
            "id",
            "teacher",
            "teacher_username",
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
            "teacher",
            "teacher_username",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value):
        value = value.strip()

        if not value:
            raise serializers.ValidationError(
                "Текст вопроса не может быть пустым."
            )

        if len(value) > 5000:
            raise serializers.ValidationError(
                "Максимальная длина вопроса — 5000 символов."
            )

        return value

    def validate_explanation(self, value):
        if len(value) > 5000:
            raise serializers.ValidationError(
                "Объяснение не может быть длиннее 5000 символов."
            )

        return value

    def validate(self, attrs):
        instance = self.instance

        question_type = attrs.get(
            "question_type",
            instance.question_type if instance else None,
        )
        option_texts = [
            option.get("text", "").strip().casefold()
            for option in options
        ]

        if len(option_texts) != len(set(option_texts)):
            raise serializers.ValidationError(
                {"options": "Тексты вариантов не должны повторяться."}
            )

        if "options" in attrs:
            options = attrs["options"]
        elif instance:
            options = list(
                instance.options.values(
                    "text",
                    "is_correct",
                    "order",
                )
            )
        else:
            options = []

        if question_type == Question.QuestionType.TEXT:
            if options:
                raise serializers.ValidationError(
                    {
                        "options": (
                            "Текстовый вопрос не должен содержать варианты ответов. "
                            "Передайте пустой список options."
                        )
                    }
                )

            return attrs

        if question_type not in [
            Question.QuestionType.SINGLE_CHOICE,
            Question.QuestionType.MULTIPLE_CHOICE,
        ]:
            raise serializers.ValidationError(
                {"question_type": "Неизвестный тип вопроса."}
            )

        if not 2 <= len(options) <= 10:
            raise serializers.ValidationError(
                {"options": "Нужно добавить от 2 до 10 вариантов."}
            )

        correct_count = sum(
            1 for option in options
            if option.get("is_correct", False)
        )

        if question_type == Question.QuestionType.SINGLE_CHOICE:
            if correct_count != 1:
                raise serializers.ValidationError(
                    {
                        "options": (
                            "Для single_choice нужен ровно один "
                            "правильный вариант."
                        )
                    }
                )

        if question_type == Question.QuestionType.MULTIPLE_CHOICE:
            if not 2 <= correct_count <= len(options) - 1:
                raise serializers.ValidationError(
                    {
                        "options": (
                            "Для multiple_choice нужно от 2 до n-1 "
                            "правильных вариантов."
                        )
                    }
                )

        orders = [
            option.get("order", 0)
            for option in options
        ]

        if len(orders) != len(set(orders)):
            raise serializers.ValidationError(
                {"options": "Порядок вариантов должен быть уникальным."}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        options_data = validated_data.pop("options", [])

        request = self.context["request"]

        question = Question.objects.create(
            teacher=request.user,
            **validated_data,
        )

        QuestionOption.objects.bulk_create([
            QuestionOption(
                question=question,
                text=option["text"],
                is_correct=option.get("is_correct", False),
                order=option.get("order", index),
            )
            for index, option in enumerate(options_data)
        ])

        return question

    @transaction.atomic
    def update(self, instance, validated_data):
        options_data = validated_data.pop("options", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.save()

        if options_data is not None:
            instance.options.all().delete()

            QuestionOption.objects.bulk_create([
                QuestionOption(
                    question=instance,
                    text=option["text"],
                    is_correct=option.get("is_correct", False),
                    order=option.get("order", index),
                )
                for index, option in enumerate(options_data)
            ])

        return instance



class QuestionBankSerializer(serializers.ModelSerializer):

    teacher_username = serializers.CharField(
        source="teacher.username",
        read_only=True,
    )

    options_count = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = [
            "id",
            "teacher",
            "teacher_username",
            "title",
            "question_type",
            "points",
            "is_active",
            "options_count",
            "created_at",
        ]
        read_only_fields = fields

    def get_options_count(self, obj):
        return obj.options.count()
