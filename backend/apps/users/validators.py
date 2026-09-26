"""Password rules. They mirror the live checklist on the sign-up form:
"8+ characters" (Django's MinimumLengthValidator), "A number", "A capital letter".
"""

import re

from django.core.exceptions import ValidationError


class HasNumberValidator:
    message = "Password needs a number."

    def validate(self, password, user=None):
        if not re.search(r"\d", password or ""):
            raise ValidationError(self.message, code="password_no_number")

    def get_help_text(self):
        return "A number"


class HasUppercaseValidator:
    message = "Password needs a capital letter."

    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password or ""):
            raise ValidationError(self.message, code="password_no_upper")

    def get_help_text(self):
        return "A capital letter"
