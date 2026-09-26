import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import User
from .phone import mask_phone, normalize_ng_phone

# Letters (any script, so Ọ, Ẹ, Ṣ etc. work) plus spaces, hyphens, apostrophes.
NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '’\-]+[^\W\d_]+)*[’']?$")


class PhoneField(serializers.CharField):
    """Accepts 0803…, 803…, +234803… or 234803…; returns E.164."""

    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        try:
            return normalize_ng_phone(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from None


def validate_name(value, label):
    value = " ".join(value.split())
    if not (2 <= len(value) <= 50) or not NAME_RE.match(value):
        raise serializers.ValidationError(f"Enter your {label} (2–50 letters).")
    return value


def validate_new_password(attrs, user=None, password_key="password", confirm_key="password_confirm"):
    """Django's password validators plus the confirm match. Raises field errors."""
    errors = {}
    try:
        validate_password(attrs[password_key], user)
    except DjangoValidationError as exc:
        errors[password_key] = exc.messages
    if attrs[password_key] != attrs[confirm_key]:
        errors[confirm_key] = ["Passwords don’t match yet."]
    if errors:
        raise serializers.ValidationError(errors)


class UserSerializer(serializers.ModelSerializer):
    """The signed-in user. The full phone number never leaves the server."""

    masked_phone = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "masked_phone",
            "state",
            "area",
            "bio",
            "avatar_color",
            "date_joined",
            "phone_verified",
        ]
        read_only_fields = fields

    def get_masked_phone(self, user):
        return mask_phone(user.phone)


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/me/. Anything else in the payload (phone included) is ignored."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "state", "area", "bio", "avatar_color"]

    def validate_first_name(self, value):
        return validate_name(value, "first name")

    def validate_last_name(self, value):
        return validate_name(value, "last name")

    def validate_area(self, value):
        value = " ".join(value.split())
        if value and len(value) < 2:
            raise serializers.ValidationError("Enter your area or town (2–60 characters).")
        return value

    def validate_bio(self, value):
        return value.strip()


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=100)
    last_name = serializers.CharField(max_length=100)
    phone = PhoneField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    password_confirm = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_first_name(self, value):
        return validate_name(value, "first name")

    def validate_last_name(self, value):
        return validate_name(value, "last name")

    def validate(self, attrs):
        validate_new_password(attrs)
        return attrs


class PhoneOnlySerializer(serializers.Serializer):
    phone = PhoneField()


class VerifyOtpSerializer(serializers.Serializer):
    phone = PhoneField()
    code = serializers.RegexField(r"^\d{6}$", error_messages={"invalid": "Enter the 6-digit code."})


class LoginSerializer(serializers.Serializer):
    # Plain strings: a malformed phone must fail exactly like a wrong password.
    phone = serializers.CharField()
    password = serializers.CharField(trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    """Shape and password rules only; the view checks the current password."""

    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False)
    new_password_confirm = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        validate_new_password(attrs, self.context["user"], "new_password", "new_password_confirm")
        return attrs


class PasswordResetConfirmSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False)
    new_password_confirm = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        validate_new_password(attrs, None, "new_password", "new_password_confirm")
        return attrs
