from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.utils import timezone
from datetime import timedelta
from mpgepmc.settings import OTP_EXPIRY_TIME 

# --- GENDER CONSTANTS & CHOICES ---
MALE = 'M'
FEMALE = 'F'
OTHER = 'O' # Constant for 'Other' choice

# Use the constants for GENDER_CHOICES
GENDER_CHOICES = [
    (MALE, 'Male'),
    (FEMALE, 'Female'),
    # Updated choice text to align with conditional form logic
    (OTHER, 'Other (must specify)'),
]
# --- END GENDER CONSTANTS & CHOICES ---


# Custom Manager for mpgepmcusersUser
class mpgepmcusersUserManager(BaseUserManager):
    """
    Custom manager for the mpgepmcusersUser model.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        # Set is_active=False by default for new users awaiting verification
        user.is_active = extra_fields.pop('is_active', False) 
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True) # Superusers are active immediately
        extra_fields.setdefault('first_name', 'Admin')
        extra_fields.setdefault('last_name', 'User')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(email, password, **extra_fields)


# Custom User Model
class mpgepmcusersUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model with required fields and prefix, including custom_gender.
    """
    
    # Expose the choices on the model for forms/views to easily access
    GENDER_CHOICES = GENDER_CHOICES
    
    # Required Fields
    first_name = models.CharField(max_length=64)
    middle_name = models.CharField(max_length=64, blank=True, null=True) # Optional
    last_name = models.CharField(max_length=64)
    
    # Gender field using the defined constants and choices
    # FIX: Removed default=MALE so no gender is selected by default.
    gender = models.CharField(
        max_length=1, 
        choices=GENDER_CHOICES,
        # default=MALE # Removed to enforce user selection
    )
    
    # NEW FIELD: Field to store the custom gender text if 'Other' is selected.
    custom_gender = models.CharField(
        max_length=64,  
        blank=True, 
        null=True, 
        verbose_name='Specify Gender (if Other selected)'
    )
    
    date_of_birth = models.DateField()
    email = models.EmailField(unique=True)
    mobile_number = models.CharField(max_length=15, unique=True) # 9 to 15 digits for international

    # Status Fields
    is_active = models.BooleanField(default=False) # Must be False until OTP is verified
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    
    # NEW FIELD: Last time the user changed their password (for throttling)
    last_password_change = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'gender', 'date_of_birth', 'mobile_number']

    objects = mpgepmcusersUserManager()

    class Meta:
        verbose_name = 'mpgepmc User'
        verbose_name_plural = 'mpgepmc Users'

    def __str__(self):
        return self.email
        
    def get_full_name(self):
        """Returns the first_name plus the last_name, with a space in between."""
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        """Returns the short name for the user."""
        return self.first_name
        
    # FIX: Added a placeholder method to satisfy the resend throttle check in views.py
    def get_otp_resend_throttle(self):
        """Returns the throttle duration (e.g., 60 seconds) as a timedelta."""
        # Using a very short duration here, as the new rule is to throttle until expiry.
        # This method is now OBSOLETE based on the new logic, but kept for compatibility.
        # The core resend logic is moved to check against the full expiry time in views.py.
        return timedelta(seconds=1) 

# OTP Verification Model
class mpgepmcusersOTP(models.Model):
    """
    Model to store OTP for email verification with expiry.
    """
    user = models.OneToOneField(mpgepmcusersUser, on_delete=models.CASCADE, related_name='otp_record')
    otp_code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    # NEW FIELD: Tracks failed verification attempts
    fail_attempts = models.PositiveSmallIntegerField(default=0) 
    # NEW FIELD: Marks the OTP as invalid due to too many attempts
    invalidated = models.BooleanField(default=False) 

    class Meta:
        verbose_name = 'mpgepmc OTP Record'
        verbose_name_plural = 'mpgepmc OTP Records'

    def is_expired(self):
        """Checks if the OTP has expired."""
        return timezone.now() > self.expires_at

    def is_valid_and_not_expired(self):
        """Checks if the OTP is currently usable."""
        return not self.is_expired() and not self.invalidated

    def save(self, *args, **kwargs):
        """Sets the expiry time before saving if not already set."""
        # Use OTP_EXPIRY_TIME from settings
        # FIX: The expiry time should be set *only* when the object is created
        # or explicitly when the OTP is regenerated, not on every save.
        if not self.id or (hasattr(self, '_regenerate') and self._regenerate): 
            self.expires_at = timezone.now() + OTP_EXPIRY_TIME
            if self.id: # Reset attempts/invalidated state on regeneration
                self.fail_attempts = 0
                self.invalidated = False
            
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"OTP for {self.user.email}"
        
# NEW MODEL: Password Reset Token
class mpgepmcusersPasswordResetToken(models.Model):
    """
    Model to store a one-time token for unauthenticated password resets.
    Expiry is set to 2 hours (120 minutes).
    """
    
    # Expiry time for the reset link (2 hours)
    RESET_TOKEN_EXPIRY = timedelta(hours=2) 
    
    user = models.OneToOneField(
        mpgepmcusersUser, 
        on_delete=models.CASCADE, 
        related_name='reset_token'
    )
    token = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    # To prevent replay attacks after a successful reset
    is_used = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Password Reset Token'
        verbose_name_plural = 'Password Reset Tokens'

    def is_expired(self):
        """Checks if the token has expired."""
        return timezone.now() > self.expires_at

    def is_valid(self):
        """Checks if the token is currently usable."""
        return not self.is_expired() and not self.is_used

    def save(self, *args, **kwargs):
        """Sets the expiry time before saving if not already set."""
        if not self.id:
            self.expires_at = timezone.now() + self.RESET_TOKEN_EXPIRY
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"Reset Token for {self.user.email}"


# --- NEW MODEL FOR DYNAMIC MOBILE VALIDATION RULES ---
class MobileValidationRule(models.Model):
    # ... (rest of MobileValidationRule remains the same)
    """
    Stores country-specific mobile number validation rules.
    """
    # E.g., +92, +1, +91
    country_code = models.CharField(
        max_length=5, 
        unique=True, 
        verbose_name='Country Code (e.g., +92)'
    )
    # Comma-separated list of allowed operator/area code prefixes. E.g., 300-355 for Pakistan.
    # The validator will convert this into a regex group.
    operator_codes = models.TextField(
        verbose_name='Allowed Operator Codes (Provide as Regex Segment)'
    )
    # The required length of the user's number part, following the operator code. E.g., 7 for Pakistan.
    user_number_length = models.PositiveSmallIntegerField(
        verbose_name='User Number Length (digits)'
    )
    # Example format to show the user/admin
    example_format = models.CharField(
        max_length=64,
        verbose_name='Example Format (e.g., +923XXYYYYYYY)'
    )

    class Meta:
        verbose_name = 'Mobile Validation Rule'
        verbose_name_plural = 'Mobile Validation Rules'

    def __str__(self):
        return f"Rule for {self.country_code}"


