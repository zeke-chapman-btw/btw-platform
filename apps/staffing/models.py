"""
Staff, availability, check-in, and payroll.

This is the most fully-specified module in the platform spec, because
it was reconstructed not just from screenshots but from base44's own
source code and internal architecture doc (spec Sections 10-11). Three
things from that research matter more than any individual field name:

1. An EventStaffAssignment (confirmed schedule intent) is NOT a
   DailyWorkReport (the actual monetary record). Payroll reads ONLY
   from DailyWorkReport, and only for people who checked in or have an
   admin-created report - a confirmed assignment alone doesn't qualify.

2. DailyWorkReport values are FROZEN at creation time - the day rate,
   per diem, and mileage reimbursement actually paid are copied onto
   the record when it's created, not looked up live from PayRole /
   MileageBand every time a report is viewed. This deliberately avoids
   a real bug found in base44's current code: it recalculates base pay
   live from whatever the CURRENT rate table says, so editing a rate
   silently rewrites every past event's payroll. Never do that here -
   changing PayRole or MileageBand only affects work reports created
   after the change.

3. Corrections are VOIDED AND REPLACED, never edited or deleted, for
   both work reports and expenses. This is the audit trail the whole
   payroll approval / paystub pipeline depends on.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class PayRole(models.Model):
    """
    Roles & Rates (spec Section 10). role_key/label/daily_rate/
    per_diem_eligible field names match base44's actual Role entity.
    Built-in roles shouldn't be deletable from the admin UI once the
    real app exists (base44 enforces this); nothing stops it at the
    model layer here, since that's a UI-layer rule, not a data-layer one.
    """

    role_key = models.SlugField(max_length=40, unique=True)
    label = models.CharField(max_length=80)
    daily_rate = models.DecimalField(max_digits=8, decimal_places=2)
    per_diem_eligible = models.BooleanField(default=True)
    is_built_in = models.BooleanField(default=False)

    def __str__(self):
        return self.label


class GlobalPayrollSettings(models.Model):
    """
    Singleton-ish: the global per diem amount, paid per day worked to
    every per-diem-eligible role by default (spec Section 10).
    """

    global_per_diem = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        verbose_name = 'Global payroll settings'
        verbose_name_plural = 'Global payroll settings'

    def __str__(self):
        return f'Per diem: ${self.global_per_diem}'


class MileageBand(models.Model):
    """
    Admin-editable mileage reimbursement TABLE - tiered bands with a
    flat amount, not a flat $/mile rate (corrected from an earlier
    assumption once base44's real build doc turned up - spec Section
    10). max_miles null means "and up" (matches base44's "226+").
    Validate non-overlapping bands at the form/admin layer.
    """

    min_miles = models.PositiveIntegerField()
    max_miles = models.PositiveIntegerField(null=True, blank=True, help_text='Blank = no upper bound.')
    reimbursement_amount = models.DecimalField(max_digits=8, decimal_places=2)

    class Meta:
        ordering = ['min_miles']

    def covers(self, miles):
        if miles < self.min_miles:
            return False
        return self.max_miles is None or miles <= self.max_miles

    def __str__(self):
        upper = self.max_miles if self.max_miles is not None else '+'
        return f'{self.min_miles}–{upper} mi: ${self.reimbursement_amount}'

    @classmethod
    def amount_for(cls, miles):
        band = cls.objects.filter(min_miles__lte=miles).filter(
            models.Q(max_miles__gte=miles) | models.Q(max_miles__isnull=True)
        ).order_by('min_miles').first()
        return band.reimbursement_amount if band else Decimal('0.00')


class Staff(models.Model):
    """
    The operational staff record - deliberately separate from the
    login (settings.AUTH_USER_MODEL / apps.core.User), joined through
    approval, matching base44's own User-vs-Staff split (spec Section
    10). Rule: syncing profile data from User never overwrites a Staff
    field that already has a value with a blank one.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='staff_profile'
    )
    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)

    mailing_street = models.CharField(max_length=255, blank=True)
    mailing_city = models.CharField(max_length=120, blank=True)
    mailing_state = models.CharField(max_length=2, blank=True)
    mailing_zip = models.CharField(max_length=10, blank=True)
    shirt_size = models.CharField(max_length=10, blank=True)

    is_active = models.BooleanField(default=True)

    def sync_profile_from_user(self):
        """Never overwrite a good Staff value with a blank User value."""
        if not self.user:
            return
        for field in ('mailing_street', 'mailing_city', 'mailing_state', 'mailing_zip', 'shirt_size'):
            user_value = getattr(self.user, field, '')
            if user_value and not getattr(self, field):
                setattr(self, field, user_value)
        self.save()

    def __str__(self):
        return self.name


