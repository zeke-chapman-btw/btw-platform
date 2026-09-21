"""
Events, daily staffing needs, expenses, and the finalized cost-per-lead
report.

Field names on Event mirror base44's actual source code (spec Section
4/10), not a guess from screenshots - that's deliberate, since it makes
migrating history later much simpler if the field names already line
up.

Two behaviors carried over on purpose from what actually works well in
base44, and one bug deliberately NOT carried over:

  - Publishing (draft -> upcoming) re-validates the location pin
    SERVER-SIDE in `Event.publish()`, not just in a form. Never trust
    a client-side check alone for a state change that matters.
  - `daily_needs` (per-day staffing counts) is the real source of
    truth; nothing here stores a flat event-wide "staff needed" number
    as primary data.
  - THE BUG NOT TO COPY: base44's payroll report recalculates base pay
    live from whatever the CURRENT PayRole rates say, so editing a
    rate today silently rewrites every past event's numbers. This
    platform freezes pay values onto DailyWorkReport at the time the
    report is created instead (see apps/staffing/models.py).
"""

from django.db import models
from django.utils import timezone


class Event(models.Model):
    class EventType(models.TextChoices):
        NASCAR_RACE = 'nascar_race', 'NASCAR race'
        RODEO = 'rodeo', 'Rodeo'
        SKILLS_CHALLENGE = 'skills_challenge', 'Skills challenge'
        TRADESHOW = 'tradeshow', 'Tradeshow'
        JOB_FAIR = 'job_fair', 'Job fair'
        OTHER = 'other', 'Other'

    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        UPCOMING = 'upcoming', 'Upcoming'
        COMPLETED = 'completed', 'Completed'
        CANCELLED = 'cancelled', 'Cancelled'
        ARCHIVED = 'archived', 'Archived'

    class HousingType(models.TextChoices):
        HOTEL = 'hotel', 'Hotel'
        AIRBNB = 'airbnb', 'Airbnb'
        OTHER = 'other', 'Other'

    name = models.CharField(max_length=255)
    event_type = models.CharField(max_length=30, choices=EventType.choices, blank=True)
    event_type_custom = models.CharField(max_length=255, blank=True)

    venue_name = models.CharField(max_length=255, blank=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip = models.CharField(max_length=10, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)

    setup_date = models.DateField(null=True, blank=True)
    setup_arrival_time = models.TimeField(null=True, blank=True)
    start_date = models.DateField()
    start_time = models.TimeField(null=True, blank=True)
    end_date = models.DateField()
    end_time = models.TimeField(null=True, blank=True)
    arrival_home_date = models.DateField(null=True, blank=True)

    staff_signup_deadline = models.DateTimeField(
        null=True, blank=True,
        help_text='After this, staff can no longer submit or edit availability. Blank = no cutoff.',
    )

    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # Event contact - shown to both staff and admins (spec Section 4).
    contact_name = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)

    # Housing - lodging details attached to the event (spec Section 4).
    housing_type = models.CharField(max_length=20, choices=HousingType.choices, blank=True)
    hotel_name = models.CharField(max_length=255, blank=True)
    housing_address = models.CharField(max_length=255, blank=True)
    housing_city = models.CharField(max_length=120, blank=True)
    housing_state = models.CharField(max_length=2, blank=True)
    housing_zip = models.CharField(max_length=10, blank=True)
    housing_info = models.TextField(blank=True, help_text='WiFi network/password, check-out instructions, etc.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']  # most-recent-first everywhere, per base44 build notes

    def __str__(self):
        return self.name

    def publish(self):
        """
        Draft -> upcoming. Mirrors base44's real behavior: the location
        pin requirement is enforced HERE, server-side, not only in a
        form. Call this from the view/API instead of setting
        status='upcoming' directly, so the guard can't be skipped.
        """
        if self.latitude is None or self.longitude is None:
            raise ValueError('A location pin is required before publishing to staff.')
        self.status = self.Status.UPCOMING
        self.save(update_fields=['status', 'updated_at'])


