from django.contrib import admin

from .models import Agreement, Customer, CustomerViewer, Plan


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'includes_shared_pool', 'detail_level', 'allows_export')
    search_fields = ('name',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'primary_contact_name', 'primary_contact_email')
    search_fields = ('name', 'primary_contact_email')


@admin.register(Agreement)
class AgreementAdmin(admin.ModelAdmin):
    list_display = ('customer', 'plan', 'start_date', 'end_date', 'buffer_days')
    list_filter = ('plan',)
    autocomplete_fields = ('customer', 'plan')
    filter_horizontal = ('events',)


admin.site.register(CustomerViewer)
