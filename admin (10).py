from django.contrib import admin

from .models import Interaction, Interest, Opportunity


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('title', 'customer', 'status', 'pay_description', 'location')
    list_filter = ('status', 'customer')


@admin.register(Interest)
class InterestAdmin(admin.ModelAdmin):
    list_display = ('participant', 'opportunity', 'status', 'created_at')
    list_filter = ('status',)


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ('participant', 'kind', 'occurred_at', 'is_released_to_customers')
    list_filter = ('kind', 'is_released_to_customers')
