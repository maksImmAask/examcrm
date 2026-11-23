from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.answers.models import Answer
from apps.exams.models import PublishedQuestion

from .models import Grade


class GradingError(Exception):

    def __init__(self, code, detail, status_code=400):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


def compare_answer_with_key(answer, question):
    value = answer.value

    correct_options = set(
        str(option.id)
        for option in question.options.filter(is_correct=True)
    )

    if question.question_type == "single_choice":
        return (
            isinstance(value, str)
            and {value} == correct_options
        )

    if question.question_type == "multiple_choice":
        if not isinstance(value, list):
            return False

        if not all(isinstance(item, str) for item in value):
            return False

        return set(value) == correct_options

    return False


def recalculate_result(result):
    from apps.results.models import ExamResult

    attempt = result.attempt
    publication = attempt.assignment.publication

    questions = PublishedQuestion.objects.filter(
        publication=publication,
    )

    total_points = sum(
        (Decimal(question.points) for question in questions),
        Decimal("0"),
    )

    grades = Grade.objects.filter(
        answer__attempt=attempt,
    )

    earned_points = sum(
        (grade.points_awarded for grade in grades),
        Decimal("0"),
    )

    has_pending_grades = grades.filter(
        status=Grade.Status.PENDING,
    ).exists()

    if total_points > 0:
        percentage = (
            earned_points / total_points * Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    else:
        percentage = Decimal("0.00")

    result.total_points = total_points
    result.earned_points = earned_points
    result.percentage = percentage

    result.is_passed = (
        percentage >= Decimal(publication.pass_percent)
    )

    result.calculated_at = timezone.now()

    if result.status != ExamResult.Status.RELEASED:
        result.status = (
            ExamResult.Status.PENDING
            if has_pending_grades
            else ExamResult.Status.READY
        )

    result.save(
        update_fields=[
            "total_points",
            "earned_points",
            "percentage",
            "is_passed",
            "calculated_at",
            "status",
            "updated_at",
        ]
    )

    return result


@transaction.atomic
def grade_submitted_attempt(attempt_id):
    from apps.attempts.models import Attempt
    from apps.results.models import ExamResult

    attempt = (
        Attempt.objects
        .select_for_update()
        .select_related(
            "assignment__publication",
        )
        .filter(pk=attempt_id)
        .first()
    )

    if attempt is None:
        raise GradingError(
            "attempt_not_found",
            "Попытка экзамена не найдена.",
            404,
        )

    if attempt.status != Attempt.Status.SUBMITTED:
        raise GradingError(
            "attempt_not_submitted",
            "Нельзя оценить незавершённую попытку.",
            409,
        )

    result, _ = ExamResult.objects.get_or_create(
        attempt=attempt,
    )

    result = ExamResult.objects.select_for_update().get(
        pk=result.pk,
    )

    if result.status == ExamResult.Status.RELEASED:
        return result

    publication = attempt.assignment.publication

    questions = PublishedQuestion.objects.filter(
        publication=publication,
    ).prefetch_related("options")

    answers = Answer.objects.filter(
        attempt=attempt,
    ).select_related("question")

    answers_by_question = {
        answer.question_id: answer
        for answer in answers
    }

    now = timezone.now()

    for question in questions:
        answer = answers_by_question.get(question.id)

        if answer is None:
            continue

        max_points = Decimal(question.points)

        if question.question_type == "text":
            value = answer.value

            if value is None or not str(value).strip():
                Grade.objects.get_or_create(
                    answer=answer,
                    defaults={
                        "points_awarded": Decimal("0"),
                        "max_points": max_points,
                        "is_correct": False,
                        "status": Grade.Status.COMPLETED,
                        "grading_type": Grade.GradingType.AUTOMATIC,
                        "graded_at": now,
                    },
                )
            else:
                Grade.objects.get_or_create(
                    answer=answer,
                    defaults={
                        "points_awarded": Decimal("0"),
                        "max_points": max_points,
                        "is_correct": None,
                        "status": Grade.Status.PENDING,
                        "grading_type": Grade.GradingType.MANUAL,
                    },
                )

            continue

        is_correct = compare_answer_with_key(
            answer,
            question,
        )

        points_awarded = (
            max_points if is_correct else Decimal("0")
        )

        Grade.objects.update_or_create(
            answer=answer,
            defaults={
                "points_awarded": points_awarded,
                "max_points": max_points,
                "is_correct": is_correct,
                "status": Grade.Status.COMPLETED,
                "grading_type": Grade.GradingType.AUTOMATIC,
                "graded_by": None,
                "graded_at": now,
            },
        )

    return recalculate_result(result)


@transaction.atomic
def grade_text_answer(
    grade_id,
    teacher,
    points_awarded,
    feedback="",
):
    from apps.results.models import ExamResult

    grade = (
        Grade.objects
        .select_for_update()
        .select_related(
            "answer__attempt__assignment__publication__exam",
            "answer__question",
        )
        .filter(pk=grade_id)
        .first()
    )

    if grade is None:
        raise GradingError(
            "grade_not_found",
            "Оценка не найдена.",
            404,
        )

    exam = grade.answer.attempt.assignment.publication.exam

    if exam.owner_id != teacher.id:
        raise GradingError(
            "permission_denied",
            "Только владелец экзамена может проверять ответы.",
            403,
        )

    if grade.answer.question.question_type != "text":
        raise GradingError(
            "not_text_question",
            "Ручная проверка доступна только для текстовых вопросов.",
            400,
        )

    result = ExamResult.objects.select_for_update().get(
        attempt=grade.answer.attempt,
    )

    if result.status == ExamResult.Status.RELEASED:
        raise GradingError(
            "result_already_released",
            "Опубликованный результат нельзя изменить.",
            409,
        )

    if grade.status != Grade.Status.PENDING:
        raise GradingError(
            "grade_already_completed",
            "Этот ответ уже проверен.",
            409,
        )

    points_awarded = Decimal(str(points_awarded))

    if points_awarded < 0 or points_awarded > grade.max_points:
        raise GradingError(
            "invalid_points",
            f"Баллы должны быть от 0 до {grade.max_points}.",
            400,
        )

    if len(feedback) > 5000:
        raise GradingError(
            "feedback_too_long",
            "Комментарий не должен превышать 5000 символов.",
            400,
        )

    grade.points_awarded = points_awarded
    grade.feedback = feedback
    grade.status = Grade.Status.COMPLETED
    grade.graded_by = teacher
    grade.graded_at = timezone.now()
    grade.is_correct = points_awarded == grade.max_points

    grade.save(
        update_fields=[
            "points_awarded",
            "feedback",
            "status",
            "graded_by",
            "graded_at",
            "is_correct",
            "updated_at",
        ]
    )

    return recalculate_result(result)
@transaction.atomic
def release_exam_result(result_id, teacher):
    from apps.results.models import ExamResult

    result = (
        ExamResult.objects
        .select_for_update()
        .select_related(
            "attempt__assignment__publication__exam",
        )
        .filter(pk=result_id)
        .first()
    )

    if result is None:
        raise GradingError(
            "result_not_found",
            "Результат не найден.",
            404,
        )

    exam = result.attempt.assignment.publication.exam

    if exam.owner_id != teacher.id:
        raise GradingError(
            "permission_denied",
            "Только владелец экзамена может публиковать результат.",
            403,
        )

    if result.status == ExamResult.Status.RELEASED:
        return result

    if result.status != ExamResult.Status.READY:
        raise GradingError(
            "result_not_ready",
            "Сначала необходимо завершить проверку всех ответов.",
            409,
        )

    result.status = ExamResult.Status.RELEASED
    result.released_at = timezone.now()
    result.released_by = teacher

    result.save(
        update_fields=[
            "status",
            "released_at",
            "released_by",
            "updated_at",
        ]
    )

    return result