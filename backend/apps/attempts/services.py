
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.answers.models import Answer, IdempotencyRecord
from apps.exams.models import ExamAssignment, PublishedOption

from .models import Attempt


class AttemptFlowError(Exception):

    def __init__(self, code, detail, status_code=400, meta=None):
        self.code = code
        self.detail = detail
        self.status_code = status_code
        self.meta = meta or {}
        super().__init__(detail)


def get_student_assignment(exam_id, student):
    try:
        return (
            ExamAssignment.objects
            .select_related("publication", "publication__exam")
            .get(
                publication__exam_id=exam_id,
                student=student,
            )
        )
    except ExamAssignment.DoesNotExist:
        raise AttemptFlowError(
            "not_found",
            "Назначение экзамена не найдено.",
            404,
        )


@transaction.atomic
def start_attempt(exam_id, student):
    assignment = get_student_assignment(exam_id, student)

    existing = (
        Attempt.objects
        .select_for_update()
        .filter(assignment=assignment)
        .first()
    )

    if existing:
        return existing, False

    publication = assignment.publication
    now = timezone.now()

    if now < publication.opens_at:
        raise AttemptFlowError(
            "exam_not_open",
            "Экзамен ещё не начался.",
            409,
        )

    if now >= publication.closes_at:
        raise AttemptFlowError(
            "exam_closed",
            "Время начала экзамена завершилось.",
            409,
        )

    duration_deadline = now + timedelta(
        minutes=publication.duration_minutes
    )

    deadline_at = min(
        duration_deadline,
        publication.closes_at,
    )
    try:
        with transaction.atomic():
            attempt = Attempt.objects.create(
                assignment=assignment,
                started_at=now,
                deadline_at=deadline_at,
            )
    except IntegrityError:
        attempt = Attempt.objects.get(
            assignment=assignment
        )
        return attempt, False

    return attempt, True

def get_attempt_for_student(attempt_id, student, lock=False):
    queryset = Attempt.objects.select_related(
        "assignment",
        "assignment__student",
        "assignment__publication",
    )

    if lock:
        queryset = queryset.select_for_update()

    try:
        return queryset.get(
            pk=attempt_id,
            assignment__student=student,
        )
    except Attempt.DoesNotExist:
        raise AttemptFlowError(
            "not_found",
            "Попытка не найдена.",
            404,
        )

def finalize_attempt_locked(attempt, now=None):
    if attempt.status != Attempt.Status.IN_PROGRESS:
        return attempt

    now = now or timezone.now()

    if now >= attempt.deadline_at:
        finished_at = attempt.deadline_at
        finish_reason = Attempt.FinishReason.TIMEOUT
    else:
        finished_at = now
        finish_reason = Attempt.FinishReason.MANUAL

    attempt.status = Attempt.Status.SUBMITTED
    attempt.finished_at = finished_at
    attempt.finalized_at = now
    attempt.finish_reason = finish_reason
    attempt.event_version += 1

    attempt.save(
        update_fields=[
            "status",
            "finished_at",
            "finalized_at",
            "finish_reason",
            "event_version",
            "updated_at",
        ]
    )

    from apps.grading.services import grade_submitted_attempt

    grade_submitted_attempt(attempt.id)

    return attempt

def get_attempt_snapshot(attempt, include_answers=True):
    publication = attempt.assignment.publication

    questions = publication.questions.prefetch_related(
        "options"
    ).order_by("position")

    saved_answers = {}

    if include_answers:
        saved_answers = {
            str(answer.question_id): {
                "value": answer.value,
                "revision": answer.revision,
                "saved_at": answer.updated_at,
            }
            for answer in Answer.objects.filter(
                attempt=attempt
            ).select_related("question")
        }

    question_data = []

    for question in questions:
        options = [
            {
                "id": str(option.id),
                "text": option.text,
                "order": option.order,
            }
            for option in question.options.all()
        ]

        saved = saved_answers.get(str(question.id), {})

        question_data.append({
            "id": str(question.id),
            "title": question.title,
            "question_type": question.question_type,
            "position": question.position,
            "points": question.points,
            "options": options,
            "answer": saved.get("value"),
            "revision": saved.get("revision", 0),
            "saved_at": saved.get("saved_at"),
        })

    answered_count = sum(
        1 for item in question_data
        if item["answer"] is not None
    )

    now = timezone.now()

    return {
        "id": str(attempt.id),
        "exam_id": str(publication.exam_id),
        "exam_name": publication.name,
        "instructions": publication.instructions,
        "status": attempt.status,
        "server_now": now,
        "started_at": attempt.started_at,
        "deadline_at": attempt.deadline_at,
        "finished_at": attempt.finished_at,
        "finalized_at": attempt.finalized_at,
        "finish_reason": attempt.finish_reason,
        "event_version": attempt.event_version,
        "answered_count": answered_count,
        "total_questions": len(question_data),
        "questions": question_data,
    }


