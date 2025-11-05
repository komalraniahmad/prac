from django import forms
from django.contrib.auth.forms import AuthenticationForm
# UPDATED IMPORT: Import GENDER_CHOICES and OTHER constant
from mpgepmcusers.models import mpgepmcusersUser, GENDER_CHOICES, OTHER
from mpgepmcusers.validators import (
    mpgepmcusers_validate_birth_date,
    mpgepmcusers_validate_email_domain,
    mpgepmcusers_validate_mobile_number,
    mpgepmcusers_validate_password_complexity,
    mpgepmcusers_validate_name_format_and_length
)

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

    # NEW FIELD: custom_gender text input (used when 'gender' is 'OTHER')
    custom_gender = forms.CharField(
        required=False, # Required status is handled in clean_gender based on 'gender' value
        max_length=64,
        label='Specify Gender',
        widget=forms.TextInput(attrs={'placeholder': 'Please specify your gender'})
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

    # UPDATED: Clean method for gender and custom_gender
    def clean_gender(self):
        gender = self.cleaned_data.get('gender')
        custom_gender = self.cleaned_data.get('custom_gender')

        if gender == OTHER: # 'O' for Other
            # 1. Check required value
            if not custom_gender or custom_gender.strip() == '':
                raise forms.ValidationError("You must specify your gender in the text box when 'Other' is selected.")
            
            # 2. Validate format of custom_gender
            try:
                # Use the existing name validator for the custom gender text
                mpgepmcusers_validate_name_format_and_length(custom_gender, 'Custom Gender')
            except Exception as e:
                # Re-raise with a specific error message
                error_message = str(e)
                # Clean up potential Django ValidationError list wrapper if needed
                if error_message.startswith("['") and error_message.endswith("']"):
                    error_message = error_message[2:-2]
                elif error_message.startswith("[") and error_message.endswith("]"):
                    error_message = error_message[1:-1]

                raise forms.ValidationError(f"Invalid custom gender format: {error_message}")
                
        return gender
        
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            mpgepmcusers_validate_birth_date(dob)
        return dob

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            mpgepmcusers_validate_email_domain(email)
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
        Global form validation, primarily for password matching.
        """
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Passwords do not match.")

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
            user.custom_gender = self.cleaned_data.get('custom_gender')
            
        if commit:
            user.save()
        return user


class mpgepmcusersSignInForm(AuthenticationForm):
    """
    Standard Django Authentication form.
    """
    pass