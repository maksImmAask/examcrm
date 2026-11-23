
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.groups.models import StudyGroup
from apps.questions.models import Question

from ..models import (
    Exam,
    ExamGroup,
    ExamQuestion,
    ExamPublication,
    PublishedQuestion,
    PublishedOption,
    ExamAssignment,
)


class ExamPublicationError(Exception):
    pass


def validate_exam_for_publication(exam):
    errors = {}

    if not exam.name or not exam.name.strip():
        errors["name"] = "Укажите название экзамена."

    if not exam.opens_at:
        errors["opens_at"] = "Укажите дату начала."

    if not exam.closes_at:
        errors["closes_at"] = "Укажите дату окончания."

    if exam.opens_at and exam.closes_at:
        if exam.opens_at >= exam.closes_at:
            errors["closes_at"] = "Дата окончания должна быть позже начала."

        if exam.opens_at <= timezone.now():
            errors["opens_at"] = "Начало экзамена должно быть в будущем."

    if not exam.duration_minutes or not 1 <= exam.duration_minutes <= 180:
        errors["duration_minutes"] = "Продолжительность должна быть от 1 до 180 минут."

    if exam.pass_percent is None or not 0 <= exam.pass_percent <= 100:
        errors["pass_percent"] = "Проходной процент должен быть от 0 до 100."

    if len(exam.instructions) > 5000:
        errors["instructions"] = "Инструкция не может быть длиннее 5000 символов."

    if errors:
        raise ExamPublicationError(errors)

    exam_groups = list(
        ExamGroup.objects
        .filter(exam=exam)
        .select_related("group")
    )

    if not exam_groups:
        raise ExamPublicationError(
            {"groups": "Добавьте хотя бы одну учебную группу."}
        )

    for exam_group in exam_groups:
        group = exam_group.group

        if not group.is_active:
            raise ExamPublicationError(
                {"groups": f"Группа «{group.name}» неактивна."}
            )

        has_owner_access = (
            group.teacher_id == exam.owner_id
            or group.teachers.filter(pk=exam.owner_id).exists()
        )

        if not has_owner_access:
            raise ExamPublicationError(
                {"groups": f"Преподаватель не имеет доступа к группе «{group.name}»."}
            )

    exam_questions = list(
        ExamQuestion.objects
        .filter(exam=exam)
        .select_related("question")
        .prefetch_related("question__options")
        .order_by("position")
    )

    if not 1 <= len(exam_questions) <= 100:
        raise ExamPublicationError(
            {"questions": "Экзамен должен содержать от 1 до 100 вопросов."}
        )

    positions = [item.position for item in exam_questions]

    if len(positions) != len(set(positions)):
        raise ExamPublicationError(
            {"questions": "Позиции вопросов должны быть уникальными."}
        )

    for exam_question in exam_questions:
        question = exam_question.question

        if not question.is_active:
            raise ExamPublicationError(
                {"questions": f"Вопрос «{question.title}» неактивен."}
            )

        if question.teacher_id != exam.owner_id:
            raise ExamPublicationError(
                {"questions": f"Вопрос «{question.title}» принадлежит другому преподавателю."}
            )

        if not question.title.strip():
            raise ExamPublicationError(
                {"questions": "Текст вопроса не может быть пустым."}
            )

        if not 1 <= exam_question.points <= 100:
            raise ExamPublicationError(
                {"questions": "Баллы за вопрос должны быть от 1 до 100."}
            )

        options = list(question.options.all())

        if question.question_type in [
            Question.QuestionType.SINGLE_CHOICE,
            Question.QuestionType.MULTIPLE_CHOICE,
        ]:
            if not 2 <= len(options) <= 10:
                raise ExamPublicationError(
                    {"questions": f"Вопрос «{question.title}» должен иметь от 2 до 10 вариантов."}
                )

            correct_count = sum(option.is_correct for option in options)

            if question.question_type == Question.QuestionType.SINGLE_CHOICE:
                if correct_count != 1:
                    raise ExamPublicationError(
                        {"questions": f"Вопрос «{question.title}» должен иметь ровно один правильный вариант."}
                    )

            if question.question_type == Question.QuestionType.MULTIPLE_CHOICE:
                if not 2 <= correct_count <= len(options) - 1:
                    raise ExamPublicationError(
                        {"questions": f"Вопрос «{question.title}» должен иметь от 2 до n-1 правильных вариантов."}
                    )

        elif question.question_type == Question.QuestionType.TEXT:
            if options:
                raise ExamPublicationError(
                    {"questions": f"Текстовый вопрос «{question.title}» не должен иметь варианты ответов."}
                )

        else:
            raise ExamPublicationError(
                {"questions": f"Неизвестный тип вопроса: {question.question_type}."}
            )

    active_student_ids = set()

    for exam_group in exam_groups:
        students = exam_group.group.students.filter(
            role="student",
            is_active=True,
        ).values_list("id", flat=True)

        active_student_ids.update(students)

    if not active_student_ids:
        raise ExamPublicationError(
            {"groups": "В выбранных группах нет активных студентов."}
        )

    return exam_groups, exam_questions, active_student_ids