class AdminNote(models.Model):
    """
    Private, admin-only note on a staff member (spec Section 10).
    Distinct from the "note to the manager" a staff member attaches to
    their own AvailabilityRequest below - never expose this model
    through any staff-facing view or API.
    """

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='admin_notes')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class StaffAdjustment(models.Model):
    """
    A one-off pay correction tied directly to a staff member - a bonus
    or a fix that doesn't map cleanly to redoing one day's
    DailyWorkReport (spec Section 10, from base44's Staff Adjustments
    Card). Separate ledger from the normal void/replace mechanism.
    """

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='adjustments')
    amount = models.DecimalField(max_digits=8, decimal_places=2, help_text='Positive or negative.')
    reason = models.CharField(max_length=255)
    date = models.DateField(default=timezone.localdate)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')


class AvailabilityRequest(models.Model):
    """
    Day-level availability submitted by staff for an event (spec
    Section 10) - not a single request for the whole event. Approval
    happens on the event's own Staff tab, not a separate global queue.
    """

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='availability_requests')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='availability_requests')
    date = models.DateField()
    requested_pay_role = models.ForeignKey(PayRole, on_delete=models.PROTECT, related_name='+')
    note_to_manager = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('staff', 'event', 'date')]

    def approve(self, decided_by):
        """Approving creates the confirmed EventStaffAssignment."""
        self.status = self.Status.APPROVED
        self.decided_by = decided_by
        self.decided_at = timezone.now()
        self.save()
        EventStaffAssignment.objects.update_or_create(
            staff=self.staff, event=self.event, date=self.date,
            defaults={'pay_role': self.requested_pay_role},
        )


class EventStaffAssignment(models.Model):
    """
    Confirmed schedule intent: this person is expected to work this
    role on this day. NOT a paid day by itself - see the module
    docstring. Admins can also create this directly (the "Add Staff"
    path in base44), bypassing an AvailabilityRequest.
    """

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='assignments')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='assignments')
    date = models.DateField()
    pay_role = models.ForeignKey(PayRole, on_delete=models.PROTECT, related_name='+')

    class Meta:
        unique_together = [('staff', 'event', 'date')]


class DailyAttendance(models.Model):
    """
    A check-in: this person actually showed up and worked this role on
    this day. Checking in should also create the linked DailyWorkReport
    (see create_work_report()) - that's what actually puts someone on a
    payroll report, per the eligibility rule in the module docstring.
    """

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='attendance')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='attendance')
    date = models.DateField()
    pay_role = models.ForeignKey(PayRole, on_delete=models.PROTECT, related_name='+')
    checked_in_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('staff', 'event', 'date')]

    def create_work_report(self, drove_personal_vehicle=False, travel_miles=None, created_by=None):
        """
        Freeze pay values at THE MOMENT this is called - the fix for
        base44's live-recalculation bug (see module docstring). Safe to
        call once per attendance; returns the existing report if one
        is already linked.
        """
        existing = DailyWorkReport.objects.filter(
            staff=self.staff, event=self.event, work_date=self.date, status=DailyWorkReport.Status.ACTIVE
        ).first()
        if existing:
            return existing

        settings_row = GlobalPayrollSettings.objects.first()
        global_per_diem = settings_row.global_per_diem if settings_row else Decimal('0.00')

        per_diem = global_per_diem if self.pay_role.per_diem_eligible else Decimal('0.00')
        travel_reimbursement = Decimal('0.00')
        if drove_personal_vehicle and travel_miles:
            travel_reimbursement = MileageBand.amount_for(travel_miles)

        return DailyWorkReport.objects.create(
            staff=self.staff,
            event=self.event,
            work_date=self.date,
            pay_role=self.pay_role,
            source=DailyWorkReport.Source.CHECK_IN,
            day_rate=self.pay_role.daily_rate,
            per_diem=per_diem,
            drove_personal_vehicle=drove_personal_vehicle,
            travel_miles=travel_miles,
            travel_reimbursement=travel_reimbursement,
            created_by=created_by,
        )


