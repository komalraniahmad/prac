from django.urls import path
from . import views

# Set the required namespace
app_name = 'mpgepmcusers'

urlpatterns = [
    # General Pages
    path('', views.mpgepmcusers_index, name='index'),
    path('home/', views.mpgepmcusers_home, name='home'),

    # Authentication
    path('signup/', views.mpgepmcusers_signup, name='signup'),
    path('signin/', views.mpgepmcusers_signin, name='signin'),
    path('logout/', views.mpgepmcusers_logout, name='logout'),

    # Verification
    path('verify-otp/', views.mpgepmcusers_otp_verify, name='otp_verify'),
    path('resend-otp/', views.mpgepmcusers_resend_otp, name='resend_otp'),

    # NEW: Password Management (Unauthenticated)
    path('forgot-password/', views.mpgepmcusers_forgot_password, name='forgot_password'),
    path('reset-password/<uidb64>/<token>/', views.mpgepmcusers_reset_password_confirm, name='reset_password_confirm'),
    
    # NEW: Password Management (Authenticated)
    path('change-password/', views.mpgepmcusers_change_password, name='change_password'),
    
    # AJAX Live Validation
    path('ajax-validate/', views.mpgepmcusers_ajax_validate, name='ajax_validate'),
]