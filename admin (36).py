from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ('Built To Work', {
            'fields': (
                'role', 'customer',
                'mailing_street', 'mailing_city', 'mailing_state', 'mailing_zip',
                'shirt_size',
            ),
        }),
    )
    list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
    list_filter = ('role', 'is_staff', 'is_active')
