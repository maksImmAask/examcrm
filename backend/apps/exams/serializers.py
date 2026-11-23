
from django.db import transaction
from rest_framework import serializers

from apps.groups.models import StudyGroup
from apps.questions.models import Question

from .models import Exam, ExamGroup, ExamQuestion, ExamPublication


class ExamQuestionInputSerializer(serializers.Serializer):
    question = serializers.PrimaryKeyRelatedField(
        queryset=Question.objects.all()
    )
    position = serializers.IntegerField(min_value=1, max_value=100)
    points = serializers.IntegerField(min_value=1, max_value=100)


class ExamGroupInputSerializer(serializers.Serializer):
    group = serializers.PrimaryKeyRelatedField(
        queryset=StudyGroup.objects.all()
    )


class ExamQuestionOutputSerializer(serializers.ModelSerializer):
    question_title = serializers.CharField(
        source="question.title",
        read_only=True,
    )
    question_type = serializers.CharField(
        source="question.question_type",
        read_only=True,
    )

    class Meta:
        model = ExamQuestion
        fields = [
            "id",
            "question",
            "question_title",
            "question_type",
            "position",
            "points",
        ]


class ExamGroupOutputSerializer(serializers.ModelSerializer):
    group_name = serializers.CharField(
        source="group.name",
        read_only=True,
    )

    class Meta:
        model = ExamGroup
        fields = [
            "id",
            "group",
            "group_name",
        ]


class ExamReadSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(
        source="owner.username",
        read_only=True,
    )
    groups = serializers.SerializerMethodField()
    questions = serializers.SerializerMethodField()
    total_points = serializers.SerializerMethodField()
    total_questions = serializers.SerializerMethodField()

    class Meta:
        model = Exam
        fields = [
            "id",
            "owner",
            "owner_username",
            "name",
            "instructions",
            "opens_at",
            "closes_at",
            "duration_minutes",
            "pass_percent",
            "status",
            "published_at",
            "archived_at",
            "groups",
            "questions",
            "total_questions",
            "total_points",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_groups(self, obj):
        return ExamGroupOutputSerializer(
            obj.exam_groups.select_related("group"),
            many=True,
        ).data

    def get_questions(self, obj):
        if obj.status != Exam.Status.DRAFT:
            return []

        return ExamQuestionOutputSerializer(
            obj.exam_questions.select_related("question"),
            many=True,
        ).data

    def get_total_questions(self, obj):
        return obj.exam_questions.count()

    def get_total_points(self, obj):
        return sum(
            obj.exam_questions.values_list("points", flat=True)
        )


class ExamWriteSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        queryset=StudyGroup.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    questions = ExamQuestionInputSerializer(
        many=True,
        required=False,
        write_only=True,
    )
    owner = serializers.PrimaryKeyRelatedField(
        queryset=Exam._meta.get_field("owner").remote_field.model.objects.filter(
            role="teacher"
        ),
        required=False,
    )

    class Meta:
        model = Exam
        fields = [
            "id",
            "owner",
            "name",
            "instructions",
            "opens_at",
            "closes_at",
            "duration_minutes",
            "pass_percent",
            "groups",
            "questions",
        ]
        read_only_fields = ["id"]

    def validate(self, attrs):
        request = self.context["request"]
        user = request.user
        instance = self.instance

        if instance and instance.status != Exam.Status.DRAFT:
            raise serializers.ValidationError(
                "Опубликованный экзамен нельзя редактировать."
            )

        if user.role == "teacher":
            attrs["owner"] = user
        elif user.role == "admin":
            owner = attrs.get(
                "owner",
                instance.owner if instance else None,
            )
            if owner is None:
                raise serializers.ValidationError(
                    {"owner": "Администратор должен указать владельца-преподавателя."}
                )
            attrs["owner"] = owner
        else:
            raise serializers.ValidationError(
                "У вас нет прав на создание экзаменов."
            )

        owner = attrs.get(
            "owner",
            instance.owner if instance else None,
        )

        groups = attrs.get("groups")
        questions = attrs.get("questions")

        if groups is not None:
            group_ids = [group.pk for group in groups]

            if len(group_ids) != len(set(group_ids)):
                raise serializers.ValidationError(
                    {"groups": "Одна группа не может быть добавлена дважды."}
                )

            if user.role == "teacher":
                for group in groups:
                    if not (
                        group.teacher_id == user.id
                        or group.teachers.filter(pk=user.pk).exists()
                    ):
                        raise serializers.ValidationError(
                            {"groups": f"Нет доступа к группе «{group.name}»."}
                        )

            if user.role == "admin":
                for group in groups:
                    if not (
                        group.teacher_id == owner.id
                        or group.teachers.filter(pk=owner.pk).exists()
                    ):
                        raise serializers.ValidationError(
                            {"groups": f"Группа «{group.name}» не принадлежит выбранному преподавателю."}
                        )

        if questions is not None:
            question_ids = [item["question"].pk for item in questions]
            positions = [item["position"] for item in questions]

            if len(question_ids) != len(set(question_ids)):
                raise serializers.ValidationError(
                    {"questions": "В экзамене не должно быть повторяющихся вопросов."}
                )

            if len(positions) != len(set(positions)):
                raise serializers.ValidationError(
                    {"questions": "Позиции вопросов должны быть уникальными."}
                )

            if len(questions) > 100:
                raise serializers.ValidationError(
                    {"questions": "В экзамене может быть максимум 100 вопросов."}
                )

            for item in questions:
                question = item["question"]

                if not question.is_active:
                    raise serializers.ValidationError(
                        {"questions": f"Вопрос «{question.title}» неактивен."}
                    )

                if question.teacher_id != owner.id:
                    raise serializers.ValidationError(
                        {"questions": f"Вопрос «{question.title}» принадлежит другому преподавателю."}
                    )

        opens_at = attrs.get(
            "opens_at",
            instance.opens_at if instance else None,
        )
        closes_at = attrs.get(
            "closes_at",
            instance.closes_at if instance else None,
        )

        if opens_at and closes_at and opens_at >= closes_at:
            raise serializers.ValidationError(
                {"closes_at": "Дата окончания должна быть позже даты начала."}
            )

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        groups = validated_data.pop("groups", [])
        questions = validated_data.pop("questions", [])

        exam = Exam.objects.create(**validated_data)

        ExamGroup.objects.bulk_create([
            ExamGroup(exam=exam, group=group)
            for group in groups
        ])

        ExamQuestion.objects.bulk_create([
            ExamQuestion(
                exam=exam,
                question=item["question"],
                position=item["position"],
                points=item["points"],
            )
            for item in questions
        ])

        return exam

    @transaction.atomic
    def update(self, instance, validated_data):
        groups = validated_data.pop("groups", None)
        questions = validated_data.pop("questions", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.full_clean(
            exclude=["owner"],
            validate_unique=False,
        )
        instance.save()

        if groups is not None:
            instance.exam_groups.all().delete()
            ExamGroup.objects.bulk_create([
                ExamGroup(exam=instance, group=group)
                for group in groups
            ])

        if questions is not None:
            instance.exam_questions.all().delete()
            ExamQuestion.objects.bulk_create([
                ExamQuestion(
                    exam=instance,
                    question=item["question"],
                    position=item["position"],
                    points=item["points"],
                )
                for item in questions
            ])

        return instance
    
    def to_representation(self, instance):
        return ExamReadSerializer(
            instance,
            context=self.context,
        ).data



class ExamPublicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExamPublication
        fields = [
            "id",
            "exam",
            "name",
            "instructions",
            "opens_at",
            "closes_at",
            "duration_minutes",
            "pass_percent",
            "published_at",
        ]
        read_only_fields = fields
