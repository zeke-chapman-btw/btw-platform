"""
Participant identity, intake, attendance, and on-site flags/notes.

Spec Sections 4 and 6. The central design decision: ONE permanent
Participant per person (a UUID that works at every event), with an
Attendance record per event they show up at. Everything else - station
results, flags, notes - hangs off the Attendance, not the Participant
directly, so that access rules tied to a specific event (exclusivity,
customer visibility) apply automatically and can't leak across a
person's history at a different, unrelated event.
"""

import uuid

from django.conf import settings
from django.db import models


class ConsentVersion(models.Model):
    """
    A specific wording of the consent/privacy text (spec Section 4/8).
    Store which version each participant agreed to, since consent
    wording controls what can later be shared with customers and it
    can't be applied retroactively.
    """

    version_label = models.CharField(max_length=40, unique=True)
    body = models.TextField()
    effective_date = models.DateField()

    def __str__(self):
        return self.version_label


class Participant(models.Model):
    """
    One record per person, forever. `public_id` is the UUID encoded in
    the QR ticket - random, and carrying no personal information on its
    own (spec Section 4).
    """

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    name = models.CharField(max_length=255)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)
    state = models.CharField(max_length=2, blank=True)

    job_status = models.CharField(max_length=120, blank=True)
    industry_interest = models.CharField(max_length=255, blank=True)
    work_history = models.TextField(blank=True)
    skills = models.JSONField(default=list, blank=True)
    licenses_certifications = models.JSONField(default=list, blank=True)
    education = models.CharField(max_length=255, blank=True)
    willing_to_travel = models.BooleanField(null=True, blank=True)
    referral_source = models.CharField(max_length=120, blank=True)

    communications_opt_in = models.BooleanField(default=False)
    consent_version = models.ForeignKey(
        ConsentVersion, null=True, blank=True, on_delete=models.PROTECT, related_name='participants',
    )

    hubspot_contact_id = models.CharField(max_length=64, blank=True, help_text='Join key for the HubSpot sync.')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Attendance(models.Model):
    """
    One person, at one event. Everything event-specific (station
    results, flags, notes, exclusivity/visibility) attaches here, not
    to Participant directly - see the module docstring.
    """

    class Source(models.TextChoices):
        WALK_UP = 'walk_up', 'Walk-up at the trailer'
        PRE_REGISTRATION = 'pre_registration', 'Pre-registered'
        ONLINE_LEAD = 'online_lead', 'Online lead form'

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='attendances')
    event = models.ForeignKey('events.Event', on_delete=models.CASCADE, related_name='attendances')
    source = models.CharField(max_length=20, choices=Source.choices)
    referral_source = models.CharField(max_length=120, blank=True)
    checked_in_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('participant', 'event')]

    def __str__(self):
        return f'{self.participant.name} @ {self.event.name}'


class Flag(models.Model):
    """
    Objective, customer-visible marker on an attendance (spec Section
    6) - e.g. "top 3 in contest," "completed all stations." Kept
    separate from Note below, which is internal-by-default.
    """

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='flags')
    label = models.CharField(max_length=120)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.label


class Note(models.Model):
    """
    Staff note on an attendance - internal by default, released to
    specific customers by an admin (spec Section 6). Every release is
    logged via `released_to` + `released_at`/`released_by`.
    """

    attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, related_name='notes')
    body = models.TextField()
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    is_released = models.BooleanField(default=False)
    released_to = models.ManyToManyField('customers.Customer', blank=True, related_name='released_notes')
    released_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )
    released_at = models.DateTimeField(null=True, blank=True)
