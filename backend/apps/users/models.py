from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models

from .states import NG_STATES


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, password, **extra_fields):
        if not phone:
            raise ValueError("A phone number is required")
        user = self.model(phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, password, **extra_fields)

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("phone_verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True")

        return self._create_user(phone, password, **extra_fields)


class AvatarColor(models.TextChoices):
    MARIGOLD = "marigold", "Marigold"
    LIME = "lime", "Lime"
    SKY = "sky", "Sky"
    CORAL = "coral", "Coral"
    PAPER = "paper", "Paper"


class User(AbstractBaseUser, PermissionsMixin):
    # E.164, e.g. +2348031234567. Always stored via normalize_ng_phone().
    phone = models.CharField(max_length=14, unique=True)
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(blank=True)

    # Profile. Blank until the user fills it in on /profile/edit.
    state = models.CharField(max_length=20, choices=NG_STATES, blank=True)
    area = models.CharField(max_length=60, blank=True)
    bio = models.CharField(max_length=160, blank=True)
    avatar_color = models.CharField(max_length=10, choices=AvatarColor.choices, default=AvatarColor.MARIGOLD)

    # Separate from is_active: an unverified user exists but can't use the API.
    phone_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "phone"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return self.phone


class PhoneVerification(models.Model):
    """One OTP sent through the provider. The code itself is never stored.
    A code only works for the flow (purpose) it was sent for."""

    class Purpose(models.TextChoices):
        SIGNUP = "signup", "Sign up"
        PASSWORD_RESET = "password_reset", "Password reset"
        CHANGE_PHONE = "change_phone", "Change phone"
        CHANGE_PAYOUT = "change_payout", "Change payout account"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="phone_verifications")
    phone = models.CharField(max_length=14)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.SIGNUP)
    pin_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    used = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["phone", "purpose", "-created_at"])]

    def __str__(self):
        return f"{self.phone} ({self.created_at:%Y-%m-%d %H:%M})"
