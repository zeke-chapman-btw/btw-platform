from django.contrib import admin

from .models import EventTypePreset, FormQuestion, FormResponse, FormSection, FormTemplate, FormVersion, Question


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('label', 'type', 'is_required')
    search_fields = ('label',)


class FormQuestionInline(admin.TabularInline):
    model = FormQuestion
    extra = 0
    autocomplete_fields = ('question',)


class FormSectionInline(admin.TabularInline):
    model = FormSection
    extra = 0
    show_change_link = True


@admin.register(FormTemplate)
class FormTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'applies_to')
    actions = ['create_new_version']

    @admin.action(description='Create a new editable version')
    def create_new_version(self, request, queryset):
        for template in queryset:
            template.new_version()


@admin.register(FormVersion)
class FormVersionAdmin(admin.ModelAdmin):
    list_display = ('template', 'version_number', 'created_at')
    inlines = [FormSectionInline]


@admin.register(FormSection)
class FormSectionAdmin(admin.ModelAdmin):
    list_display = ('version', 'title', 'order')
    inlines = [FormQuestionInline]


@admin.register(EventTypePreset)
class EventTypePresetAdmin(admin.ModelAdmin):
    list_display = ('event_type', 'form_template')


admin.site.register(FormResponse)
