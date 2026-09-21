from django.contrib import admin

from .models import Station, StationResult


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'kind', 'is_rebuilt_in_house')


@admin.register(StationResult)
class StationResultAdmin(admin.ModelAdmin):
    list_display = ('attendance', 'station', 'score', 'passed', 'recorded_at')
    list_filter = ('station',)
