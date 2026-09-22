import datetime
import re

from django.shortcuts import render, redirect

from apps.events.models import Event
from apps.formbuilder.models import EventTypePreset, FormTemplate, FormResponse
from apps.participants.models import Participant, Attendance

JOB_STATUS_CHOICES = [
    'Currently employed in construction and/or a trade',
    'Currently employed in another industry',
    'Unemployed and looking for work',
    'High school',
    'College',
    'Trade school',
    'Retired',
    'Other',
]

INDUSTRY_CHOICES = [
    'Construction',
    'Auto Mechanic / Mechanic',
    'Manufacturing',
    'Transportation & Logistics',
    'Agriculture',
    'Electrical Trade',
    'Welding',
    'Plumbing',
    'Business / Management',
    'Retail / Hospitality',
    'Other',
]

SKILLS_CHOICES = [
    'Heavy Equipment Operation', 'Excavator Operation', 'Dozer Operation',
    'Loader Operation', 'Motor Grader Operation', 'Skid Steer Operation',
    'Backhoe Operation', 'Crane Operation', 'Forklift Operation',
    'CDL Driver (Class A/B)', 'Dump Truck Operation', 'Commercial Driving',
    'General Construction Labor', 'Site Development', 'Earthwork & Grading',
    'Utility Installation (Water, Sewer, Storm Drain)', 'Concrete Work',
    'Asphalt Paving', 'Road Construction', 'Demolition', 'Erosion Control',
    'Carpentry', 'Framing', 'Welding', 'Fabrication', 'Pipefitting',
    'Plumbing', 'Electrical Work', 'HVAC', 'Masonry', 'Surveying',
    'Blueprint Reading', 'Equipment Maintenance', 'Mechanical Repair',
    'Fleet Maintenance', 'Land Clearing', 'Warehouse Operations',
    'Logistics & Material Handling', 'Inventory Management',
    'Shipping & Receiving', 'Safety Management',
    'Crew Leadership / Foreman Experience', 'Project Management',
    'Quality Control', 'Manufacturing Experience',
    'Agriculture / Farming Equipment Operation', 'Computer Skills',
    'GPS Machine Control Systems', 'Drone Operation',
    'Estimating / Preconstruction', 'Other',
]

LICENSE_CHOICES = [
    'CDL Class A', 'CDL Class B', 'CDL Permit (CLP)', 'OSHA 10', 'OSHA 30',
    'MSHA Part 46', 'MSHA Part 48', 'CPR / First Aid', 'AED Certified',
    'NCCER Certified', 'NCCCO Crane Operator', 'Rigger Certification',
    'Signal Person Certification', 'Certified Flagger',
    'Confined Space Entry',
    'Competent Person - Excavation & Trenching',
    'Competent Person - Fall Protection',
    'Competent Person - Scaffolding',
    'Forklift Certification', 'Aerial Lift Certification',
    'Telehandler Certification', 'Excavator Certification',
    'Dozer Certification', 'Heavy Equipment Operator Certification',
    'Welding Certification', 'AWS Certified Welder', 'TWIC Card',
    'HAZWOPER (40-Hour)', 'DOT Medical Card',
    'Electrician Apprentice License', 'Journeyman Electrician License',
    'Master Electrician License', 'Electrical Contractor License',
    'Plumbing Apprentice License', 'Journeyman Plumber License',
    'Master Plumber License', 'HVAC Certification', 'EPA 608 Certification',
    'Pipefitter Certification', 'Lineman Certification',
    'Utility Locator Certification', 'Traffic Control Supervisor (TCS)',
    'Traffic Control Technician (TCT)',
    'Commercial Drone Pilot (FAA Part 107)',
    'Military Occupational Training/Certification',
    "Valid Driver's License", 'Other',
]

TRAVEL_CHOICES = ['Yes', 'No', 'Maybe']

REFERRAL_CHOICES = [
    'Community Event', 'Nascar', 'Trade Show', 'Career Fair',
    'Google/ Website', 'Social Media', 'Email', 'Friend/ Family Member',
    'Other',
]


def _normalize_phone(phone):
    return re.sub(r'\D', '', phone or '')


def _resolve_todays_event():
    today = datetime.date.today()
    return (
        Event.objects.filter(start_date__lte=today, end_date__gte=today)
        .order_by('start_date')
        .first()
    )


