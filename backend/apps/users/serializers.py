from rest_framework import serializers

from .models import User


class UserProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "role",
            "is_active",
            "date_joined",
        ]
        read_only_fields = fields