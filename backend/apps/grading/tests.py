
from decimal import Decimal
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.users.models import User
from apps.exams.models import (
    Exam,
    ExamPublication,
    ExamAssignment,
    PublishedQuestion,
    PublishedOption,
)
from apps.attempts.models import Attempt
from apps.answers.models import Answer
from apps.results.models import ExamResult

from .models import Grade
from .services import (
    GradingError,
    grade_submitted_attempt,
    grade_text_answer,
    release_exam_result,
)


class GradingServiceTests(TestCase):

    def setUp(self):
        now = timezone.now()

        self.teacher = User.objects.create_user(
            username="grading_teacher",
            password="test-password",
            role=User.Role.TEACHER,
        )

        self.other_teacher = User.objects.create_user(
            username="other_grading_teacher",
            password="test-password",
            role=User.Role.TEACHER,
        )

        self.student = User.objects.create_user(
            username="grading_student",
            password="test-password",
            role=User.Role.STUDENT,
        )

        self.exam = Exam.objects.create(
            owner=self.teacher,
            name="Экзамен для проверки",
            instructions="Инструкция",
            opens_at=now - timedelta(minutes=10),
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

        self.choice_question = PublishedQuestion.objects.create(
            publication=self.publication,
            title="Сколько будет 2 + 2?",
            question_type="single_choice",
            position=1,
            points=5,
        )

        self.correct_option = PublishedOption.objects.create(
            question=self.choice_question,
            text="4",
            is_correct=True,
            order=1,
        )

        self.wrong_option = PublishedOption.objects.create(
            question=self.choice_question,
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

        self.attempt = Attempt.objects.create(
            assignment=self.assignment,
            started_at=now - timedelta(minutes=20),
            deadline_at=now + timedelta(minutes=40),
            status=Attempt.Status.SUBMITTED,
            finished_at=now,
            finalized_at=now,
            finish_reason=Attempt.FinishReason.MANUAL,
        )

        self.choice_answer = Answer.objects.create(
            attempt=self.attempt,
            question=self.choice_question,
            value=str(self.correct_option.id),
            revision=1,
        )

        self.text_answer = Answer.objects.create(
            attempt=self.attempt,
            question=self.text_question,
            value="Потому что 2 + 2 = 4",
            revision=1,
        )

    def test_submitted_attempt_is_graded_automatically(self):
        result = grade_submitted_attempt(self.attempt.id)

        self.assertEqual(
            result.status,
            ExamResult.Status.PENDING,
        )

        choice_grade = Grade.objects.get(
            answer=self.choice_answer,
        )

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        self.assertEqual(
            choice_grade.grading_type,
            Grade.GradingType.AUTOMATIC,
        )
        self.assertEqual(
            choice_grade.status,
            Grade.Status.COMPLETED,
        )
        self.assertEqual(
            choice_grade.points_awarded,
            Decimal("5"),
        )
        self.assertTrue(choice_grade.is_correct)

        self.assertEqual(
            text_grade.grading_type,
            Grade.GradingType.MANUAL,
        )
        self.assertEqual(
            text_grade.status,
            Grade.Status.PENDING,
        )
        self.assertEqual(
            text_grade.points_awarded,
            Decimal("0"),
        )

    def test_grading_is_idempotent(self):
        first_result = grade_submitted_attempt(
            self.attempt.id,
        )

        second_result = grade_submitted_attempt(
            self.attempt.id,
        )

        self.assertEqual(first_result.id, second_result.id)
        self.assertEqual(
            Grade.objects.filter(
                answer__attempt=self.attempt,
            ).count(),
            2,
        )
        self.assertEqual(
            ExamResult.objects.filter(
                attempt=self.attempt,
            ).count(),
            1,
        )

    def test_manual_text_grading_completes_result(self):
        result = grade_submitted_attempt(
            self.attempt.id,
        )

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        result = grade_text_answer(
            grade_id=text_grade.id,
            teacher=self.teacher,
            points_awarded=Decimal("4"),
            feedback="Хорошее объяснение.",
        )

        text_grade.refresh_from_db()

        self.assertEqual(
            text_grade.status,
            Grade.Status.COMPLETED,
        )
        self.assertEqual(
            text_grade.points_awarded,
            Decimal("4"),
        )
        self.assertEqual(
            text_grade.graded_by,
            self.teacher,
        )
        self.assertEqual(
            text_grade.feedback,
            "Хорошее объяснение.",
        )

        self.assertEqual(
            result.status,
            ExamResult.Status.READY,
        )
        self.assertEqual(
            result.total_points,
            Decimal("10"),
        )
        self.assertEqual(
            result.earned_points,
            Decimal("9"),
        )
        self.assertEqual(
            result.percentage,
            Decimal("90.00"),
        )
        self.assertTrue(result.is_passed)

    def test_another_teacher_cannot_grade_answer(self):
        grade_submitted_attempt(self.attempt.id)

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        with self.assertRaises(GradingError) as context:
            grade_text_answer(
                grade_id=text_grade.id,
                teacher=self.other_teacher,
                points_awarded=Decimal("4"),
                feedback="Проверка",
            )

        self.assertEqual(
            context.exception.code,
            "permission_denied",
        )
        self.assertEqual(
            context.exception.status_code,
            403,
        )

    def test_manual_grade_cannot_exceed_question_points(self):
        grade_submitted_attempt(self.attempt.id)

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        with self.assertRaises(GradingError) as context:
            grade_text_answer(
                grade_id=text_grade.id,
                teacher=self.teacher,
                points_awarded=Decimal("6"),
            )

        self.assertEqual(
            context.exception.code,
            "invalid_points",
        )

    def test_completed_grade_cannot_be_graded_again(self):
        grade_submitted_attempt(self.attempt.id)

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        grade_text_answer(
            grade_id=text_grade.id,
            teacher=self.teacher,
            points_awarded=Decimal("4"),
        )

        with self.assertRaises(GradingError) as context:
            grade_text_answer(
                grade_id=text_grade.id,
                teacher=self.teacher,
                points_awarded=Decimal("5"),
            )

        self.assertEqual(
            context.exception.code,
            "grade_already_completed",
        )

    def test_result_cannot_be_released_before_manual_grading(self):
        result = grade_submitted_attempt(self.attempt.id)

        with self.assertRaises(GradingError) as context:
            release_exam_result(
                result.id,
                self.teacher,
            )

        self.assertEqual(
            context.exception.code,
            "result_not_ready",
        )

    def test_only_exam_owner_can_release_result(self):
        result = grade_submitted_attempt(self.attempt.id)

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        result = grade_text_answer(
            grade_id=text_grade.id,
            teacher=self.teacher,
            points_awarded=Decimal("4"),
        )

        with self.assertRaises(GradingError) as context:
            release_exam_result(
                result.id,
                self.other_teacher,
            )

        self.assertEqual(
            context.exception.code,
            "permission_denied",
        )

    def test_owner_can_release_result(self):
        result = grade_submitted_attempt(self.attempt.id)

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        result = grade_text_answer(
            grade_id=text_grade.id,
            teacher=self.teacher,
            points_awarded=Decimal("4"),
        )

        released_result = release_exam_result(
            result.id,
            self.teacher,
        )

        self.assertEqual(
            released_result.status,
            ExamResult.Status.RELEASED,
        )
        self.assertEqual(
            released_result.released_by,
            self.teacher,
        )
        self.assertIsNotNone(released_result.released_at)

    def test_releasing_result_twice_is_safe(self):
        result = grade_submitted_attempt(self.attempt.id)

        text_grade = Grade.objects.get(
            answer=self.text_answer,
        )

        result = grade_text_answer(
            grade_id=text_grade.id,
            teacher=self.teacher,
            points_awarded=Decimal("4"),
        )

        first_release = release_exam_result(
            result.id,
            self.teacher,
        )

        second_release = release_exam_result(
            result.id,
            self.teacher,
        )

        self.assertEqual(
            first_release.id,
            second_release.id,
        )
        self.assertEqual(
            second_release.status,
            ExamResult.Status.RELEASED,
        )
