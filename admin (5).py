from django.contrib import admin

from .models import (
    AdminNote,
    AvailabilityRequest,
    DailyAttendance,
    DailyWorkReport,
    EventStaffAssignment,
    GlobalPayrollSettings,
    MileageBand,
    PayRole,
    Paystub,
    PayrollPeriod,
    Staff,
    StaffAdjustment,
)


@admin.register(PayRole)
class PayRoleAdmin(admin.ModelAdmin):
    list_display = ('label', 'role_key', 'daily_rate', 'per_diem_eligible', 'is_built_in')


@admin.register(MileageBand)
class MileageBandAdmin(admin.ModelAdmin):
    list_display = ('min_miles', 'max_miles', 'reimbursement_amount')


admin.site.register(GlobalPayrollSettings)


class AdminNoteInline(admin.TabularInline):
    model = AdminNote
    extra = 0
    readonly_fields = ('author', 'created_at')


class StaffAdjustmentInline(admin.TabularInline):
    model = StaffAdjustment
    extra = 0


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'is_active')
    search_fields = ('name', 'email', 'phone')
    inlines = [AdminNoteInline, StaffAdjustmentInline]
    # Admin notes are for admin eyes only - this ModelAdmin is itself
    # only reachable by staff with Django admin access, but a real
    # staff-facing view/API must never serialize AdminNote (spec
    # Section 10).


@admin.register(AvailabilityRequest)
class AvailabilityRequestAdmin(admin.ModelAdmin):
    list_display = ('staff', 'event', 'date', 'requested_pay_role', 'status')
    list_filter = ('status', 'event')
    actions = ['approve_requests']

    @admin.action(description='Approve selected requests')
    def approve_requests(self, request, queryset):
        for req in queryset.filter(status=AvailabilityRequest.Status.PENDING):
            req.approve(decided_by=request.user)


@admin.register(EventStaffAssignment)
class EventStaffAssignmentAdmin(admin.ModelAdmin):
    list_display = ('staff', 'event', 'date', 'pay_role')
    list_filter = ('event',)


@admin.register(DailyAttendance)
class DailyAttendanceAdmin(admin.ModelAdmin):
    list_display = ('staff', 'event', 'date', 'pay_role', 'checked_in_at')
    list_filter = ('event',)
    actions = ['create_work_reports']

    @admin.action(description='Create work report (freeze pay) for selected check-ins')
    def create_work_reports(self, request, queryset):
        for attendance in queryset:
            attendance.create_work_report(created_by=request.user)


@admin.register(DailyWorkReport)
class DailyWorkReportAdmin(admin.ModelAdmin):
    list_display = ('staff', 'event', 'work_date', 'pay_role', 'day_total', 'status', 'source')
    list_filter = ('status', 'source', 'event')
    readonly_fields = ('day_rate', 'per_diem', 'travel_reimbursement', 'created_at')


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ('start_date', 'end_date', 'status', 'compiled_at', 'approved_at')
    actions = ['approve_periods']

    @admin.action(description='Approve payroll (locks period, generates paystubs)')
    def approve_periods(self, request, queryset):
        for period in queryset.filter(status=PayrollPeriod.Status.COMPILED):
            period.approve(approved_by=request.user)


admin.site.register(Paystub)
