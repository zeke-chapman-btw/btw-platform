from django.urls import path

from apps.participants import views

urlpatterns = [
    path('', views.intake_form, name='intake_form'),
    path('done/', views.intake_done, name='intake_done'),
]
