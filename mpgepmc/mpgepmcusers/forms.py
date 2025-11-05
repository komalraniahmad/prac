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

    # UPDATED: Clean method for gender and custom_gender
    def clean_gender(self):
        gender = self.cleaned_data.get('gender')
        custom_gender = self.cleaned_data.get('custom_gender') # This is the selected option value
        
        # FIX: BaseUserManager.create_user handles the case where required fields are missing 
        # but the ChoiceField is required=True and will throw an error if no selection is made.
        if not gender:
            # This case should be caught by the standard required=True check on the ChoiceField,
            # but is kept here for robustness, although it's redundant now.
            raise forms.ValidationError("You must select a gender.")

        if gender == OTHER: # 'O' for Other
            # 1. Check required value (non-empty choice)
            if not custom_gender or custom_gender.strip() == '':
                # FIX: Add an error to the 'gender' field itself to show it's conditionally invalid
                self.add_error('gender', "Specification required when 'Other' is selected.")
                self.add_error('custom_gender', "You must select an option from the dropdown when 'Other' is selected.")
            elif custom_gender == 'Other-Typed':
                # If the user selects the "Other (Specify using Custom Text box)" option,
                # you would need an actual text field on the form (not currently implemented)
                # to allow typing, and validation on that text field.
                # For now, we will allow this to pass as valid if selected.
                pass
            else:
                # 2. If a non-empty, non-Custom-Text value is selected, it's inherently valid
                # because it came from the controlled dropdown choices.
                pass
                
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