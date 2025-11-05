import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from django.utils import timezone 
from django.core.exceptions import ValidationError 

from mpgepmcusers.forms import mpgepmcusersSignupForm, mpgepmcusersSignInForm
from mpgepmcusers.models import mpgepmcusersUser, mpgepmcusersOTP, OTHER
from mpgepmcusers.utils import mpgepmcusers_generate_otp, mpgepmcusers_send_otp_email
from mpgepmcusers.validators import (
    mpgepmcusers_validate_birth_date, mpgepmcusers_validate_email,
    mpgepmcusers_validate_mobile_number, mpgepmcusers_validate_password_complexity,
    mpgepmcusers_validate_name_format_and_length 
)
from mpgepmcusers.decorators import mpgepmcusers_unauthenticated_user
from datetime import datetime
# --- Shared Views ---

def mpgepmcusers_index(request):
    """Landing page view."""
    return render(request, 'mpgepmcusers/mpgepmcusers_index.html')

@login_required
def mpgepmcusers_home(request):
    """Home/Dashboard view for authenticated users."""
    return render(request, 'mpgepmcusers/mpgepmcusers_home.html')

# --- Authentication Views ---

@mpgepmcusers_unauthenticated_user
def mpgepmcusers_signin(request):
    if request.method == 'POST':
        form = mpgepmcusersSignInForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            # Check if user is active (i.e., verified)
            if user.is_active:
                login(request, user)
                return redirect('mpgepmcusers:home')
            else:
                # If account is not active, redirect to OTP verification
                messages.warning(request, 'Your account is not verified. Please verify using the OTP sent to your email.')
                request.session['unverified_email'] = user.email # Ensure email is set for verification
                return redirect('mpgepmcusers:otp_verify')
        else:
            messages.error(request, 'Invalid email or password.')
    else:
        form = mpgepmcusersSignInForm()
        
    return render(request, 'mpgepmcusers/mpgepmcusers_signin.html', {'form': form, 'title': 'Sign In'})

@login_required
def mpgepmcusers_logout(request):
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('mpgepmcusers:signin')

# --- Registration Views ---

@mpgepmcusers_unauthenticated_user
def mpgepmcusers_signup(request):
    if request.method == 'POST':
        form = mpgepmcusersSignupForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                # 1. Generate OTP
                otp_code = mpgepmcusers_generate_otp(user)
                
                # 2. Send OTP (Simulated)
                mpgepmcusers_send_otp_email(user, otp_code)
                
                # 3. Store email in session to verify
                request.session['unverified_email'] = user.email
                messages.success(request, 'Registration successful. An OTP has been sent to your email for verification.')
                return redirect('mpgepmcusers:otp_verify')
            except IntegrityError:
                # Handle database errors (though uniqueness should be caught in form.is_valid)
                messages.error(request, 'A user with this email or mobile number already exists.')
            except Exception as e:
                messages.error(request, f'An unexpected error occurred: {e}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = mpgepmcusersSignupForm()
        
    return render(request, 'mpgepmcusers/mpgepmcusers_signup.html', {'form': form, 'title': 'Sign Up'})

# --- Verification Views (Fix for the error) ---

def mpgepmcusers_otp_verify(request):
    """OTP Verification View."""
    email = request.session.get('unverified_email')
    
    if not email:
        messages.error(request, "Verification session expired or missing. Please sign up or sign in again.")
        return redirect('mpgepmcusers:signup')

    user = get_object_or_404(mpgepmcusersUser, email=email)
    
    if user.is_active:
        # User is already verified
        if 'unverified_email' in request.session:
            del request.session['unverified_email']
        return redirect('mpgepmcusers:signin')

    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        try:
            otp_record = mpgepmcusersOTP.objects.get(user=user)
            
            if otp_code is None or not otp_code.strip():
                 messages.error(request, "Please enter the OTP code.")
            elif otp_record.otp_code == otp_code.strip() and not otp_record.is_expired():
                # Verification success
                user.is_active = True
                user.save()
                otp_record.delete()
                if 'unverified_email' in request.session:
                    del request.session['unverified_email']
                messages.success(request, "Account successfully verified! Please sign in.")
                return redirect('mpgepmcusers:signin')
            elif otp_record.is_expired():
                messages.error(request, "OTP has expired. Please request a new one.")
            else:
                messages.error(request, "Invalid OTP code.")
        except mpgepmcusersOTP.DoesNotExist:
            messages.error(request, "No active OTP found. Please request a resend.")
        except Exception:
            messages.error(request, "Verification failed. Please try again.")

    context = {'email': email, 'title': 'Verify Account'}
    return render(request, 'mpgepmcusers/mpgepmcusers_otp_verify.html', context)

@require_POST
def mpgepmcusers_resend_otp(request):
    """Resends a new OTP to the unverified user."""
    email = request.session.get('unverified_email')
    if not email:
        return JsonResponse({'success': False, 'message': 'Verification session missing.'}, status=400)

    try:
        user = mpgepmcusersUser.objects.get(email=email)
        
        # Prevent spamming: Check if an OTP was recently generated (e.g., in the in the last 60 seconds)
        try:
            last_otp = mpgepmcusersOTP.objects.get(user=user)
            # Assuming get_otp_resend_throttle() is a method on the User model
            if (last_otp.created_at + user.get_otp_resend_throttle()) > timezone.now():
                 return JsonResponse({'success': False, 'message': 'Wait a moment before resending.'}, status=429)
        except mpgepmcusersOTP.DoesNotExist:
            pass # No existing OTP, so proceed.
        
        new_otp = mpgepmcusers_generate_otp(user)
        
        if mpgepmcusers_send_otp_email(user, new_otp):
            return JsonResponse({'success': True, 'message': 'New OTP sent to your email!'}, status=200)
        else:
            return JsonResponse({'success': False, 'message': 'Failed to send new OTP.'}, status=500)

    except mpgepmcusersUser.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)

