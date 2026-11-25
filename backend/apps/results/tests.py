
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from apps.users.models import User
from apps.exams.models import Exam, ExamPublication, ExamAssignment
from apps.attempts.models import Attempt

from .models import ExamResult


class StudentResultsAPITests(TestCase):

    def setUp(self):
        now = timezone.now()

        self.teacher = User.objects.create_user(
            username="results_teacher",
            password="test-password",
            role=User.Role.TEACHER,
        )

        self.student = User.objects.create_user(
            username="results_student",
            password="test-password",
            role=User.Role.STUDENT,
        )

        self.other_student = User.objects.create_user(
            username="other_results_student",
            password="test-password",
            role=User.Role.STUDENT,
        )

        self.exam = Exam.objects.create(
            owner=self.teacher,
            name="Results API Test",
            instructions="Test instructions",
            opens_at=now - timedelta(hours=1),
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

        self.other_assignment = ExamAssignment.objects.create(
            publication=self.publication,
            student=self.other_student,
            source_group_ids=[],
        )

        self.attempt = Attempt.objects.create(
            assignment=self.assignment,
            started_at=now - timedelta(minutes=30),
            deadline_at=now + timedelta(minutes=30),
            status=Attempt.Status.SUBMITTED,
            finished_at=now,
            finalized_at=now,
            finish_reason=Attempt.FinishReason.MANUAL,
        )

        self.other_attempt = Attempt.objects.create(
            assignment=self.other_assignment,
            started_at=now - timedelta(minutes=30),
            deadline_at=now + timedelta(minutes=30),
            status=Attempt.Status.SUBMITTED,
            finished_at=now,
            finalized_at=now,
            finish_reason=Attempt.FinishReason.MANUAL,
        )

        self.result = ExamResult.objects.create(
            attempt=self.attempt,
            total_points=10,
            earned_points=8,
            percentage=80,
            is_passed=True,
            status=ExamResult.Status.RELEASED,
            calculated_at=now,
            released_at=now,
            released_by=self.teacher,
        )

        self.other_result = ExamResult.objects.create(
            attempt=self.other_attempt,
            total_points=10,
            earned_points=5,
            percentage=50,
            is_passed=False,
            status=ExamResult.Status.RELEASED,
            calculated_at=now,
            released_at=now,
            released_by=self.teacher,
        )

        self.client = APIClient()
        self.client.force_authenticate(user=self.student)

    def test_student_can_view_own_results(self):
        response = self.client.get("/api/v1/results/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            str(response.data[0]["id"]),
            str(self.result.id),
        )

    def test_student_cannot_see_other_student_results(self):
        response = self.client.get("/api/v1/results/")

        result_ids = [
            str(item["id"])
            for item in response.data
        ]

        self.assertNotIn(
            str(self.other_result.id),
            result_ids,
        )

    
    def test_student_can_view_own_released_result(self):
        response = self.client.get(
            f"/api/v1/results/{self.result.id}/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            str(response.data["id"]),
            str(self.result.id),
        )


    def test_student_cannot_view_other_student_result(self):
        response = self.client.get(
            f"/api/v1/results/{self.other_result.id}/"
        )

        self.assertEqual(response.status_code, 404)

    
    def test_student_cannot_view_unreleased_result(self):
        self.result.status = ExamResult.Status.PENDING
        self.result.save(update_fields=["status"])

        response = self.client.get(
            f"/api/v1/results/{self.result.id}/"
        )

        self.assertEqual(response.status_code, 404)


    def test_unauthenticated_user_cannot_view_results(self):
        client = APIClient()

        response = client.get("/api/v1/results/")

        self.assertEqual(response.status_code, 401)

    def test_teacher_cannot_use_student_results_api(self):
        client = APIClient()
        client.force_authenticate(user=self.teacher)

        response = client.get("/api/v1/results/")

        self.assertEqual(response.status_code, 403)