def normalize_answer_value(question, value):
    if value is None:
        return None

    if question.question_type == "single_choice":
        if not isinstance(value, str):
            raise AttemptFlowError(
                "invalid_answer",
                "Для этого вопроса нужно передать ID одного варианта.",
            )

        option_ids = {
            str(option.id)
            for option in question.options.all()
        }

        if value not in option_ids:
            raise AttemptFlowError(
                "invalid_answer",
                "Выбранный вариант не принадлежит этому вопросу.",
            )

        return value

    if question.question_type == "multiple_choice":
        if not isinstance(value, list):
            raise AttemptFlowError(
                "invalid_answer",
                "Для этого вопроса нужно передать список ID вариантов.",
            )

        if not all(isinstance(item, str) for item in value):
            raise AttemptFlowError(
                "invalid_answer",
                "ID вариантов должны быть строками.",
            )

        if len(value) != len(set(value)):
            raise AttemptFlowError(
                "invalid_answer",
                "ID вариантов не должны повторяться.",
            )

        if not value:
            return None

        option_ids = {
            str(option.id)
            for option in question.options.all()
        }

        if not set(value).issubset(option_ids):
            raise AttemptFlowError(
                "invalid_answer",
                "Один или несколько вариантов не принадлежат этому вопросу.",
            )

        return sorted(value)
    if question.question_type == "text":
        if not isinstance(value, str):
            raise AttemptFlowError(
                "invalid_answer",
                "Текстовый ответ должен быть строкой.",
            )

        if len(value) > 5000:
            raise AttemptFlowError(
                "invalid_answer",
                "Ответ не может быть длиннее 5000 символов.",
            )

        if not value.strip():
            return None

        return value

    raise AttemptFlowError(
        "invalid_answer",
        "Неизвестный тип вопроса.",
    )


def save_answer(
    attempt_id,
    question_id,
    student,
    value,
    base_revision,
    idempotency_key,
):
    import hashlib
    import json
    import uuid

    try:
        key = uuid.UUID(str(idempotency_key))
    except (ValueError, TypeError, AttributeError):
        raise AttemptFlowError(
            "invalid_idempotency_key",
            "Заголовок Idempotency-Key должен содержать UUID.",
        )

    if not isinstance(base_revision, int) or base_revision < 0:
        raise AttemptFlowError(
            "validation_error",
            "base_revision должен быть целым неотрицательным числом.",
        )

    with transaction.atomic():
        attempt = get_attempt_for_student(
            attempt_id,
            student,
            lock=True,
        )

        try:
            question = attempt.assignment.publication.questions.get(
                pk=question_id
            )
        except Exception:
            raise AttemptFlowError(
                "not_found",
                "Вопрос не найден в этой попытке.",
                404,
            )

        normalized_value = normalize_answer_value(
            question,
            value,
        )

        payload = {
            "value": normalized_value,
            "base_revision": base_revision,
        }

        request_hash = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        resource_id = f"{attempt.id}:{question.id}"

        previous = IdempotencyRecord.objects.filter(
            user=student,
            operation="save_answer",
            resource_id=resource_id,
            key=key,
        ).first()

        if previous:
            if previous.request_hash != request_hash:
                raise AttemptFlowError(
                    "idempotency_conflict",
                    "Этот ключ уже использован с другим содержимым.",
                    409,
                )

            return previous.response_data, previous.response_status

        now = timezone.now()

        if attempt.status != Attempt.Status.IN_PROGRESS:
            raise AttemptFlowError(
                "attempt_closed",
                "Попытка уже завершена.",
                409,
            )

        if now >= attempt.deadline_at:
            finalize_attempt_locked(attempt, now)

            return {
                "code": "deadline_passed",
                "detail": "Время попытки истекло.",
            }, 409

        answer = (
            Answer.objects
            .select_for_update()
            .filter(
                attempt=attempt,
                question=question,
            )
            .first()
        )

        current_revision = answer.revision if answer else 0

        if current_revision != base_revision:
            raise AttemptFlowError(
                "answer_conflict",
                "Ответ уже изменён в другой вкладке.",
                409,
                {
                    "current_revision": current_revision,
                    "current_value": answer.value if answer else None,
                },
            )

        if answer is None:
            answer = Answer.objects.create(
                attempt=attempt,
                question=question,
                value=normalized_value,
                revision=1,
            )
        else:
            answer.value = normalized_value
            answer.revision += 1
            answer.save(
                update_fields=[
                    "value",
                    "revision",
                    "updated_at",
                ]
            )

        attempt.event_version += 1
        attempt.save(
            update_fields=[
                "event_version",
                "updated_at",
            ]
        )

        answered_count = Answer.objects.filter(
            attempt=attempt
        ).exclude(value=None).count()

        response_data = {
            "question_id": str(question.id),
            "value": answer.value,
            "revision": answer.revision,
            "saved_at": answer.updated_at.isoformat(),
            "answered_count": answered_count,
            "event_version": attempt.event_version,
        }

        IdempotencyRecord.objects.create(
            user=student,
            operation="save_answer",
            resource_id=resource_id,
            key=key,
            request_hash=request_hash,
            response_data=response_data,
            response_status=200,
        )

        return response_data, 200



@transaction.atomic
def submit_attempt(attempt_id, student):
    attempt = get_attempt_for_student(
        attempt_id,
        student,
        lock=True,
    )

    if attempt.status == Attempt.Status.IN_PROGRESS:
        attempt = finalize_attempt_locked(attempt)

    return {
        "id": str(attempt.id),
        "status": attempt.status,
        "finished_at": attempt.finished_at,
        "finish_reason": attempt.finish_reason,
    }
