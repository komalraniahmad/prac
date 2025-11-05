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

# NEW CONSTANT: Strict Name Validation Regex (A-Z, a-z, ., space, -, _)
NAME_REGEX = r"^[A-Za-z\s\-\._]+$"
MIN_NAME_LETTERS = 1
MAX_NAME_LETTERS = 64

# --- Validators ---

def mpgepmcusers_validate_name_format_and_length(value, field_name):
    """
    Validates name format (only allows letters, spaces, periods, hyphens, and underscores)
    and ensures the letter count is between 1 and 64 (ignoring non-letter characters in the count).
    """
    if not value:
        # This case is primarily handled by the form's required=True/False, but acts as a safeguard
        raise ValidationError(_('This field is required.'), code='required')

    # 1. Check for invalid characters using the strict regex
    if not re.fullmatch(NAME_REGEX, value):
        raise ValidationError(
            _('Name can only contain letters (A-Z), spaces, periods (.), hyphens (-), and underscores (_). No numbers or other symbols allowed.'),
            code='invalid_name_format'
        )

    # 2. Check for letter count (min 1, max 64)
    # Count only the alphabetic characters in the string
    letter_count = len([c for c in value if c.isalpha()])

    if letter_count < MIN_NAME_LETTERS:
        # A name with only symbols/spaces is invalid based on 1-64 letter requirement
        raise ValidationError(
            _('%(field)s must contain at least 1 letter.', params={'field': field_name}),
            code='too_short'
        )
    if letter_count > MAX_NAME_LETTERS:
        raise ValidationError(
            _('%(field)s must not exceed 64 letters (spaces and symbols are ignored in the count).', params={'field': field_name}),
            code='too_long'
        )


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
            _('You must be at least %(min_age)s years old to register.', params={'min_age': MIN_AGE}),
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
    allowed_domains_str = ', '.join(ALLOWED_DOMAINS)
    if domain not in ALLOWED_DOMAINS:
        # FIXED: Professional Email Domain Error Message
        raise ValidationError(
            _('Invalid email domain. Must be one of: %(domains)s.', params={'domains': allowed_domains_str}),
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