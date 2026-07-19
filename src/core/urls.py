from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('landing/', views.LandingView.as_view(), name='landing'),
    path('healthz/', views.healthz, name='healthz'),
]
