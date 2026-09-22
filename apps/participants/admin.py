from django.contrib import admin

from .models import Attendance, ConsentVersion, Flag, Note, Participant


@admin.register(ConsentVersion)
class ConsentVersionAdmin(admin.ModelAdmin):
    list_display = ('version_label', 'effective_date')


@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'phone', 'public_id', 'communications_opt_in')
    search_fields = ('name', 'email', 'phone')
    readonly_fields = ('public_id',)


class FlagInline(admin.TabularInline):
    model = Flag
    extra = 0


class NoteInline(admin.TabularInline):
    model = Note
    extra = 0
    filter_horizontal = ('released_to',)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('participant', 'event', 'source', 'checked_in_at')
    list_filter = ('source', 'event')
    inlines = [FlagInline, NoteInline]
