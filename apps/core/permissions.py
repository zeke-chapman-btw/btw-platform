"""
Central scope enforcement (spec Section 2 / Section 8).

The spec is explicit that "most access bugs come from getting scope
wrong, so build that check into one central place and not scatter it
through the code." This module is that one place. Views should call
these helpers rather than hand-rolling their own filters.

This is a starting skeleton, not a finished authorization layer - fill
in real queryset filtering here as each module (participants, events,
customer portal) is built, instead of re-deriving scope rules per view.
"""

from apps.core.models import Role


def is_admin(user):
    return user.is_authenticated and user.role == Role.ADMIN


def is_event_lead_or_admin(user):
    return user.is_authenticated and user.role in (Role.ADMIN, Role.EVENT_LEAD)


def is_staff_role(user):
    return user.is_authenticated and user.role in (Role.ADMIN, Role.EVENT_LEAD, Role.STAFF)


def is_customer(user):
    return user.is_authenticated and user.role == Role.CUSTOMER


def visible_events_for(user):
    """
    Scope events to what a user is allowed to see.

    - Admin: everything.
    - Event lead / staff: events they're assigned to (TODO: filter by
      staffing.EventStaffAssignment once that app's views exist).
    - Customer: events reachable through their Customer's Agreements,
      honoring each Agreement's exclusivity window (spec Section 8:
      shareable_from = agreement.end_date + agreement.buffer_days,
      evaluated at read time, never precomputed).
    """
    from apps.events.models import Event

    if is_admin(user):
        return Event.objects.all()
    if is_customer(user):
        # Placeholder - real implementation joins through
        # customers.Agreement / customers.AgreementEvent and applies the
        # exclusivity-window check described in spec Section 8.
        return Event.objects.none()
    # Staff / event lead: placeholder until EventStaffAssignment exists.
    return Event.objects.none()
