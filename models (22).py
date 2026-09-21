"""
Customers, agreements, plans, and the exclusivity window.

Spec Section 8. The core rule this app exists to make easy:

    shareable_from = agreement.end_date + agreement.buffer_days

...evaluated at the moment data is viewed, never precomputed by a
scheduled job. Extending or ending an agreement changes visibility
immediately, with no cleanup job to run. See
`Agreement.is_shareable_as_of()` below.
"""

from django.db import models
from django.utils import timezone


class Plan(models.Model):
    """
    A bundle of access levers (spec Section 8) so pricing changes are a
    config edit, not a code change. Kept intentionally small - add
    levers only when a real deal needs one, per the spec's warning
    against over-building this before the sales side has settled on
    tiers.
    """

    class DetailLevel(models.TextChoices):
        AGGREGATE = 'aggregate', 'Aggregate stats only'
        ANONYMIZED = 'anonymized', 'Anonymized profiles'
        FULL_CONTACT = 'full_contact', 'Full contact details'

    name = models.CharField(max_length=120)
    includes_shared_pool = models.BooleanField(
        default=False,
        help_text='Whether this plan grants access to the broader shared dashboard, '
                   'in addition to the customer\'s own exclusive events.',
    )
    detail_level = models.CharField(max_length=20, choices=DetailLevel.choices, default=DetailLevel.ANONYMIZED)
    monthly_record_cap = models.PositiveIntegerField(null=True, blank=True)
    allows_export = models.BooleanField(default=False)
    industry_filter = models.CharField(max_length=255, blank=True, help_text='Comma-separated, optional.')
    region_filter = models.CharField(max_length=255, blank=True, help_text='Comma-separated, optional.')

    def __str__(self):
        return self.name


class Customer(models.Model):
    name = models.CharField(max_length=255)
    primary_contact_name = models.CharField(max_length=255, blank=True)
    primary_contact_email = models.EmailField(blank=True)
    primary_contact_phone = models.CharField(max_length=30, blank=True)

    def __str__(self):
        return self.name


class Agreement(models.Model):
    """
    Sits between a Customer and the Events it covers. Deliberately its
    own record (not a field on Customer) so a company can have several
    agreements over time - e.g. a 6-month hiring engagement, then a
    renewal on a different plan - with a clean history of who had
    access to what, when.
    """

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='agreements')
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT, related_name='agreements')
    start_date = models.DateField()
    end_date = models.DateField()
    buffer_days = models.PositiveIntegerField(
        default=0,
        help_text='Days after end_date that data stays exclusive before becoming shareable.',
    )
    events = models.ManyToManyField(
        'events.Event',
        related_name='agreements',
        blank=True,
        help_text='Events explicitly tied to this agreement (in addition to any '
                   'date-range auto-assignment your event-creation flow adds).',
    )

    def is_shareable_as_of(self, when=None):
        """
        The one formula this whole model exists to compute correctly
        (spec Section 8). Call this at read time - never cache the
        result, since extending/ending an agreement must take effect
        immediately.
        """
        when = when or timezone.localdate()
        shareable_from = self.end_date + timezone.timedelta(days=self.buffer_days)
        return when >= shareable_from

    def __str__(self):
        return f'{self.customer.name} — {self.plan.name} ({self.start_date} to {self.end_date})'


class CustomerViewer(models.Model):
    """
    A customer can have several logins; one is the admin who can invite
    the others (spec Section 2 recommendation). This just tracks who
    invited whom - the login itself is apps.core.User with role=CUSTOMER
    and customer set.
    """

    user = models.OneToOneField('core.User', on_delete=models.CASCADE, related_name='viewer_profile')
    invited_by = models.ForeignKey(
        'core.User', null=True, blank=True, on_delete=models.SET_NULL, related_name='invited_viewers'
    )
    is_customer_admin = models.BooleanField(default=False)
