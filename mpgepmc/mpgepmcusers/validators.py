import re
from datetime import date
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

# --- Constants for Validation ---
MIN_AGE = 12
MAX_AGE = 150
ALLOWED_DOMAINS = ['gmail.com', 'yahoo.com', 'mpgepmc.com']
PASSWORD_REGEX = r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*#?&])[A-Za-z\d@$!%*#?&]{8,52}$"

# NEW CONSTANT: Dynamic Mobile Number Rules
# Key: Country Code (string)
# Value: Dictionary with 'operator_regex' (string) and 'user_length' (int)
# Note: The operator regex should NOT include the country code.
MOBILE_RULES = {
    # Pakistan (+92)
    '+92': {
        # Operator Codes: 300-355. User Number Length: 7 digits.
        'operator_regex': r'3(?:[0-5][0-9]|5[0-5])', 
        'user_length': 7, 
        'example': '+923XXYYYYYYY (7 digits)'
    },
    # USA/Canada (+1) - Using common 3-digit area code, then 7 digits (Total 10 after +1)
    '+1': {
        # Operator (Area) Codes: 200-999 (excluding some reserved ranges for simplicity). User Number Length: 7 digits.
        'operator_regex': r'[2-9]\d{2}', 
        'user_length': 7, 
        'example': '+1AAAXXXXXXX (10 digits)'
    },
    # India (+91)
    '+91': {
        # Operator Codes: 6, 7, 8, or 9 followed by 9 digits. User Number Length: 9 digits.
        'operator_regex': r'[6-9]\d', 
        'user_length': 8, # 10 digits total (2 for operator + 8 for user number)
        'example': '+91XXYYYYYYYYYY (10 digits)'
    },
}

# Calculated Constant: Allowed Country Codes for quicker reference
ALLOWED_COUNTRY_CODES = list(MOBILE_RULES.keys())

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
    """
    if not value:
        raise ValidationError(_('This field is required.'), code='required')

    if not re.fullmatch(NAME_REGEX, value):
        raise ValidationError(
            _('%(field_name)s contains invalid characters. Only letters, spaces, periods (.), hyphens (-), and underscores (_) are allowed.'),
            params={'field_name': field_name},
            code='invalid_name_format'
        )

    letter_count = sum(1 for char in value if char.isalpha())
    if letter_count < MIN_NAME_LETTERS:
        raise ValidationError(
            _('%(field_name)s must contain at least %(min)s letters (non-letter characters are ignored).'),
            params={'field_name': field_name, 'min': MIN_NAME_LETTERS},
            code='name_too_short'
        )
    if letter_count > MAX_NAME_LETTERS:
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
    Validates the mobile number against country-specific rules for operator code and user number length.
    """
    # 1. Check for valid country code prefix
    country_code = next((cc for cc in ALLOWED_COUNTRY_CODES if value.startswith(cc)), None)

    if not country_code:
        # If no supported country code is found
        allowed_codes_str = ', '.join(ALLOWED_COUNTRY_CODES)
        raise ValidationError(
            _('Mobile number must start with a valid country code: %(codes)s.'),
            params={'codes': allowed_codes_str},
            code='invalid_country_code'
        )

    # 2. Extract country-specific rules
    rules = MOBILE_RULES[country_code]
    operator_regex = rules['operator_regex']
    user_length = rules['user_length']
    example = rules['example']
    
    # 3. Construct the dynamic regex pattern
    # Pattern: ^(Country Code)(Operator Regex)(\d{User Length})$
    dynamic_regex = rf"^{re.escape(country_code)}({operator_regex})(\d{{{user_length}}})$"
    
    # 4. Perform the final validation
    if not re.fullmatch(dynamic_regex, value):
        # Specific error message tailored to the country's rules
        raise ValidationError(
            _('Invalid mobile number format for %(country_code)s. Expected format (example: %(example)s) with valid operator code and %(length)s user digits.'),
            params={'country_code': country_code, 'length': user_length, 'example': example},
            code='invalid_mobile_number_format'
        )