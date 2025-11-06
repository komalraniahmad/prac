import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail, EmailMultiAlternatives # UPDATED IMPORT
from django.template.loader import render_to_string # NEW IMPORT
from django.urls import reverse
from django.conf import settings
from mpgepmcusers.models import mpgepmcusersOTP

def mpgepmcusers_generate_otp(user):
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