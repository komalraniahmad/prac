from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
# Import the new model
from mpgepmcusers.models import mpgepmcusersUser, mpgepmcusersOTP, MobileValidationRule, mpgepmcusersPasswordResetToken

# Custom Admin for mpgepmcusersUser
class mpgepmcusersUserAdmin(UserAdmin):
    """
    Custom admin interface for the mpgepmcusersUser model.
    """
    # UPDATED list_display to show all relevant signup fields
    list_display = (
        'email', 
        'first_name', 
        'middle_name', 
        'last_name', 
        'gender', 
        'custom_gender', 
        'date_of_birth', 
        'mobile_number', 
        'is_active', 
        'is_staff', 
        'is_superuser',
        'last_password_change' # NEW: Show last password change time
    )
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    filter_horizontal = ()

    # Custom fieldsets for the admin change form
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'middle_name', 'last_name', 'gender', 'custom_gender', 'date_of_birth', 'mobile_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined', 'last_password_change')}), # NEW: last_password_change
    )
    # Fields that cannot be edited via the admin form
    readonly_fields = ('last_login', 'date_joined')

# Admin for OTP
@admin.register(mpgepmcusersOTP)
class mpgepmcusersOTPAdmin(admin.ModelAdmin):
    """
    Admin interface for the OTP record model.
    """
    list_display = ('user', 'otp_code', 'created_at', 'expires_at', 'is_expired')
    search_fields = ('user__email',)
    list_filter = ('expires_at',)

# NEW ADMIN: Password Reset Token
@admin.register(mpgepmcusersPasswordResetToken)
class mpgepmcusersPasswordResetTokenAdmin(admin.ModelAdmin):
    """
    Admin interface for the Password Reset Token model.
    """
    list_display = ('user', 'token', 'created_at', 'expires_at', 'is_used', 'is_valid')
    search_fields = ('user__email',)
    list_filter = ('expires_at', 'is_used')

# --- NEW ADMIN FOR DYNAMIC MOBILE VALIDATION RULES ---
@admin.register(MobileValidationRule)
class MobileValidationRuleAdmin(admin.ModelAdmin):
    """
    Admin interface for the MobileValidationRule model.
    """
    list_display = ('country_code', 'user_number_length', 'example_format')
    search_fields = ('country_code',)
    list_filter = ('country_code',)
    # Order the fields on the add/change form for clarity
    fieldsets = (
        (None, {'fields': ('country_code', 'operator_codes', 'user_number_length', 'example_format')}),
    )


# Register the custom User model with the custom admin
admin.site.register(mpgepmcusersUser, mpgepmcusersUserAdmin)