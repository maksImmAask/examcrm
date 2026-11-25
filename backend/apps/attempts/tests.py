
import uuid
from datetime import timedelta

from django.utils import timezone
from django.test import TestCase
from rest_framework.test import APIClient
from apps.users.models import User
from apps.exams.models import (
    Exam,
    ExamPublication,
    ExamAssignment,
    PublishedQuestion,
    PublishedOption,
)
from apps.answers.models import Answer, IdempotencyRecord
from apps.grading.models import Grade
from apps.results.models import ExamResult

from .models import Attempt
from .services import (
    AttemptFlowError,
    start_attempt,
    get_attempt_snapshot,
    save_answer,
    submit_attempt,
    finalize_attempt_locked,
)


class AttemptServiceTests(TestCase):

    def setUp(self):
        now = timezone.now()

        self.teacher = User.objects.create_user(
            username="attempt_teacher",
            password="test-password",
            role=User.Role.TEACHER,
        )

        self.student = User.objects.create_user(
            username="attempt_student",
            password="test-password",
            role=User.Role.STUDENT,
        )

        self.exam = Exam.objects.create(
            owner=self.teacher,
            name="Тестовый экзамен",
            instructions="Инструкция",
            opens_at=now - timedelta(minutes=5),
            closes_at=now + timedelta(hours=2),
            duration_minutes=60,
            pass_percent=60,
            status=Exam.Status.PUBLISHED,
        )

        self.publication = ExamPublication.objects.create(
            exam=self.exam,
            name=self.exam.name,
            instructions=self.exam.instructions,
            opens_at=self.exam.opens_at,
            closes_at=self.exam.closes_at,
            duration_minutes=self.exam.duration_minutes,
            pass_percent=self.exam.pass_percent,
        )

        self.assignment = ExamAssignment.objects.create(
            publication=self.publication,
            student=self.student,
            source_group_ids=[],
        )

        self.question = PublishedQuestion.objects.create(
            publication=self.publication,
            title="Сколько будет 2 + 2?",
            question_type="single_choice",
            position=1,
            points=5,
        )

        self.correct_option = PublishedOption.objects.create(
            question=self.question,
            text="4",
            is_correct=True,
            order=1,
        )

        self.wrong_option = PublishedOption.objects.create(
            question=self.question,
            text="5",
            is_correct=False,
            order=2,
        )

        self.text_question = PublishedQuestion.objects.create(
            publication=self.publication,
            title="Объясните решение",
            question_type="text",
            position=2,
            points=5,
        )

    def create_attempt(self):
        attempt, created = start_attempt(
            self.exam.id,
            self.student,
        )
        self.assertTrue(created)
        return attempt

    def test_student_can_start_attempt(self):
        attempt, created = start_attempt(
            self.exam.id,
            self.student,
        )

        self.assertTrue(created)
        self.assertEqual(
            attempt.status,
            Attempt.Status.IN_PROGRESS,
        )
        self.assertEqual(
            attempt.assignment,
            self.assignment,
        )

    def test_start_attempt_returns_existing_attempt(self):
        first_attempt, first_created = start_attempt(
            self.exam.id,
            self.student,
        )

        second_attempt, second_created = start_attempt(
            self.exam.id,
            self.student,
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first_attempt.id, second_attempt.id)
        self.assertEqual(Attempt.objects.count(), 1)

    def test_student_without_assignment_cannot_start(self):
        another_student = User.objects.create_user(
            username="another_student",
            password="test-password",
            role=User.Role.STUDENT,
        )

        with self.assertRaises(AttemptFlowError) as context:
            start_attempt(
                self.exam.id,
                another_student,
            )

        self.assertEqual(context.exception.code, "not_found")
        self.assertEqual(context.exception.status_code, 404)

    def test_attempt_deadline_does_not_exceed_exam_close(self):
        now = timezone.now()

        self.publication.closes_at = now + timedelta(minutes=10)
        self.publication.duration_minutes = 60
        self.publication.save(
            update_fields=["closes_at", "duration_minutes"]
        )

        attempt, created = start_attempt(
            self.exam.id,
            self.student,
        )

        self.assertTrue(created)
        self.assertLessEqual(
            attempt.deadline_at,
            self.publication.closes_at,
        )

    def test_snapshot_does_not_expose_correct_answers(self):
        attempt = self.create_attempt()

        snapshot = get_attempt_snapshot(attempt)

        self.assertEqual(snapshot["total_questions"], 2)

        question_data = snapshot["questions"][0]

        self.assertEqual(
            question_data["question_type"],
            "single_choice",
        )

        for option in question_data["options"]:
            self.assertNotIn("is_correct", option)

        self.assertNotIn("correct_answer", question_data)

    def test_save_single_choice_answer(self):
        attempt = self.create_attempt()
        key = uuid.uuid4()

        response, status_code = save_answer(
            attempt_id=attempt.id,
            question_id=self.question.id,
            student=self.student,
            value=str(self.correct_option.id),
            base_revision=0,
            idempotency_key=key,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(response["revision"], 1)
        self.assertEqual(
            response["value"],
            str(self.correct_option.id),
        )

        answer = Answer.objects.get(
            attempt=attempt,
            question=self.question,
        )

        self.assertEqual(answer.revision, 1)

    def test_same_idempotency_key_returns_previous_response(self):
        attempt = self.create_attempt()
        key = uuid.uuid4()

        first_response, first_status = save_answer(
            attempt_id=attempt.id,
            question_id=self.question.id,
            student=self.student,
            value=str(self.correct_option.id),
            base_revision=0,
            idempotency_key=key,
        )

        second_response, second_status = save_answer(
            attempt_id=attempt.id,
            question_id=self.question.id,
            student=self.student,
            value=str(self.correct_option.id),
            base_revision=0,
            idempotency_key=key,
        )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first_response, second_response)
        self.assertEqual(Answer.objects.count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

    def test_reusing_idempotency_key_with_different_payload_fails(self):
        attempt = self.create_attempt()
        key = uuid.uuid4()

        save_answer(
            attempt_id=attempt.id,
            question_id=self.question.id,
            student=self.student,
            value=str(self.correct_option.id),
            base_revision=0,
            idempotency_key=key,
        )

        with self.assertRaises(AttemptFlowError) as context:
            save_answer(
                attempt_id=attempt.id,
                question_id=self.question.id,
                student=self.student,
                value=str(self.wrong_option.id),
                base_revision=0,
                idempotency_key=key,
            )

        self.assertEqual(
            context.exception.code,
            "idempotency_conflict",
        )
        self.assertEqual(context.exception.status_code, 409)

    def test_stale_revision_is_rejected(self):
        attempt = self.create_attempt()

        save_answer(
            attempt_id=attempt.id,
            question_id=self.question.id,
            student=self.student,
            value=str(self.correct_option.id),
            base_revision=0,
            idempotency_key=uuid.uuid4(),
        )

        with self.assertRaises(AttemptFlowError) as context:
            save_answer(
                attempt_id=attempt.id,
                question_id=self.question.id,
                student=self.student,
                value=str(self.wrong_option.id),
                base_revision=0,
                idempotency_key=uuid.uuid4(),
            )

        self.assertEqual(context.exception.code, "answer_conflict")
        self.assertEqual(context.exception.status_code, 409)

    def test_invalid_option_is_rejected(self):
        attempt = self.create_attempt()

        with self.assertRaises(AttemptFlowError) as context:
            save_answer(
                attempt_id=attempt.id,
                question_id=self.question.id,
                student=self.student,
                value=str(uuid.uuid4()),
                base_revision=0,
                idempotency_key=uuid.uuid4(),
            )

        self.assertEqual(context.exception.code, "invalid_answer")

    def test_text_answer_can_be_saved(self):
        attempt = self.create_attempt()

        response, status_code = save_answer(
            attempt_id=attempt.id,
            question_id=self.text_question.id,
            student=self.student,
            value="Потому что 2 + 2 = 4",
            base_revision=0,
            idempotency_key=uuid.uuid4(),
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(response["revision"], 1)

        answer = Answer.objects.get(
            attempt=attempt,
            question=self.text_question,
        )

        self.assertEqual(answer.value, "Потому что 2 + 2 = 4")

    def test_submit_attempt_finalizes_attempt_and_creates_result(self):
        attempt = self.create_attempt()

        save_answer(
            attempt_id=attempt.id,
            question_id=self.question.id,
            student=self.student,
            value=str(self.correct_option.id),
            base_revision=0,
            idempotency_key=uuid.uuid4(),
        )

        response = submit_attempt(
            attempt.id,
            self.student,
        )

        attempt.refresh_from_db()

        self.assertEqual(
            response["status"],
            Attempt.Status.SUBMITTED,
        )
        self.assertEqual(
            attempt.finish_reason,
            Attempt.FinishReason.MANUAL,
        )
        self.assertIsNotNone(attempt.finished_at)
        self.assertTrue(
            ExamResult.objects.filter(attempt=attempt).exists()
        )

        grade = Grade.objects.get(
            answer__attempt=attempt,
            answer__question=self.question,
        )

        self.assertEqual(
            grade.points_awarded,
            5,
        )

    def test_timeout_finalization_uses_deadline_as_finished_at(self):
        attempt = self.create_attempt()

        deadline = attempt.deadline_at
        future_now = deadline + timedelta(seconds=5)

        finalize_attempt_locked(
            attempt,
            now=future_now,
        )

        attempt.refresh_from_db()

        self.assertEqual(
            attempt.status,
            Attempt.Status.SUBMITTED,
        )
        self.assertEqual(
            attempt.finish_reason,
            Attempt.FinishReason.TIMEOUT,
        )
        self.assertEqual(attempt.finished_at, deadline)
        self.assertEqual(attempt.finalized_at, future_now)

    def test_submitting_attempt_twice_does_not_duplicate_result(self):
        attempt = self.create_attempt()

        submit_attempt(attempt.id, self.student)
        submit_attempt(attempt.id, self.student)

        self.assertEqual(
            ExamResult.objects.filter(attempt=attempt).count(),
            1,
        )
    
    def create_other_student_attempt(self):
        other_student = User.objects.create_user(
            username="other_student_api",
            password="test-password",
            role=User.Role.STUDENT,
        )

        other_assignment = ExamAssignment.objects.create(
            publication=self.publication,
            student=other_student,
            source_group_ids=[],
        )

        attempt, created = start_attempt(
            self.exam.id,
            other_student,
        )

        self.assertTrue(created)
        self.assertEqual(attempt.assignment, other_assignment)

        return attempt

    def test_student_cannot_view_another_students_attempt(self):
        attempt = self.create_other_student_attempt()

        client = APIClient()
        client.force_authenticate(user=self.student)

        response = client.get(
            f"/api/v1/attempts/{attempt.id}/"
        )

        self.assertEqual(response.status_code, 404)

    def test_student_cannot_save_answer_to_another_students_attempt(self):
        attempt = self.create_other_student_attempt()

        client = APIClient()
        client.force_authenticate(user=self.student)

        response = client.put(
            f"/api/v1/attempts/{attempt.id}/answers/{self.question.id}/",
            {
                "value": str(self.correct_option.id),
                "base_revision": 0,
            },
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            Answer.objects.filter(
                attempt=attempt,
                question=self.question,
            ).exists()
        )

    def test_student_cannot_submit_another_students_attempt(self):
        attempt = self.create_other_student_attempt()

        client = APIClient()
        client.force_authenticate(user=self.student)

        response = client.post(
            f"/api/v1/attempts/{attempt.id}/submit/"
        )

        self.assertEqual(response.status_code, 404)

        attempt.refresh_from_db()

        self.assertEqual(
            attempt.status,
            Attempt.Status.IN_PROGRESS,
        )

    def test_unauthenticated_user_cannot_view_attempt(self):
        attempt = self.create_attempt()

        client = APIClient()

        response = client.get(
            f"/api/v1/attempts/{attempt.id}/"
        )

        self.assertEqual(response.status_code, 401)

    def test_student_can_view_own_attempt(self):
        attempt = self.create_attempt()

        client = APIClient()
        client.force_authenticate(user=self.student)

        response = client.get(
            f"/api/v1/attempts/{attempt.id}/"
        )

        self.assertEqual(response.status_code, 200)

