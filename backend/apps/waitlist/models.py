from django.core.validators import RegexValidator
from django.db import models

from apps.users.states import NG_STATES


class WaitlistSignup(models.Model):
    """A pre-launch waitlist entry. One per phone; signing up again updates it."""

    class Role(models.TextChoices):
        BUY = 'buy', 'Buy'
        SELL = 'sell', 'Sell'
        BOTH = 'both', 'Both'
        VENDOR = 'vendor', 'Runs a declutter page'

    phone = models.CharField(
        max_length=14,
        unique=True,
        validators=[RegexValidator(r'^\+234[789][01]\d{8}$', 'Enter a Nigerian mobile number in E.164 form.')],
        help_text='E.164, e.g. +2348031234567',
    )
    state = models.CharField(max_length=20, choices=NG_STATES)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.BUY)
    source = models.CharField(max_length=200, blank=True, help_text='Referrer, or the host the form was on')
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # Set when the launch SMS goes out. TODO: Termii hook, sent per state at launch.
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.phone} ({self.get_state_display()})'
