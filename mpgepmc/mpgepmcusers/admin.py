from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from mpgepmcusers.models import mpgepmcusersUser, mpgepmcusersOTP

# Custom Admin for mpgepmcusersUser
class mpgepmcusersUserAdmin(UserAdmin):
    """
    Custom admin interface for the mpgepmcusersUser model.
    """
    # The fields to be used in displaying the User model.
    list_display = ('email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('email', 'first_name', 'last_name')
    ordering = ('email',)
    filter_horizontal = ()

    # Custom fieldsets for the admin change form
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal info', {'fields': ('first_name', 'middle_name', 'last_name', 'gender', 'date_of_birth', 'mobile_number')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
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

# Register the custom User model with the custom admin
admin.site.register(mpgepmcusersUser, mpgepmcusersUserAdmin)