def _intake_template_version(event):
    template = None
    preset = EventTypePreset.objects.filter(event_type=event.event_type).first()
    if preset:
        template = preset.form_template
    if not template:
        template = FormTemplate.objects.filter(applies_to=FormTemplate.AppliesTo.INTAKE).first()
    if not template:
        return None, None
    return template, template.current_version()


def _find_existing_participant(phone):
    normalized = _normalize_phone(phone)
    if not normalized:
        return None
    for candidate in Participant.objects.exclude(phone=''):
        if _normalize_phone(candidate.phone) == normalized:
            return candidate
    return None


def intake_form(request):
    event = _resolve_todays_event()
    if not event:
        return render(request, 'intake/error.html', {'message': "There's no event running today. Please check with staff."})
    template, version = _intake_template_version(event)
    sections = []
    if version:
        sections = list(version.sections.order_by('order').prefetch_related('form_questions__question'))

    context = {
        'event': event,
        'template': template,
        'sections': sections,
        'job_status_choices': JOB_STATUS_CHOICES,
        'industry_choices': INDUSTRY_CHOICES,
        'skills_choices': SKILLS_CHOICES,
        'license_choices': LICENSE_CHOICES,
        'travel_choices': TRAVEL_CHOICES,
        'referral_choices': REFERRAL_CHOICES,
        'posted': {'skills': [], 'licenses_certifications': []},
    }

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        job_status = request.POST.get('job_status', '').strip()
        industry_interest = request.POST.get('industry_interest', '').strip()
        work_history = request.POST.get('work_history', '').strip()
        skills = request.POST.getlist('skills')
        licenses_certifications = request.POST.getlist('licenses_certifications')
        education = request.POST.get('education', '').strip()
        willing_to_travel_raw = request.POST.get('willing_to_travel', '')
        referral_source = request.POST.get('referral_source', '').strip()
        opt_in_raw = request.POST.get('communications_opt_in', '')

        name = (first_name + ' ' + last_name).strip()
        posted = {
            'first_name': first_name, 'last_name': last_name, 'email': email,
            'phone': phone, 'address': address, 'city': city, 'state': state,
            'job_status': job_status, 'industry_interest': industry_interest,
            'work_history': work_history, 'skills': skills,
            'licenses_certifications': licenses_certifications,
            'education': education, 'willing_to_travel': willing_to_travel_raw,
            'referral_source': referral_source,
            'communications_opt_in': opt_in_raw,
        }
        context['posted'] = posted

        if not first_name or not last_name or not phone or not email:
            context['error'] = 'Please fill in your name, email, and phone number.'
            return render(request, 'intake/form.html', context)

        if willing_to_travel_raw == 'Yes':
            willing_to_travel = True
        elif willing_to_travel_raw == 'No':
            willing_to_travel = False
        else:
            willing_to_travel = None

        field_values = dict(
            name=name, email=email, address=address, city=city, state=state,
            job_status=job_status, industry_interest=industry_interest,
            work_history=work_history, skills=skills,
            licenses_certifications=licenses_certifications, education=education,
            willing_to_travel=willing_to_travel, referral_source=referral_source,
            communications_opt_in=(opt_in_raw == 'Yes'),
        )

        participant = _find_existing_participant(phone)
        if participant:
            for field, value in field_values.items():
                setattr(participant, field, value)
            participant.phone = phone
            participant.save()
        else:
            participant = Participant.objects.create(phone=phone, **field_values)

        Attendance.objects.get_or_create(
            participant=participant, event=event,
            defaults={'source': Attendance.Source.ONLINE_LEAD},
        )

        if version:
            answers = {}
            for section in sections:
                for fq in section.form_questions.all():
                    q = fq.question
                    field_name = f'q_{fq.id}'
                    value = request.POST.getlist(field_name) if q.type == 'multi_choice' else request.POST.get(field_name, '')
                    answers[str(fq.id)] = {'label': q.label, 'value': value}
            FormResponse.objects.create(form_version=version, answers=answers)

        return redirect(f"/intake/done/?name={name}&event={event.name}")

    return render(request, 'intake/form.html', context)


def intake_done(request):
    return render(request, 'intake/done.html', {
        'name': request.GET.get('name', ''),
        'event_name': request.GET.get('event', ''),
    })
