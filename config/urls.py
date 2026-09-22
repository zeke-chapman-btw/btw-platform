from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('kiosk/', include('apps.stations.kiosk_urls')),
    path('intake/', include('apps.participants.intake_urls')),
    # Real routes (station API, staff portal, customer portal) get added
    # as each module is built, per the spec's Section 14b build order:
    # intake -> stations -> sync -> staff/events -> customer portal.
]
