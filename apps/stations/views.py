import re

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from apps.participants.models import Participant, Attendance
from apps.formbuilder.models import FormTemplate, FormResponse
from apps.stations.models import Station, StationResult

UUID_RE = re.compile(
    r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
)


def kiosk_scan(request):
    error = None
    if request.method == 'POST':
        raw = request.POST.get('ticket', '').strip()
        match = UUID_RE.search(raw)
        if not match:
            error = "That doesn't look like a valid ticket. Try scanning again, or ask staff for help."
        else:
            try:
                participant = Participant.objects.get(public_id=match.group(0))
            except Participant.DoesNotExist:
                error = "We couldn't find that ticket. Please see staff for help."
            else:
                attendance = (
                    Attendance.objects.filter(participant=participant)
                    .order_by('-checked_in_at')
                    .first()
                )
                if not attendance:
                    error = f"{participant.name}, you're not checked in yet. Please see staff first."
                else:
                    return redirect('kiosk_test', attendance_id=attendance.id)
    return render(request, 'kiosk/scan.html', {'error': error})


def _kiosk_template_version():
    template = (
        FormTemplate.objects.filter(applies_to=FormTemplate.AppliesTo.KIOSK_TEST)
        .first()
    )
    if not template:
        return None, None
    return template, template.current_version()


def kiosk_test(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id)
    template, version = _kiosk_template_version()
    if not template:
        return render(request, 'kiosk/error.html', {
            'message': 'No kiosk test has been set up yet. An admin can add one under '
                       'Form / Question Builder → Form templates (applies to: Kiosk test).',
        })
    if not version:
        return render(request, 'kiosk/error.html', {
            'message': f'“{template.name}” has no questions yet. An admin can add '
                       'sections and questions to it in the admin.',
        })
    sections = version.sections.order_by('order').prefetch_related('form_questions__question')
    return render(request, 'kiosk/test.html', {
        'attendance': attendance,
        'participant': attendance.participant,
        'template': template,
        'version': version,
        'sections': sections,
    })


def kiosk_submit(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id)
    if request.method != 'POST':
        return redirect('kiosk_test', attendance_id=attendance.id)

    template, version = _kiosk_template_version()
    if not template or not version:
        return redirect('kiosk_test', attendance_id=attendance.id)

    answers = {}
    for section in version.sections.all():
        for fq in section.form_questions.all():
            field_name = f'q_{fq.id}'
            question = fq.question
            if question.type == 'multi_choice':
                value = request.POST.getlist(field_name)
            else:
                value = request.POST.get(field_name, '')
            answers[str(fq.id)] = {
                'label': question.label,
                'value': value,
            }

    FormResponse.objects.create(
        form_version=version,
        attendance=attendance,
        answers=answers,
    )

    station, _ = Station.objects.get_or_create(
        kind=Station.Kind.KIOSK_TEST,
        defaults={'name': template.name},
    )
    StationResult.objects.create(
        attendance=attendance,
        station=station,
        answers=answers,
    )

    return redirect('kiosk_done')


def kiosk_done(request):
    return render(request, 'kiosk/done.html')
