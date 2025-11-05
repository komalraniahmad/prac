import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db import IntegrityError
from django.utils import timezone # ADDED: Required for resend OTP logic

from mpgepmcusers.forms import mpgepmcusersSignupForm, mpgepmcusersSignInForm
from mpgepmcusers.models import mpgepmcusersUser, mpgepmcusersOTP
from mpgepmcusers.utils import mpgepmcusers_generate_otp, mpgepmcusers_send_otp_email
from mpgepmcusers.validators import (
    mpgepmcusers_validate_birth_date, mpgepmcusers_validate_email_domain,
    mpgepmcusers_validate_mobile_number, mpgepmcusers_validate_password_complexity,
    mpgepmcusers_validate_name_format_and_length # Existing new import
)
from mpgepmcusers.decorators import mpgepmcusers_unauthenticated_user

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
        
        # Prevent spamming: Check if an OTP was recently generated (e.g., in the last 60 seconds)
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
    Handles live, asynchronous validation checks for uniqueness and other rules.
    """
    data = json.loads(request.body)
    field_name = data.get('field')
    value = data.get('value', '').strip() 
    
    # Allows empty value for middle_name, but checks for missing value on required fields if they are passed in
    if not value and field_name not in ['middle_name']:
        return HttpResponseBadRequest(json.dumps({'is_valid': False, 'error': 'Missing required field value.'}))
    
    is_valid = True
    error_message = ''

    try:
        if field_name in ['first_name', 'last_name']:
            # Use the new comprehensive validator
            mpgepmcusers_validate_name_format_and_length(value, field_name.replace('_', ' ').title())

        elif field_name == 'middle_name':
            if value: # Only validate if a value is present (it's optional)
                # Use the new comprehensive validator
                mpgepmcusers_validate_name_format_and_length(value, field_name.replace('_', ' ').title())
            else:
                # Value is empty, which is valid for middle_name
                is_valid = True 
        
        elif field_name == 'gender':
            if value not in ['M', 'F', 'O']:
                is_valid = False
                error_message = 'Invalid gender selected.'

        elif field_name == 'date_of_birth':
            # Note: client-side date format is YYYY-MM-DD
            from datetime import datetime
            dob = datetime.strptime(value, '%Y-%m-%d').date()
            mpgepmcusers_validate_birth_date(dob)
            
        elif field_name == 'email':
            mpgepmcusers_validate_email_domain(value)
            # Check uniqueness
            if mpgepmcusersUser.objects.filter(email=value).exists():
                is_valid = False
                error_message = 'This email is already registered.'
            
        elif field_name == 'mobile_number':
            mpgepmcusers_validate_mobile_number(value)
            # Check uniqueness
            if mpgepmcusersUser.objects.filter(mobile_number=value).exists():
                is_valid = False
                error_message = 'This mobile number is already registered.'

        elif field_name == 'password':
            mpgepmcusers_validate_password_complexity(value)
            
    except Exception as e:
        is_valid = False
        if hasattr(e, 'message'):
            error_message = e.message
        elif hasattr(e, 'messages') and e.messages:
            error_message = str(e.messages[0])
        else:
            error_message = str(e)
            
        # Clean up Django's ValidationError wrapper messages 
        if error_message.startswith("['") and error_message.endswith("']"):
            error_message = error_message[2:-2]
        elif error_message.startswith("[") and error_message.endswith("]"):
             error_message = error_message[1:-1]
            
    return JsonResponse({'is_valid': is_valid, 'error': error_message})