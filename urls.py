from django.contrib import admin
from django.urls import path

urlpatterns = [
    path('admin/', admin.site.urls),
    # Real routes (intake form, station API, staff portal, customer portal)
    # get added as each module is built, per the spec's Section 14b build
    # order: intake -> stations -> sync -> staff/events -> customer portal.
]
