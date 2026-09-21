# Built To Work — Event Trailer Platform

Django project scaffold, generated from `event-trailer-platform-spec.md`.
Every model file has a docstring pointing back to the relevant spec
section, and to the base44 research (screenshots + real source code)
that shaped it — read those before changing anything, since several
choices here (frozen pay values, server-side publish validation,
void-not-delete) are deliberately fixing a bug seen in the current
system, not arbitrary.

## What's here

```
config/            Django project settings, urls, wsgi
apps/
  core/            Custom User model, roles, central scope/permission helpers
  participants/    Participant identity, intake attendance, on-site flags/notes
  stations/        Kiosk / hunting game / simulator results (one shared model)
  formbuilder/     Forms & questions as admin-editable data, with versioning
  events/          Event details, daily staffing needs, expenses, cost-per-lead report
  staffing/        Pay roles, mileage bands, assignments, check-in, work reports,
                    payroll periods, paystubs, adjustments
  customers/       Customers, agreements, plans, exclusivity windows
  opportunities/   HubSpot-linked opportunities and participant interest
```

## What this scaffold does NOT include yet

This is deliberately just the data layer (models + Django admin), not
the actual user-facing app. Nothing here has been run or tested — see
"First run" below to do that yourself, since the sandbox this was
written in couldn't reach PyPI to install Django and verify it live.

Still to build, roughly in the spec's suggested order (Section 14b):

1. The intake form itself (participant-facing, served from the trailer,
   works offline) — currently just the `Participant`/`Attendance` models
2. The station API + the simulator "station agent" (once the real CSV
   format is known — see spec Section 12)
3. Trailer <-> cloud sync (the outbox/versioning pattern from spec
   Section 3)
4. The on-site event console (scan, flag, note, leaderboard)
5. Staff-facing pages (sign-up, check-in) — the *data model* for this
   is the most complete part of the scaffold; the actual pages aren't
   built
6. The customer portal
7. Real PDF generation for event/payroll reports and paystubs (deliberately
   NOT `window.print()` over the screen layout — see the note in
   `apps/staffing/models.py` about the printing bug this avoids)
8. HubSpot sync

## First run (do this on a machine with normal internet access)

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Then visit http://127.0.0.1:8000/admin/ and log in. Every model has a
registered admin screen, so you can create a PayRole, a MileageBand, an
Event, etc. right away and see the relationships work.

By default this uses SQLite (`db.sqlite3`, created automatically) — no
database server needed. That's intentional: the trailer server is meant
to run fully offline (spec Section 7), so SQLite is the right default
there. For the cloud deployment, set these environment variables to
switch to Postgres with no code changes:

```bash
export DJANGO_DB_ENGINE=postgres
export POSTGRES_DB=btw_platform
export POSTGRES_USER=btw_platform
export POSTGRES_PASSWORD=...
export POSTGRES_HOST=...
```

## A few things worth reading before extending this

- **`apps/staffing/models.py` module docstring** — explains the
  assignment-vs-work-report split, and the frozen-pay-value fix for a
  real bug found in base44's current code (it recalculates historical
  pay from *today's* rate table; this scaffold freezes values at the
  moment a work report is created instead).
- **`apps/events/models.py` — `Event.publish()`** — the location-pin
  requirement is enforced here, server-side, not just in a future form.
  Apply that same pattern to any other state change that matters
  (approving payroll, finalizing a report).
- **`apps/customers/models.py` — `Agreement.is_shareable_as_of()`** —
  the exclusivity-window formula (`end_date + buffer_days`), evaluated
  at read time. Never cache or precompute this.
- **`apps/formbuilder/models.py`** — this is what lets BTW staff edit
  intake/kiosk questions with no code (spec Section 14a). `FormVersion`
  is immutable once created; edit by calling
  `FormTemplate.new_version()`, never by mutating an old version's
  questions.
- **`apps/core/permissions.py`** — intentionally a thin skeleton right
  now. Fill in real scope filtering here as each module gets views,
  rather than re-deriving access rules per view.