class DailyStaffingNeed(models.Model):
    """
    Per-day staffing targets by role - the real source of truth for
    "how many people do we need," per spec Section 4/10. An event-wide
    total, if you ever want one for a summary view, is derived from
    these (max or sum across days), never stored as primary data.
    """

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='daily_needs')
    date = models.DateField()
    pay_role = models.ForeignKey('staffing.PayRole', on_delete=models.PROTECT, related_name='daily_needs')
    count_needed = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [('event', 'date', 'pay_role')]
        ordering = ['date']


class Expense(models.Model):
    """
    Hand-entered per-event expense (spec Section 11). Voided rather
    than deleted once it could have been reported - same audit-trail
    pattern used for DailyWorkReport in apps/staffing/models.py.
    """

    class Category(models.TextChoices):
        FUEL = 'fuel', 'Fuel'
        FOOD = 'food', 'Food'
        LODGING = 'lodging', 'Lodging'
        MARKETING = 'marketing', 'Marketing'
        SUPPLIES = 'supplies', 'Supplies'
        OTHER = 'other', 'Other'

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='expenses')
    description = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=Category.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    receipt_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    is_voided = models.BooleanField(default=False)
    voided_reason = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f'{self.description} — ${self.amount}'


class EventReport(models.Model):
    """
    The finalized, locked cost-per-lead report for one event (spec
    Section 11). Confirmed formula, straight from base44's real
    report:

        total_event_cost = payroll_total + other_expenses_total
        cost_per_lead = total_event_cost / total_leads
        cost_per_qualified_lead = total_event_cost / qualified_leads
        lead_qualification_rate = qualified_leads / total_leads

    total_leads and qualified_leads should eventually be computed
    automatically (attendances, and the qualification-rule engine
    described in spec Section 11) rather than hand-entered - but the
    fields stay here either way, since the report needs to freeze a
    snapshot of them once finalized regardless of how they were
    produced.
    """

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name='report')

    total_leads = models.PositiveIntegerField(default=0)
    qualified_leads = models.PositiveIntegerField(default=0)

    # Simulator/station play-count metric, generalized from base44's
    # "Excavator Plays" (spec Section 12 backlog doc). Add one row per
    # station type if you run more than one; kept as a simple count
    # here since the exact station lineup may still change.
    station_play_counts = models.JSONField(
        default=dict, blank=True,
        help_text='e.g. {"excavator_simulator": 41, "kiosk_test": 141}',
    )

    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)

    # Two separate retrospective note fields, straight from base44's
    # own finalized report - distinct from the per-participant
    # flags/notes in apps/participants/models.py.
    event_notes = models.TextField(blank=True, help_text='Operational retrospective (e.g. staffing/logistics).')
    lead_notes = models.TextField(blank=True, help_text='Qualitative notes about the crowd/leads.')

    @property
    def payroll_total(self):
        from apps.staffing.models import DailyWorkReport
        reports = DailyWorkReport.objects.filter(event=self.event, status=DailyWorkReport.Status.ACTIVE)
        return sum((r.day_total for r in reports), start=0)

    @property
    def expenses_total(self):
        return sum(
            (e.amount for e in self.event.expenses.filter(is_voided=False)),
            start=0,
        )

    @property
    def total_event_cost(self):
        return self.payroll_total + self.expenses_total

    @property
    def lead_qualification_rate(self):
        if not self.total_leads:
            return None
        return self.qualified_leads / self.total_leads

    @property
    def cost_per_lead(self):
        if not self.total_leads:
            return None
        return self.total_event_cost / self.total_leads

    @property
    def cost_per_qualified_lead(self):
        if not self.qualified_leads:
            return None
        return self.total_event_cost / self.qualified_leads

    def finalize(self):
        """Lock the report. Corrections after this go through void/replace, not edits."""
        self.is_finalized = True
        self.finalized_at = timezone.now()
        self.save(update_fields=['is_finalized', 'finalized_at'])

    def __str__(self):
        return f'Report — {self.event.name}'