class DailyWorkReport(models.Model):
    """
    THE monetary source of truth for payroll (spec Section 10-11). All
    dollar values are frozen at creation time - see the module
    docstring for why this matters. Voided, never deleted or edited,
    to correct a mistake (same pattern as Expense).
    """

    class Status(models.TextChoices):
        ACTIVE = 'active', 'Active'
        VOIDED = 'voided', 'Voided'

    class Source(models.TextChoices):
        CHECK_IN = 'check_in', 'Staff check-in'
        ADMIN_ENTRY = 'admin_entry', 'Admin-created'

    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='work_reports')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='work_reports')
    work_date = models.DateField()
    pay_role = models.ForeignKey(PayRole, on_delete=models.PROTECT, related_name='+')
    source = models.CharField(max_length=20, choices=Source.choices)

    # Frozen at creation - never recalculated from a later rate change.
    day_rate = models.DecimalField(max_digits=8, decimal_places=2)
    per_diem = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))
    drove_personal_vehicle = models.BooleanField(default=False)
    travel_miles = models.PositiveIntegerField(null=True, blank=True)
    travel_reimbursement = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    voided_reason = models.CharField(max_length=255, blank=True)
    replaces = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='replaced_by',
        help_text='If this report corrects a voided one, link to it here.',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def day_total(self):
        return self.day_rate + self.per_diem + self.travel_reimbursement

    def void(self, reason=''):
        self.status = self.Status.VOIDED
        self.voided_reason = reason
        self.save(update_fields=['status', 'voided_reason'])

    def __str__(self):
        return f'{self.staff.name} — {self.event.name} — {self.work_date}'


class PayrollPeriod(models.Model):
    """
    Weekly payroll (spec Section 10). Compiled -> Approved. Approval
    locks the period; further corrections go through void/replace on
    the underlying DailyWorkReport rows, not by editing this record.
    Approval also triggers paystub generation (see Paystub below).
    """

    class Status(models.TextChoices):
        COMPILED = 'compiled', 'Compiled'
        APPROVED = 'approved', 'Approved'

    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.COMPILED)
    compiled_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        ordering = ['-start_date']

    def eligible_work_reports(self):
        return DailyWorkReport.objects.filter(
            work_date__gte=self.start_date, work_date__lte=self.end_date, status=DailyWorkReport.Status.ACTIVE,
        )

    def approve(self, approved_by):
        """
        Locks the period and generates one paystub per eligible
        employee. Idempotent - see Paystub.get_or_create semantics.
        Actual PDF rendering is left to the view/service layer; this
        just guarantees exactly one Paystub row per employee+period.
        """
        self.status = self.Status.APPROVED
        self.approved_at = timezone.now()
        self.approved_by = approved_by
        self.save(update_fields=['status', 'approved_at', 'approved_by'])

        staff_ids = self.eligible_work_reports().values_list('staff_id', flat=True).distinct()
        for staff_id in staff_ids:
            Paystub.objects.get_or_create(payroll_period=self, staff_id=staff_id)

    def __str__(self):
        return f'Payroll {self.start_date} – {self.end_date} ({self.status})'


class Paystub(models.Model):
    """
    One per employee per payroll period (spec Section 10) - enforced
    by unique_together so re-approving/revisiting can never duplicate.
    The PDF itself is generated once and stored permanently (a
    FileField once real file storage is configured); never regenerated
    on view.
    """

    payroll_period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='paystubs')
    staff = models.ForeignKey(Staff, on_delete=models.CASCADE, related_name='paystubs')
    pdf_file = models.FileField(upload_to='paystubs/%Y/%m/', null=True, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    emailed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [('payroll_period', 'staff')]

    def __str__(self):
        return f'Paystub — {self.staff.name} — {self.payroll_period}'
