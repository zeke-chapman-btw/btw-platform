"""
Forms and questions as configuration data, not hardcoded pages (spec
Section 14a). This is what lets BTW staff add/remove intake or kiosk-
test questions themselves, with no developer and no deploy - the whole
point being that this module is edited through the Django admin (or a
future custom admin screen) by an admin/manager user, and changes take
effect immediately.

Used by both the participant intake form and the kiosk test, since
they're the same underlying problem: an ordered set of question groups
that needs to be easy to edit and that varies by context (event type,
for intake).

Versioning matters here specifically: a form changes over time, but
people already answered it under an older version. Every submission
should record which FormVersion it was answered against, so a later
edit to a question's wording or options never makes historical answers
ambiguous.
"""

from django.db import models


class Question(models.Model):
    class Type(models.TextChoices):
        SHORT_TEXT = 'short_text', 'Short text'
        LONG_TEXT = 'long_text', 'Long text'
        SINGLE_CHOICE = 'single_choice', 'Single choice'
        MULTI_CHOICE = 'multi_choice', 'Multi-select / checklist'
        YES_NO = 'yes_no', 'Yes / no'
        DATE = 'date', 'Date'
        NUMERIC = 'numeric', 'Numeric'
        LICENSE_LIST = 'license_list', 'License / certification list'
        FILE_PHOTO = 'file_photo', 'File / photo'

    label = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=Type.choices)
    options = models.JSONField(default=list, blank=True, help_text='For choice types.')
    is_required = models.BooleanField(default=False)

    def __str__(self):
        return self.label


class FormTemplate(models.Model):
    """
    A named, ordered set of question groups - "Standard Intake," "CDL
    Job Fair Intake," "Excavator Kiosk Test." Built and edited by an
    admin with no code involved.
    """

    class AppliesTo(models.TextChoices):
        INTAKE = 'intake', 'Participant intake'
        KIOSK_TEST = 'kiosk_test', 'Kiosk test'

    name = models.CharField(max_length=120)
    applies_to = models.CharField(max_length=20, choices=AppliesTo.choices)

    def __str__(self):
        return self.name

    def current_version(self):
        return self.versions.order_by('-version_number').first()

    def new_version(self):
        """
        Create a new, editable version by cloning the current one's
        sections/questions. Old submissions keep pointing at the old
        FormVersion, so their answers stay interpretable even after
        this edit.
        """
        latest = self.current_version()
        next_number = (latest.version_number + 1) if latest else 1
        new_version = FormVersion.objects.create(template=self, version_number=next_number)
        if latest:
            for section in latest.sections.all():
                new_section = FormSection.objects.create(
                    version=new_version, title=section.title, order=section.order
                )
                for fq in section.form_questions.all():
                    FormQuestion.objects.create(
                        section=new_section, question=fq.question, order=fq.order
                    )
        return new_version


class FormVersion(models.Model):
    """One immutable snapshot of a template's questions. Never edit a
    version after a submission references it - create a new version
    instead (see FormTemplate.new_version)."""

    template = models.ForeignKey(FormTemplate, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('template', 'version_number')]
        ordering = ['-version_number']

    def __str__(self):
        return f'{self.template.name} v{self.version_number}'


class FormSection(models.Model):
    version = models.ForeignKey(FormVersion, on_delete=models.CASCADE, related_name='sections')
    title = models.CharField(max_length=255, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


class FormQuestion(models.Model):
    """Join of a Question into a specific section/version, with its
    own ordering (a question can be reused across many forms)."""

    section = models.ForeignKey(FormSection, on_delete=models.CASCADE, related_name='form_questions')
    question = models.ForeignKey(Question, on_delete=models.PROTECT, related_name='+')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']


class EventTypePreset(models.Model):
    """
    Maps an Event.EventType to a default FormTemplate (spec Section
    14a). A new job-fair event starts with the job-fair intake
    automatically; an admin can still add/remove questions for that one
    event, or edit the preset to change the default for future events
    of that type.
    """

    event_type = models.CharField(max_length=30, unique=True, help_text='Matches apps.events.models.Event.EventType.')
    form_template = models.ForeignKey(FormTemplate, on_delete=models.PROTECT, related_name='event_type_presets')

    def __str__(self):
        return f'{self.event_type} -> {self.form_template.name}'


class FormResponse(models.Model):
    """
    A submitted response. Records exactly which FormVersion it was
    answered against - the piece that keeps old answers interpretable
    after the form changes later.
    """

    form_version = models.ForeignKey(FormVersion, on_delete=models.PROTECT, related_name='responses')
    attendance = models.ForeignKey(
        'participants.Attendance', null=True, blank=True, on_delete=models.CASCADE, related_name='form_responses'
    )
    answers = models.JSONField(default=dict, help_text='{form_question_id: answer}')
    submitted_at = models.DateTimeField(auto_now_add=True)
