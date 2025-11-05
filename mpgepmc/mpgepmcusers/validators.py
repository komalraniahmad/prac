import re
from datetime import date
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
# Import the new model to query validation rules
from mpgepmcusers.models import MobileValidationRule

# --- Constants for Validation ---
MIN_AGE = 12
MAX_AGE = 150
ALLOWED_DOMAINS = ['gmail.com', 'yahoo.com', 'mpgepmc.com']
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,52}$"

# Basic Email Format Regex (checks for username@domain.tld structure)
EMAIL_FORMAT_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

# Strict Name Validation Regex (A-Z, a-z, ., space, -, _)
NAME_REGEX = r"^[A-Za-z\s\-\._]+$"
MIN_NAME_LETTERS = 1
MAX_NAME_LETTERS = 64

# --- Validators ---

def mpgepmcusers_validate_name_format_and_length(value, field_name):
    """
    Validates name format (only allows letters, spaces, periods, hyphens, and underscores)
    and ensures the letter count is between 1 and 64 (ignoring non-letter characters in the count).
    
    NEW RULES:
    1. Must not end with space, -, or _.
    2. Must contain at least one character that is NOT a space, -, or _.
    """
    if not value:
        raise ValidationError(_('This field is required.'), code='required')

    # Rule 1 & 2: Check for forbidden trailing characters and minimum meaningful content
    # Note: Middle Name is optional in the model, but if a value is provided here (i.e., not blank/null),
    # it must pass these checks.
    
    # Check if the value is solely composed of invalid separator characters
    # If the value only contains spaces, hyphens, or underscores (and is not empty), it's invalid.
    meaningful_chars_present = any(char.isalpha() or char == '.' for char in value)
    if not meaningful_chars_present and field_name != 'Middle Name': # Apply stricter to First/Last Name
        raise ValidationError(
            _('%(field_name)s must contain at least one letter.'),
            params={'field_name': field_name},
            code='only_separators'
        )
    # Stricter check for First/Last Name: they cannot be just one of the separators
    if field_name != 'Middle Name' and len(value.strip(' -_')) == 0:
        raise ValidationError(
            _('%(field_name)s cannot be empty or only consist of spaces, hyphens, or underscores.'),
            params={'field_name': field_name},
            code='insufficient_content'
        )


    # Check for forbidden trailing characters
    if value.endswith((' ', '-', '_')):
        raise ValidationError(
            _('%(field_name)s cannot end with a space, hyphen (-), or underscore (_).'),
            params={'field_name': field_name},
            code='trailing_separator'
        )

    # Check for general allowed characters
    if not re.fullmatch(NAME_REGEX, value):
        raise ValidationError(
            _('%(field_name)s contains invalid characters. Only letters, spaces, periods (.), hyphens (-), and underscores (_) are allowed.'),
            params={'field_name': field_name},
            code='invalid_name_format'
        )

    # Check letter count (1 to 64)
    letter_count = sum(1 for char in value if char.isalpha())
    if letter_count < MIN_NAME_LETTERS:
        raise ValidationError(
            _('%(field_name)s must contain at least %(min)s letters (non-letter characters are ignored).'),
            params={'field_name': field_name, 'min': MIN_NAME_LETTERS},
            code='name_too_short'
        )
    if letter_count > MAX_NAME_LETTERS:
        # Note: The max length for the CharField is 64, which is checked by Django's form/model validation.
        # This check is for the *letter* count specifically. Keeping it for consistency.
        raise ValidationError(
            _('%(field_name)s cannot contain more than %(max)s letters (non-letter characters are ignored).'),
            params={'field_name': field_name, 'max': MAX_NAME_LETTERS},
            code='name_too_long'
        )


def mpgepmcusers_validate_birth_date(value):
    """
    Validates the date of birth, ensuring the user is between MIN_AGE (12) and MAX_AGE (150).
    """
    today = date.today()
    age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))

    if age < MIN_AGE:
        raise ValidationError(
            _('you are under age %(min_age)s yrs'),
            params={'min_age': MIN_AGE},
            code='too_young'
        )
    if age > MAX_AGE:
        raise ValidationError(
            _('you are over age %(max_age)s yrs'),
            params={'max_age': MAX_AGE},
            code='too_old'
        )

def mpgepmcusers_validate_email(value): 
    """
    Validates if the email has a basic valid format (username@domain) and 
    belongs to one of the allowed domains.
    """
    if not re.fullmatch(EMAIL_FORMAT_REGEX, value):
        raise ValidationError(
            _('Enter a valid email address with a username and domain.'),
            code='invalid_email_format'
        )

    domain = value.split('@')[-1].lower()
    allowed_domains_str = ', '.join(ALLOWED_DOMAINS)
    if domain not in ALLOWED_DOMAINS:
        raise ValidationError(
            _('Invalid email domain. Must be one of: %(domains)s.'),
            params={'domains': allowed_domains_str},
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
    Validates the mobile number against country-specific rules fetched from the MobileValidationRule model.
    """
    # 1. Find the matching MobileValidationRule based on the prefix
    rule = None
    # Use .iterator() for potentially large tables for memory efficiency, though .all() is fine for small tables.
    all_rules = MobileValidationRule.objects.all()
    allowed_country_codes = [r.country_code for r in all_rules]

    for r in all_rules:
        if value.startswith(r.country_code):
            rule = r
            break
            
    if not rule:
        # If no supported country code is found
        allowed_codes_str = ', '.join(allowed_country_codes) if allowed_country_codes else 'None defined'
        raise ValidationError(
            _('Mobile number must start with a valid country code: %(codes)s.'),
            params={'codes': allowed_codes_str},
            code='invalid_country_code'
        )

    # 2. Extract country-specific rules
    country_code = rule.country_code
    # The operator_codes field is treated as a raw regex segment
    operator_regex_segment = rule.operator_codes.strip()
    user_length = rule.user_number_length
    example = rule.example_format
    
    # 3. Construct the dynamic regex pattern
    # Pattern: ^(Country Code)(Operator Regex Segment)(\d{User Length})$
    dynamic_regex = rf"^{re.escape(country_code)}({operator_regex_segment})(\d{{{user_length}}})$"
    
    # 4. Perform the final validation
    if not re.fullmatch(dynamic_regex, value):
        # Specific error message tailored to the country's rules
        raise ValidationError(
            _('Invalid mobile number format for %(country_code)s. Expected format (example: %(example)s) with a valid operator code and %(length)s user digits. Check Admin for allowed operator codes.'),
            params={
                'country_code': country_code, 
                'length': user_length, 
                'example': example,
            },
            code='invalid_mobile_number_format'
        )