# --- AJAX Validation View ---

@require_POST
def mpgepmcusers_ajax_validate(request):
    """
    Handles live, asynchronous validation checks for uniqueness, format, and other rules.
    Expects a JSON payload in request.body.
    """
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest(json.dumps({'is_valid': False, 'error': 'Invalid JSON payload.'}))
        
    field_name = data.get('field')
    # Use .get('value', '') to handle missing 'value' key, then strip
    value = data.get('value', '').strip() 
    
    # NEW: Include custom_gender and gender for context-specific validation
    custom_gender_value = data.get('custom_gender', '').strip()
    gender_field_value = data.get('gender')

    is_valid = True
    error_message = ''

    # --- Initial Required Field Check ---
    # middle_name is optional, all others passed in must have a value
    if not value and field_name not in ['middle_name']:
        # Exception: For 'custom_gender', we only check required status if gender is 'OTHER'
        if field_name == 'custom_gender' and gender_field_value == OTHER:
            # Fall through to specific validation
            pass 
        else:
            return HttpResponseBadRequest(json.dumps({'is_valid': False, 'error': 'Missing required field value.'}))
    
    # If middle_name is empty, it's valid, so we can exit early.
    if field_name == 'middle_name' and not value:
        return JsonResponse({'is_valid': True, 'error': ''})

    try:
        # --- Name Fields Validation ---
        if field_name in ['first_name', 'last_name']:
            mpgepmcusers_validate_name_format_and_length(value, field_name.replace('_', ' ').title())

        elif field_name == 'middle_name':
            # Value is present (checked above), so validate it
            mpgepmcusers_validate_name_format_and_length(value, field_name.replace('_', ' ').title())
        
        # --- Gender Field Validation (Dropdown/Radio) ---
        elif field_name == 'gender':
            valid_genders = [choice[0] for choice in mpgepmcusersUser.GENDER_CHOICES]
            if value not in valid_genders:
                is_valid = False
                error_message = 'Invalid gender selected.'
            elif value == OTHER: # 'O' for Other
                # If 'Other' is selected, custom_gender value MUST be provided
                if not custom_gender_value:
                    is_valid = False
                    error_message = 'You must specify your gender in the text box.'
                # The final form validation in forms.py handles the core submission error.
        
        # --- Custom Gender Field Validation (ChoiceField) ---
        elif field_name == 'custom_gender':
            # Only validate if the user's selected gender is 'Other'
            if gender_field_value == OTHER:
                if not value:
                    is_valid = False
                    error_message = 'You must select an option from the dropdown when Other is selected.'
                else:
                    # The value comes from a controlled dropdown (ChoiceField) which is inherently valid.
                    pass 
            # If gender is not 'Other', or if it's not provided, custom_gender is valid.
            elif gender_field_value and gender_field_value != OTHER:
                is_valid = True
                error_message = ''
            else:
                 is_valid = True
                 error_message = ''
        
        # --- Date of Birth Validation ---
        elif field_name == 'date_of_birth':
            # This line could raise ValueError if the format is wrong
            dob = datetime.strptime(value, '%Y-%m-%d').date()
            # This line could raise ValidationError if age is out of bounds
            mpgepmcusers_validate_birth_date(dob)
            
        # --- Email Validation (Format + Uniqueness) ---
        elif field_name == 'email':
            mpgepmcusers_validate_email(value) # <-- FIXED FUNCTION CALL
            # Check uniqueness
            if mpgepmcusersUser.objects.filter(email=value).exists():
                is_valid = False
                error_message = 'This email is already registered.'
                
        # --- Mobile Number Validation (Format + Uniqueness) ---
        elif field_name == 'mobile_number':
            mpgepmcusers_validate_mobile_number(value)
            # Check uniqueness
            if mpgepmcusersUser.objects.filter(mobile_number=value).exists():
                is_valid = False
                error_message = 'This mobile number is already registered.'

        # --- Password Validation ---
        elif field_name == 'password':
            mpgepmcusers_validate_password_complexity(value)
            
    except Exception as e:
        is_valid = False
        error_message = '' 
        
        # --- Consolidated Exception Handling ---
        
        # 1. Handle Django's ValidationError explicitly
        if isinstance(e, ValidationError):
            try:
                error_messages = [str(msg) for msg in e] 
                error_message = ' '.join(error_messages)
            except Exception as inner_e:
                error_message = f"Validation failed: {type(inner_e).__name__} during message resolution."
                
        # 2. Fallback for other exceptions 
        elif hasattr(e, 'message'):
            error_message = e.message
        elif hasattr(e, 'messages') and e.messages:
            error_message = str(e.messages[0])
        else:
            # Catch all other exceptions (e.g., ValueError from datetime.strptime)
            error_message = str(e)
            
        # 3. Clean up wrappers
        error_message = error_message.strip("[]'\"")
        
        # 4. Handle specific technical errors for user-friendly output
        if "time data" in error_message and "does not match format" in error_message:
            error_message = "Invalid date format. Please use YYYY-MM-DD."
        elif not error_message or error_message == "<exception str() failed>" or error_message == "Validation error.":
             # Use a robust default message
             error_message = "Validation error occurred. Please check your input."
             
    # Default response for valid or invalid fields
    return JsonResponse({'is_valid': is_valid, 'error': error_message})