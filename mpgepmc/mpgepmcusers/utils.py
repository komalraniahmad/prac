import random
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings
from mpgepmcusers.models import mpgepmcusersOTP

def mpgepmcusers_generate_otp(user):
    """
    Generates a 6-digit OTP and stores it in the database with a 30-minute expiry.
    Returns the generated OTP.
    """
    otp_code = ''.join([random.choice('0123456789') for _ in range(6)])
    expires_at = timezone.now() + settings.OTP_EXPIRY_TIME # 30 minutes

    # Create or update the OTP record for the user
    otp_record, created = mpgepmcusersOTP.objects.update_or_create(
        user=user,
        defaults={
            'otp_code': otp_code,
            'expires_at': expires_at
        }
    )
    return otp_code

def mpgepmcusers_send_otp_email(user, otp_code):
    """
    Simulates sending the OTP email to the user.
    In a real app, this would use a proper mail service.
    """
    subject = 'mpgepmc Account Verification Code'
    message = (
        f'Hello {user.first_name},\n\n'
        f'Your One-Time Password (OTP) for verifying your mpgepmc account is: {otp_code}\n\n'
        f'This code will expire in 30 minutes.\n\n'
        f'Thank you,\n'
        f'mpgepmc Team'
    )
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    try:
        # NOTE: This will print to console because EMAIL_BACKEND is set to console.EmailBackend
        send_mail(subject, message, from_email, recipient_list, fail_silently=False)
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        # In a real application, you'd log this error
        return False
