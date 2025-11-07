from django import forms
from django.contrib.auth.forms import AuthenticationForm
# UPDATED IMPORT: Import GENDER_CHOICES and OTHER constant
from mpgepmcusers.models import mpgepmcusersUser, GENDER_CHOICES, OTHER
from mpgepmcusers.validators import (
    mpgepmcusers_validate_birth_date,
    mpgepmcusers_validate_mobile_number,
    mpgepmcusers_validate_password_complexity,
    mpgepmcusers_validate_name_format_and_length,
    mpgepmcusers_validate_email, # UPDATED: Renamed validator
)

# --- NEW CHOICES FOR THE CUSTOM GENDER DROPDOWN ---
CUSTOM_GENDER_OPTIONS = (
    ('', '--- Select a specified gender ---'),
    ('Non-binary', 'Non-binary'),
    ('Transgender', 'Transgender'),
    ('Prefer-not-to-say', 'Prefer not to say'),
)

# FIX: Add an empty choice to GENDER_CHOICES for the form to ensure no default selection
FORM_GENDER_CHOICES = (('', '--- Select your gender ---'),) + tuple(GENDER_CHOICES)


class mpgepmcusersSignupForm(forms.ModelForm):
    """
    Form for user registration, including password confirmation and 
    conditional validation for custom_gender.
    """
    # --- Custom Form Fields (Not in Model) ---
    password = forms.CharField(
        widget=forms.PasswordInput,
        label='Password',
        min_length=8,
        max_length=52,
        validators=[mpgepmcusers_validate_password_complexity],
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        label='Confirm Password',
        min_length=8,
        max_length=52,
    )

    # UPDATED FIELD: custom_gender is now a ChoiceField (Dropdown)
    custom_gender = forms.ChoiceField(
        choices=CUSTOM_GENDER_OPTIONS,
        required=False,
        label='Specify Gender (Dropdown)',
        widget=forms.Select(attrs={
            'id': 'id_custom_gender', 
            'placeholder': 'Please select a specified gender'
        })
    )
    
    # FIX: Override the gender field to use the FORM_GENDER_CHOICES with the empty option
    gender = forms.ChoiceField(
        choices=FORM_GENDER_CHOICES,
        required=True, # Explicitly required
        label='Gender',
    )


    class Meta:
        model = mpgepmcusersUser
        fields = (
            'first_name', 'middle_name', 'last_name', 'gender',
            'date_of_birth', 'email', 'mobile_number', 'custom_gender', # Include custom_gender
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'first_name': 'First Name',
            'middle_name': 'Middle Name (Optional)', 
            'last_name': 'Last Name',
            'mobile_number': 'Mobile Number',
        }
    
    # --- Initialization for Field Ordering ---
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Ensure 'custom_gender' is placed right after 'gender' for better UX
        field_order = list(self.fields.keys())
        if 'gender' in field_order and 'custom_gender' in field_order:
            gender_index = field_order.index('gender')
            
            # Remove 'custom_gender' from its current position
            field_order.pop(field_order.index('custom_gender'))
            # Insert 'custom_gender' after 'gender'
            field_order.insert(gender_index + 1, 'custom_gender')

        self.order_fields(field_order)

    # --- Custom Field Validation (clean_<field> methods) ---

    def clean_first_name(self):
        name = self.cleaned_data.get('first_name')
        mpgepmcusers_validate_name_format_and_length(name, 'First Name')
        return name

    # Middle Name is optional, only validate format if provided
    def clean_middle_name(self):
        name = self.cleaned_data.get('middle_name')
        if name:
            mpgepmcusers_validate_name_format_and_length(name, 'Middle Name')
        return name

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name')
        mpgepmcusers_validate_name_format_and_length(name, 'Last Name')
        return name

    # UPDATED: Clean method for gender - simplified to only check for selection
    def clean_gender(self):
        gender = self.cleaned_data.get('gender')
        
        if not gender:
            raise forms.ValidationError("You must select a gender.")
            
        # FIX: Removed conditional logic for custom_gender. Moved to global clean method.
        return gender
        
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            mpgepmcusers_validate_birth_date(dob)
        return dob

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # UPDATED: Use the combined email validator
            mpgepmcusers_validate_email(email)
            # Check uniqueness 
            if mpgepmcusersUser.objects.filter(email=email).exists():
                raise forms.ValidationError("This email is already registered.")
        return email

    def clean_mobile_number(self):
        mobile = self.cleaned_data.get('mobile_number')
        if mobile:
            mpgepmcusers_validate_mobile_number(mobile)
            # Check uniqueness
            if mpgepmcusersUser.objects.filter(mobile_number=mobile).exists():
                raise forms.ValidationError("This mobile number is already registered.")
        return mobile

    # --- Global Form Validation and Save ---

    def clean(self):
        """
        Global form validation, primarily for password matching and cross-field dependencies.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        gender = cleaned_data.get('gender')
        custom_gender = cleaned_data.get('custom_gender') # Check conditional value here

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")
        
        # FIX: Conditional Gender Specification Check moved to the global clean method
        if gender == OTHER and (not custom_gender or custom_gender.strip() == ''):
            # This is the check that was previously causing issues in clean_gender when it shouldn't
            self.add_error('custom_gender', "You must select an option from the dropdown when 'Other' is selected.")

        return cleaned_data

    def save(self, commit=True):
        """
        Create the user object and set the password.
        """
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])
        # is_active remains False, awaiting OTP verification
        
        # If the user selected 'Other' gender, set the custom_gender on the model instance
        if user.gender == OTHER:
            # The value is now one of the CUSTOM_GENDER_OPTIONS keys
            user.custom_gender = self.cleaned_data.get('custom_gender')
        else:
            # Ensure custom_gender is cleared if a standard gender is selected
            user.custom_gender = None
            
        if commit:
            user.save()
        return user


class mpgepmcusersSignInForm(AuthenticationForm):
    """
    Standard Django Authentication form.
    """
    pass

# --- NEW PASSWORD MANAGEMENT FORMS ---

class mpgepmcusersForgotPasswordForm(forms.Form):
    """
    Form to request a password reset link via email.
    """
    email = forms.EmailField(
        label='Email Address',
        max_length=254,
    )
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not mpgepmcusersUser.objects.filter(email__iexact=email).exists():
            # Hide the fact that an email does not exist to prevent user enumeration
            # We still return the email so the save/send process can skip without error
            pass 
        return email

class mpgepmcusersSetPasswordForm(forms.Form):
    """
    Form for setting a new password (used after a password reset link is clicked).
    """
    new_password = forms.CharField(
        widget=forms.PasswordInput,
        label='New Password',
        min_length=8,
        max_length=52,
        validators=[mpgepmcusers_validate_password_complexity],
    )
    new_password_confirm = forms.CharField(
        widget=forms.PasswordInput,
        label='Confirm New Password',
        min_length=8,
        max_length=52,
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        new_password_confirm = cleaned_data.get("new_password_confirm")

        if new_password and new_password_confirm and new_password != new_password_confirm:
            self.add_error('new_password_confirm', "Passwords do not match.")
            
        return cleaned_data


class mpgepmcusersChangePasswordForm(mpgepmcusersSetPasswordForm):
    """
    Form for authenticated users to change their password.
    Extends mpgepmcusersSetPasswordForm but adds the old password field.
    """
    old_password = forms.CharField(
        widget=forms.PasswordInput,
        label='Current Password',
    )
    
    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        # Check if the old password matches the current one
        if not self.user.check_password(old_password):
            raise forms.ValidationError("Your current password was entered incorrectly.")
        return old_password

    def clean(self):
        cleaned_data = super().clean()
        old_password = cleaned_data.get("old_password")
        new_password = cleaned_data.get("new_password")

        if old_password and new_password and self.user.check_password(new_password):
            # Prevent changing to the same password
            self.add_error('new_password', "The new password cannot be the same as the old password.")

        return cleaned_data