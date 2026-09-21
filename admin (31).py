from django.contrib import admin

from .models import DailyStaffingNeed, EventReport, Event, Expense


class DailyStaffingNeedInline(admin.TabularInline):
    model = DailyStaffingNeed
    extra = 0


class ExpenseInline(admin.TabularInline):
    model = Expense
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('name', 'event_type', 'status', 'start_date', 'end_date', 'city', 'state')
    list_filter = ('status', 'event_type')
    search_fields = ('name', 'venue_name', 'city')
    inlines = [DailyStaffingNeedInline, ExpenseInline]
    actions = ['publish_events']

    @admin.action(description='Publish selected events to staff')
    def publish_events(self, request, queryset):
        errors = 0
        for event in queryset:
            try:
                event.publish()
            except ValueError:
                errors += 1
        if errors:
            self.message_user(request, f'{errors} event(s) skipped: location pin required.')


@admin.register(EventReport)
class EventReportAdmin(admin.ModelAdmin):
    list_display = (
        'event', 'is_finalized', 'total_leads', 'qualified_leads',
        'cost_per_lead_display', 'cost_per_qualified_lead_display',
    )
    readonly_fields = ('finalized_at',)

    @admin.display(description='Cost per lead')
    def cost_per_lead_display(self, obj):
        v = obj.cost_per_lead
        return f'${v:,.2f}' if v is not None else '—'

    @admin.display(description='Cost per qualified lead')
    def cost_per_qualified_lead_display(self, obj):
        v = obj.cost_per_qualified_lead
        return f'${v:,.2f}' if v is not None else '—'
