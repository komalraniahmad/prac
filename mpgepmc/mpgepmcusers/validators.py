import re
from datetime import date
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# --- Constants for Validation ---
MIN_AGE = 12
MAX_AGE = 150
ALLOWED_DOMAINS = ['gmail.com', 'yahoo.com', 'mpgepmc.com']
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,52}$"
MOBILE_REGEX = r"^\+?1?\d{9,15}$" # Basic international phone number format (9 to 15 digits)

# --- Validators ---

def mpgepmcusers_validate_birth_date(value):
    """
    Validates if the date of birth corresponds to a minimum age of 12
    and a maximum age of 150.
    """
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

    if age < MIN_AGE:
        # FIXED: Professional Age Error Message
        raise ValidationError(
            _('You must be at least 12 years old to register.'),
            code='too_young'
        )
    if age > MAX_AGE:
        raise ValidationError(
            _('Date of birth is invalid. Maximum age allowed is 150 years.'),
            code='too_old'
        )

def mpgepmcusers_validate_email_domain(value):
    """
    Validates if the email belongs to one of the allowed domains.
    """
    domain = value.split('@')[-1].lower()
    if domain not in ALLOWED_DOMAINS:
        # FIXED: Professional Email Domain Error Message
        raise ValidationError(
            _('Invalid email domain. Must be one of: gmail.com, yahoo.com, or mpgepmc.com.'),
            code='invalid_domain'
        )

def mpgepmcusers_validate_password_complexity(value):
    """
    Validates password complexity: 8-52 chars, 1 small, 1 capital, 1 digit, 1 symbol.
    """
    if not re.fullmatch(PASSWORD_REGEX, value):
        raise ValidationError(
            _('Password must be 8-52 characters long and contain at least 1 small letter, 1 capital letter, 1 digit, and 1 symbol.'),
            code='invalid_password_complexity'
        )

def mpgepmcusers_validate_mobile_number(value):
    """
    Validates the mobile number format.
    """
    if not re.fullmatch(MOBILE_REGEX, value):
        raise ValidationError(
            _('Enter a valid mobile number (9 to 15 digits, optional +).'),
            code='invalid_mobile'
        )