"""
Custom user model and access control.

Spec Section 2 defines four roles: admin/manager, event lead, event
staff/driver, and customer. Each user also has a *scope* - what data
they can actually reach, not just what actions they're allowed to
attempt. Scope is enforced in `permissions.py`, in one place, rather
than scattered through every view - that's a deliberate call in the
spec, because most access bugs come from getting scope wrong in some
forgotten corner of the app.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    ADMIN = 'admin', 'Admin / manager'
    EVENT_LEAD = 'event_lead', 'Event lead'
    STAFF = 'staff', 'Event staff / driver'
    CUSTOMER = 'customer', 'Customer'


class User(AbstractUser):
    """
    The authenticated login. Kept deliberately separate from the
    operational `staffing.Staff` record (see apps/staffing/models.py) -
    base44's own architecture makes the same split, and the spec's
    Section 10 explicitly calls out never overwriting a good Staff
    value with a blank one when the two are synced.
    """

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.STAFF)

    # Set when role == CUSTOMER. A customer user's scope is entirely
    # defined by which Agreements their Customer holds (spec Section 8).
    customer = models.ForeignKey(
        'customers.Customer',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='users',
        help_text='Set only for customer-role users. Determines portal scope.',
    )

    # Onboarding/profile fields that need to transfer to the Staff record
    # without ever overwriting a value Staff already has (spec Section 10,
    # confirmed by base44's own "push profile data through" build item).
    mailing_street = models.CharField(max_length=255, blank=True)
    mailing_city = models.CharField(max_length=120, blank=True)
    mailing_state = models.CharField(max_length=2, blank=True)
    mailing_zip = models.CharField(max_length=10, blank=True)
    shirt_size = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return self.get_full_name() or self.username
