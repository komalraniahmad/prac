import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_POST
from django.db import IntegrityError

from mpgepmcusers.forms import mpgepmcusersSignupForm, mpgepmcusersSignInForm
from mpgepmcusers.models import mpgepmcusersUser, mpgepmcusersOTP
from mpgepmcusers.utils import mpgepmcusers_generate_otp, mpgepmcusers_send_otp_email
from mpgepmcusers.validators import (
    mpgepmcusers_validate_birth_date, mpgepmcusers_validate_email_domain,
    mpgepmcusers_validate_mobile_number, mpgepmcusers_validate_password_complexity
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
    """User Sign-in View."""
    if request.method == 'POST':
        form = mpgepmcusersSignInForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if user.is_active:
                login(request, user)
                messages.success(request, f"Welcome back, {user.first_name}!")
                return redirect('mpgepmcusers:home')
            else:
                # Redirect to verification if not active
                messages.warning(request, "Your account is not yet verified. Please verify your email.")
                request.session['unverified_email'] = user.email
                return redirect('mpgepmcusers:otp_verify')
        else:
            messages.error(request, "Invalid credentials.")
    else:
        form = mpgepmcusersSignInForm()

    context = {'form': form, 'title': 'Sign In'}
    return render(request, 'mpgepmcusers/mpgepmcusers_signin.html', context)

def mpgepmcusers_logout(request):
    """User Logout View."""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('mpgepmcusers:index')

# --- Registration Views ---

@mpgepmcusers_unauthenticated_user
def mpgepmcusers_signup(request):
    """User Registration/Signup View."""
    if request.method == 'POST':
        form = mpgepmcusersSignupForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                otp_code = mpgepmcusers_generate_otp(user)
                
                # Send (Simulated) OTP email
                if mpgepmcusers_send_otp_email(user, otp_code):
                    messages.success(request, "Registration successful! Check your email for the verification code.")
                    # Store the email in session for the OTP verification step
                    request.session['unverified_email'] = user.email
                    return redirect('mpgepmcusers:otp_verify')
                else:
                    user.delete() # Rollback user creation if email fails
                    messages.error(request, "Could not send verification email. Please try again later.")
                    return redirect('mpgepmcusers:signup')
            except IntegrityError:
                # Catch race condition or final unique constraint error
                messages.error(request, "A user with this email or mobile number already exists.")
            except Exception as e:
                print(f"Signup error: {e}")
                messages.error(request, "An unexpected error occurred during registration.")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = mpgepmcusersSignupForm()

    context = {'form': form, 'title': 'User Registration'}
    return render(request, 'mpgepmcusers/mpgepmcusers_signup.html', context)

def mpgepmcusers_otp_verify(request):
    """OTP Verification View."""
    email = request.session.get('unverified_email')
    
    if not email:
        messages.error(request, "Verification session expired or missing. Please sign up or sign in again.")
        return redirect('mpgepmcusers:signup')

    user = get_object_or_404(mpgepmcusersUser, email=email)
    
    if user.is_active:
        # User is already verified
        del request.session['unverified_email']
        return redirect('mpgepmcusers:signin')

    if request.method == 'POST':
        otp_code = request.POST.get('otp_code')
        try:
            otp_record = mpgepmcusersOTP.objects.get(user=user)
            
            if otp_record.otp_code == otp_code and not otp_record.is_expired():
                # Verification success
                user.is_active = True
                user.save()
                otp_record.delete()
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
            if (last_otp.created_at + last_otp.user.get_otp_resend_throttle()) > timezone.now():
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
    value = data.get('value')
    
    if not field_name or not value:
        return HttpResponseBadRequest(json.dumps({'is_valid': False, 'error': 'Missing field or value'}))
    
    is_valid = True
    error_message = ''

    try:
        if field_name == 'first_name' or field_name == 'middle_name' or field_name == 'last_name':
            if not (1 <= len(value) <= 64):
                is_valid = False
                error_message = f"{field_name.replace('_', ' ').title()} must be 1-64 characters."

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
        
        # password_confirm is handled purely client-side unless a full form submit is done

    except Exception as e:
        is_valid = False
        error_message = str(e.message) if hasattr(e, 'message') else str(e)
        # Clean up ValidationError wrapper messages
        if error_message.startswith('[') and error_message.endswith(']'):
            error_message = error_message[2:-2] # Remove [ and ] and single quotes

    return JsonResponse({'is_valid': is_valid, 'error': error_message})
