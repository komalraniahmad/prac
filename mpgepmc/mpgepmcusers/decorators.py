from django.shortcuts import redirect
from django.contrib import messages
from django.conf import settings

def mpgepmcusers_unauthenticated_user(view_func):
    """
    Decorator that redirects authenticated users away from certain pages (like signup/signin).
    """
    def wrapper_func(request, *args, **kwargs):
        if request.user.is_authenticated:
            # Redirect to the home page if already authenticated
            return redirect(settings.LOGIN_REDIRECT_URL)
        return view_func(request, *args, **kwargs)
    return wrapper_func