@transaction.atomic
def publish_exam(exam_id, user=None):
    try:
        exam = (
            Exam.objects
            .select_for_update()
            .select_related("owner")
            .get(pk=exam_id)
        )
    except Exam.DoesNotExist:
        raise ExamPublicationError(
            {"exam": "Экзамен не найден."}
        )

    if user and user.role != "admin" and exam.owner_id != user.id:
        raise ExamPublicationError(
            {"detail": "У вас нет доступа к этому экзамену."}
        )

    existing_publication = ExamPublication.objects.filter(
        exam=exam
    ).first()

    if existing_publication:
        return existing_publication

    if exam.status != Exam.Status.DRAFT:
        raise ExamPublicationError(
            {"status": "Опубликовать можно только черновик."}
        )

    exam_groups, exam_questions, student_ids = (
        validate_exam_for_publication(exam)
    )

    published_at = timezone.now()

    publication = ExamPublication.objects.create(
        exam=exam,
        name=exam.name,
        instructions=exam.instructions,
        opens_at=exam.opens_at,
        closes_at=exam.closes_at,
        duration_minutes=exam.duration_minutes,
        pass_percent=exam.pass_percent,
        published_at=published_at,
    )

    published_questions = []

    for exam_question in exam_questions:
        source_question = exam_question.question

        published_question = PublishedQuestion.objects.create(
            publication=publication,
            source_question=source_question,
            title=source_question.title,
            question_type=source_question.question_type,
            explanation=source_question.explanation,
            position=exam_question.position,
            points=exam_question.points,
        )

        source_options = list(
            source_question.options.all()
        )

        PublishedOption.objects.bulk_create([
            PublishedOption(
                question=published_question,
                source_option_id=option.pk,
                text=option.text,
                is_correct=option.is_correct,
                order=option.order,
            )
            for option in source_options
        ])

        published_questions.append(published_question)

    group_students = {}

    for exam_group in exam_groups:
        group_id = exam_group.group_id

        students = exam_group.group.students.filter(
            role="student",
            is_active=True,
        ).values_list("id", flat=True)

        for student_id in students:
            group_students.setdefault(student_id, set()).add(group_id)

    assignments = [
        ExamAssignment(
            publication=publication,
            student_id=student_id,
            source_group_ids=sorted(group_ids),
        )
        for student_id, group_ids in group_students.items()
        if student_id in student_ids
    ]

    ExamAssignment.objects.bulk_create(
        assignments,
        ignore_conflicts=True,
    )

    exam.status = Exam.Status.PUBLISHED
    exam.published_at = published_at
    exam.save(update_fields=["status", "published_at", "updated_at"])

    return publication
