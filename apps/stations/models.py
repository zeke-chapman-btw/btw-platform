"""
Stations: the kiosk test, the hunting game (both rebuilt in-house and
run offline from the trailer server), and the heavy equipment
simulators (NOT rebuilt - integrated via a small "station agent" that
watches a results CSV, per spec Section 5).

One shared model for all station results, rather than one table per
station, so adding a station later doesn't require new tables - it's
the "station API" idea from the spec: one shared pattern (identify
participant, post result) for every station.
"""

from django.db import models


class Station(models.Model):
    class Kind(models.TextChoices):
        KIOSK_TEST = 'kiosk_test', 'Kiosk test'
        HUNTING_GAME = 'hunting_game', 'Hunting game'
        SIMULATOR = 'simulator', 'Heavy equipment simulator'

    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=20, choices=Kind.choices)
    is_rebuilt_in_house = models.BooleanField(
        default=False,
        help_text='True for the kiosk test and hunting game; false for simulators, '
                   'which stay third-party and are integrated via a station agent.',
    )

    def __str__(self):
        return self.name


class StationResult(models.Model):
    """
    One row per attempt/run at a station, whichever station it is.
    For simulators, `raw_source_row` keeps the original CSV row for
    traceability back to the vendor software, once the simulator's
    actual CSV format is known (spec Section 12 - still an open item
    pending physical access to the trailer).
    """

    attendance = models.ForeignKey(
        'participants.Attendance', on_delete=models.CASCADE, related_name='station_results'
    )
    station = models.ForeignKey(Station, on_delete=models.PROTECT, related_name='results')

    score = models.FloatField(null=True, blank=True)
    passed = models.BooleanField(null=True, blank=True)
    answers = models.JSONField(default=dict, blank=True, help_text='Kiosk test answers, if applicable.')

    raw_source_row = models.JSONField(
        null=True, blank=True,
        help_text='For simulator results ingested from the CSV station agent - the original row, unparsed fields kept for audit.',
    )

    recorded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.attendance} — {self.station.name} — {self.score}'
