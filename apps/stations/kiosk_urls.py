from django.urls import path

from apps.stations import views

urlpatterns = [
    path('', views.kiosk_scan, name='kiosk_scan'),
    path('test/<int:attendance_id>/', views.kiosk_test, name='kiosk_test'),
    path('test/<int:attendance_id>/submit/', views.kiosk_submit, name='kiosk_submit'),
    path('done/', views.kiosk_done, name='kiosk_done'),
]
