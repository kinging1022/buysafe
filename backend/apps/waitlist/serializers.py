from rest_framework import serializers

from apps.users.states import NG_STATES

from .models import WaitlistSignup
from .phone import normalize_waitlist_phone

INVALID_PHONE_MESSAGE = 'Enter a Nigerian mobile number, like 0803 123 4567.'


class TruncatedCharField(serializers.CharField):
    """Optional attribution text: cut to fit rather than reject the signup."""

    def __init__(self, max_length, **kwargs):
        self.truncate_to = max_length
        super().__init__(required=False, allow_blank=True, default='', **kwargs)

    def to_internal_value(self, data):
        return super().to_internal_value(data)[: self.truncate_to]


class WaitlistSignupSerializer(serializers.Serializer):
    phone = serializers.CharField(max_length=40)
    state = serializers.ChoiceField(choices=NG_STATES)
    role = serializers.ChoiceField(choices=WaitlistSignup.Role.choices, default=WaitlistSignup.Role.BUY)
    source = TruncatedCharField(200)
    utm_source = TruncatedCharField(100)
    utm_medium = TruncatedCharField(100)
    utm_campaign = TruncatedCharField(100)

    def validate_phone(self, value):
        phone = normalize_waitlist_phone(value)
        if phone is None:
            raise serializers.ValidationError(INVALID_PHONE_MESSAGE)
        return phone
