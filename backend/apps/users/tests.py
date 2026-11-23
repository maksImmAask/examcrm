from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from rest_framework_simplejwt.tokens import RefreshToken

from .models import User


class JWTAuthenticationTests(APITestCase):

    def setUp(self):
        self.password = "TestPassword123!"

        self.student = User.objects.create_user(
            username="student_test",
            password=self.password,
            first_name="Test",
            last_name="Student",
            email="student@test.com",
            role=User.Role.STUDENT,
        )

        self.teacher = User.objects.create_user(
            username="teacher_test",
            password=self.password,
            role=User.Role.TEACHER,
        )

        self.admin = User.objects.create_user(
            username="admin_test",
            password=self.password,
            role=User.Role.ADMIN,
        )

        self.token_url = reverse("token-obtain")
        self.refresh_url = reverse("token-refresh")
        self.verify_url = reverse("token-verify")
        self.profile_url = reverse("current-user")

    def get_access_token(self, user):
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)

    def test_student_can_obtain_jwt_tokens(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "student_test",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_teacher_can_obtain_jwt_tokens(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "teacher_test",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_admin_can_obtain_jwt_tokens(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "admin_test",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "student_test",
                "password": "WrongPassword123!",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_unknown_username_is_rejected(self):
        response = self.client.post(
            self.token_url,
            {
                "username": "unknown_user",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_inactive_user_cannot_obtain_tokens(self):
        self.student.is_active = False
        self.student.save(update_fields=["is_active"])

        response = self.client.post(
            self.token_url,
            {
                "username": "student_test",
                "password": self.password,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_profile_requires_authentication(self):
        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_student_can_get_own_profile(self):
        access = self.get_access_token(self.student)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["username"],
            self.student.username,
        )

        self.assertEqual(
            response.data["role"],
            User.Role.STUDENT,
        )

    def test_teacher_can_get_own_profile(self):
        access = self.get_access_token(self.teacher)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["role"],
            User.Role.TEACHER,
        )

    def test_admin_can_get_own_profile(self):
        access = self.get_access_token(self.admin)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["role"],
            User.Role.ADMIN,
        )

    def test_profile_does_not_expose_password(self):
        access = self.get_access_token(self.student)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        response = self.client.get(self.profile_url)

        self.assertNotIn("password", response.data)

    def test_refresh_token_returns_new_access_token(self):
        refresh = RefreshToken.for_user(self.student)

        response = self.client.post(
            self.refresh_url,
            {
                "refresh": str(refresh),
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_invalid_refresh_token_is_rejected(self):
        response = self.client.post(
            self.refresh_url,
            {
                "refresh": "invalid.refresh.token",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_valid_access_token_can_be_verified(self):
        access = self.get_access_token(self.student)

        response = self.client.post(
            self.verify_url,
            {
                "token": access,
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_invalid_access_token_cannot_be_verified(self):
        response = self.client.post(
            self.verify_url,
            {
                "token": "invalid.token.value",
            },
            format="json",
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED,
        )

    def test_profile_does_not_allow_role_modification(self):
        access = self.get_access_token(self.student)

        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}"
        )

        response = self.client.get(self.profile_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

        self.assertEqual(
            response.data["role"],
            User.Role.STUDENT,
        )