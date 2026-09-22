"""
HubSpot integration surface (spec Section 9). This platform stays the
system of record for identity, events, results, and opportunities;
HubSpot owns communication and engagement (emails, clicks, calls). The
join key is Participant.hubspot_contact_id (apps/participants/models.py).

Opportunity records are kept deliberately small - the platform doesn't
try to replace HubSpot's campaign/email tooling, just track enough to
answer "who's interested in this specific job opening" for the
customer portal.
"""

from django.db import models


class Opportunity(models.Model):
    class Status(models.TextChoices):
        OPEN = 'open', 'Open'
        FILLED = 'filled', 'Filled'
        CLOSED = 'closed', 'Closed'

    customer = models.ForeignKey('customers.Customer', on_delete=models.CASCADE, related_name='opportunities')
    agreement = models.ForeignKey(
        'customers.Agreement', null=True, blank=True, on_delete=models.SET_NULL, related_name='opportunities'
    )
    title = models.CharField(max_length=255)
    pay_description = models.CharField(max_length=120, blank=True, help_text='e.g. "$28/hr" or "$65k/yr".')
    location = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    hubspot_campaign_id = models.CharField(max_length=64, blank=True)

    def __str__(self):
        return self.title


class Interest(models.Model):
    """A participant responded to an opportunity - typically via a
    HubSpot email click that gets synced back (spec Section 9)."""

    class InterestStatus(models.TextChoices):
        INTERESTED = 'interested', 'Interested'
        CONTACTED = 'contacted', 'Contacted'
        NOT_INTERESTED = 'not_interested', 'Not interested'

    participant = models.ForeignKey('participants.Participant', on_delete=models.CASCADE, related_name='interests')
    opportunity = models.ForeignKey(Opportunity, on_delete=models.CASCADE, related_name='interests')
    status = models.CharField(max_length=20, choices=InterestStatus.choices, default=InterestStatus.INTERESTED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('participant', 'opportunity')]


class Interaction(models.Model):
    """
    Engagement synced back from HubSpot: clicks, form fills, and call
    notes (spec Section 9). Call notes default to internal and are
    released to customers the same way participant Notes are (spec
    Section 6) - deliberately not duplicating that release mechanism
    here; a real implementation should probably share it.
    """

    class Kind(models.TextChoices):
        EMAIL_CLICK = 'email_click', 'Email click'
        FORM_FILL = 'form_fill', 'Form fill'
        CALL_NOTE = 'call_note', 'Call note'
        OTHER = 'other', 'Other'

    participant = models.ForeignKey('participants.Participant', on_delete=models.CASCADE, related_name='interactions')
    kind = models.CharField(max_length=20, choices=Kind.choices)
    campaign_reference = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True, help_text='Call note text, if applicable.')
    occurred_at = models.DateTimeField()
    synced_at = models.DateTimeField(auto_now_add=True)
    is_released_to_customers = models.BooleanField(default=False)
