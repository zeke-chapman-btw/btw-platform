import datetime
import re

from django.shortcuts import render, redirect

from apps.events.models import Event
from apps.formbuilder.models import EventTypePreset, FormTemplate, FormResponse
from apps.participants.models import Participant, Attendance


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
        return render(request, 'intake/error.html', {
            'message': "There's no event running today. Please check with staff.",
        })

    template, version = _intake_template_version(event)
    sections = []
    if version:
        sections = list(version.sections.order_by('order').prefetch_related('form_questions__question'))

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        job_status = request.POST.get('job_status', '').strip()
        opt_in = request.POST.get('communications_opt_in') == '1'

        posted = {
            'name': name, 'phone': phone, 'email': email, 'city': city,
            'state': state, 'job_status': job_status,
            'communications_opt_in': opt_in,
        }

        if not name or not phone:
            return render(request, 'intake/form.html', {
                'event': event, 'template': template, 'sections': sections,
                'posted': posted,
                'error': 'Please fill in your name and phone number.',
            })

        participant = _find_existing_participant(phone)
        if participant:
            participant.name = name
            participant.email = email or participant.email
            participant.city = city or participant.city
            participant.state = state or participant.state
            participant.job_status = job_status or participant.job_status
            participant.communications_opt_in = opt_in
            participant.save()
        else:
            participant = Participant.objects.create(
                name=name, phone=phone, email=email, city=city, state=state,
                job_status=job_status, communications_opt_in=opt_in,
            )

        Attendance.objects.get_or_create(
            participant=participant,
            event=event,
            defaults={'source': Attendance.Source.ONLINE_LEAD},
        )

        if version:
            answers = {}
            for section in sections:
                for fq in section.form_questions.all():
                    q = fq.question
                    field_name = f'q_{fq.id}'
                    value = (
                        request.POST.getlist(field_name)
                        if q.type == 'multi_choice'
                        else request.POST.get(field_name, '')
                    )
                    answers[str(fq.id)] = {'label': q.label, 'value': value}
            FormResponse.objects.create(form_version=version, answers=answers)

        return redirect(f"/intake/done/?name={name}&event={event.name}")

    return render(request, 'intake/form.html', {
        'event': event, 'template': template, 'sections': sections, 'posted': {},
    })


def intake_done(request):
    return render(request, 'intake/done.html', {
        'name': request.GET.get('name', ''),
        'event_name': request.GET.get('event', ''),
    })
