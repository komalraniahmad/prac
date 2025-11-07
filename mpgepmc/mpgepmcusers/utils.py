import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives 
from django.template.loader import render_to_string 
from django.urls import reverse
from django.conf import settings
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.sites.shortcuts import get_current_site
from secrets import token_urlsafe # Use secrets for token generation

from mpgepmcusers.models import mpgepmcusersOTP, mpgepmcusersPasswordResetToken, mpgepmcusersUser # UPDATED IMPORT: Added mpgepmcusersUser

# --- NEW UTILITY FOR USERNAME GENERATION ---

def mpgepmcusers_generate_unique_username(first_name, middle_name, last_name):
    """
    Generates a unique username based on the user's full name, ensuring:
    1. It's min. 8 characters long (padded with random digits if necessary).
    2. It's unique (appends random digits until unique).
    3. It's max. 64 characters long (max field length).
    Format: FirstnameLastname or FirstnameMiddlenameLastname, stripped of spaces.
    """
    
    # Base structure: Concatenate names (e.g., Ali + Haider + Ahmad -> AliHaiderAhmad)
    name_parts = [first_name, middle_name, last_name]
    base_username = ''.join(
        [part.strip().replace(' ', '') for part in name_parts if part is not None and part.strip()]
    )
    
    # Remove any non-alphanumeric characters, keeping it clean
    base_username = ''.join(filter(str.isalnum, base_username))
    
    # Ensure all names are capitalized for consistency (e.g., AliAhmad)
    base_username = base_username.title() 
    
    # Ensure it's not too long before we start padding
    max_name_length = 60 # Reserve a few characters for digits
    base_username = base_username[:max_name_length] 
    
    # Try the base username first
    potential_username = base_username
    counter = 0
    
    # Loop until a unique username is found
    while mpgepmcusersUser.objects.filter(username=potential_username).exists():
        counter += 1
        
        # 1. Pad with a 3-digit random number for initial uniqueness attempt
        # This also helps meet the min 8-character requirement if the name is short.
        random_suffix = str(random.randint(100, 9999)) 
        
        # 2. Append the random suffix to the base name
        temp_username = base_username + random_suffix
        
        # 3. If the username is still less than 8 characters, pad with more digits until it reaches 8
        if len(temp_username) < 8:
            padding = ''.join(random.choices('0123456789', k=8 - len(temp_username)))
            temp_username += padding
            
        # 4. Final check for max length (64)
        potential_username = temp_username[:64]
        
        # As a safeguard against infinite loops (highly unlikely with random digits)
        if counter > 10:
            # Fallback to a purely random 10-character string
            potential_username = 'user' + token_urlsafe(6).replace('-', '').replace('_', '')
            break

    return potential_username

# --- END NEW UTILITY ---


def mpgepmcusers_generate_otp(user):
# ... (mpgepmcusers_generate_otp remains the same)
    """
    Generates a 6-digit OTP and stores it in the database with expiry.
    Returns the generated OTP.
    """
    otp_code = ''.join([random.choice('0123456789') for _ in range(6)])
    # The expires_at logic is now moved to the save() method on the model
    # to correctly handle the reset of fail_attempts/invalidated status.

    # FIX: Update_or_create to reset fail_attempts and invalidated status
    otp_record, created = mpgepmcusersOTP.objects.update_or_create(
        user=user,
        defaults={
            'otp_code': otp_code,
            # Set defaults to ensure a clean slate, model's save() handles expiry
            'fail_attempts': 0, 
            'invalidated': False,
        }
    )
    # Signal to the model's save method that the OTP is being regenerated
    otp_record._regenerate = True 
    otp_record.save()
    
    return otp_code

def mpgepmcusers_send_otp_email(user, otp_code):
# ... (mpgepmcusers_send_otp_email remains the same)
    """
    Sends the OTP email to the user using an HTML template.
    Uses EmailMultiAlternatives for a multi-part (text/html) message.
    """
    # 1. Prepare Context and Expiry Time
    # Assuming OTP_EXPIRY_TIME is a timedelta object in settings
    expiry_minutes = settings.OTP_EXPIRY_TIME.total_seconds() // 60
    context = {
        'user': user,
        'otp_code': otp_code,
        'expiry_minutes': int(expiry_minutes),
        'site_name': 'mpgepmc', # Hardcoded site name for template display
    }
    
    # 2. Render HTML and prepare Plain Text Fallback
    subject = 'mpgepmc Account Verification Code'
    html_message = render_to_string('mpgepmcusers/email/signup-otp-emal.html', context)
    
    text_content = (
        f'Hello {user.first_name},\n\n'
        f'Your One-Time Password (OTP) for verifying your mpgepmc account is: {otp_code}\n\n'
        f'This code will expire in {int(expiry_minutes)} minutes.\n\n'
        f'Thank you,\n'
        f'mpgepmc Team'
    )
    
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    try:
        # 3. Create and send a multi-part email
        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        # In a real application, you'd log this error
        return False

# --- NEW PASSWORD MANAGEMENT UTILS ---

def mpgepmcusers_generate_reset_token(user):
# ... (mpgepmcusers_generate_reset_token remains the same)
    """
    Generates a unique, URL-safe token and stores it in the database with expiry.
    Returns the generated token string.
    """
    # Generate a secure token
    token = token_urlsafe(32) 

    # Delete any existing token for this user to ensure only one active link
    try:
        mpgepmcusersPasswordResetToken.objects.get(user=user).delete()
    except mpgepmcusersPasswordResetToken.DoesNotExist:
        pass
    
    # Create the new token record
    reset_token_record = mpgepmcusersPasswordResetToken.objects.create(
        user=user,
        token=token,
        is_used=False # Ensure it's marked as fresh
    )
    # The expiry is automatically set in the model's save() method
    
    return reset_token_record.token


def mpgepmcusers_send_reset_email(request, user, token):
# ... (mpgepmcusers_send_reset_email remains the same)
    """
    Sends the password reset link email to the user.
    """
    
    # Need the domain name to build the absolute URL
    current_site = get_current_site(request)
    domain = current_site.domain

    # Encode the user's primary key (pk) in base64 for the URL
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    
    # Build the full reset link
    reset_link = reverse('mpgepmcusers:reset_password_confirm', kwargs={'uidb64': uid, 'token': token})
    absolute_url = f'http://{domain}{reset_link}' # Use https in production

    # Prepare context for the email
    expiry_minutes = mpgepmcusersPasswordResetToken.RESET_TOKEN_EXPIRY.total_seconds() // 60
    context = {
        'user': user,
        'reset_link': absolute_url,
        'expiry_minutes': int(expiry_minutes),
        'site_name': 'mpgepmc',
    }
    
    subject = 'mpgepmc Password Reset Request'
    html_message = render_to_string('mpgepmcusers/email/password-reset-email.html', context)
    
    text_content = (
        f'Hello {user.first_name},\n\n'
        f'You requested a password reset for your mpgepmc account. Please click the link below to set a new password:\n'
        f'{absolute_url}\n\n'
        f'This link will expire in {int(expiry_minutes)} minutes.\n\n'
        f'If you did not request this, please ignore this email.\n\n'
        f'Thank you,\n'
        f'mpgepmc Team'
    )
    
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    
    try:
        msg = EmailMultiAlternatives(subject, text_content, from_email, recipient_list)
        msg.attach_alternative(html_message, "text/html")
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        print(f"Error sending reset email: {e}")
        return False