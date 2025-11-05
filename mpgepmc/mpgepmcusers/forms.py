from django import forms
from django.contrib.auth.forms import AuthenticationForm
from mpgepmcusers.models import mpgepmcusersUser
from mpgepmcusers.validators import (
    mpgepmcusers_validate_birth_date,
    mpgepmcusers_validate_email_domain,
    mpgepmcusers_validate_mobile_number,
    mpgepmcusers_validate_password_complexity,
    mpgepmcusers_validate_name_format_and_length
)

class mpgepmcusersSignupForm(forms.ModelForm):
    """
    Form for user registration, including password and confirmation.
    """
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

    class Meta:
        model = mpgepmcusersUser
        fields = (
            'first_name', 'middle_name', 'last_name', 'gender',
            'date_of_birth', 'email', 'mobile_number',
        )
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }
        labels = {
            'first_name': 'First Name',
            'middle_name': 'Middle Name (Optional)', # Updated label
            'last_name': 'Last Name',
            'mobile_number': 'Mobile Number',
        }

    # Custom Field Validation (using ModelForm's clean_<field> methods)
    def clean_first_name(self):
        name = self.cleaned_data.get('first_name')
        # Use the new comprehensive validator
        mpgepmcusers_validate_name_format_and_length(name, 'First Name')
        return name

    # Middle Name is optional, only validate length/format if provided
    def clean_middle_name(self):
        name = self.cleaned_data.get('middle_name')
        if name: # Only validate if a value is present
            # Use the new comprehensive validator
            mpgepmcusers_validate_name_format_and_length(name, 'Middle Name')
        # If blank, it passes silently, fulfilling the optional requirement.
        return name

    def clean_last_name(self):
        name = self.cleaned_data.get('last_name')
        # Use the new comprehensive validator
        mpgepmcusers_validate_name_format_and_length(name, 'Last Name')
        return name

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
        if commit:
            user.save()
        return user

class mpgepmcusersSignInForm(AuthenticationForm):
    """
    Standard Django Authentication form with custom prefix.
    """
    # Simply inheriting for consistency and potential future customization
    pass