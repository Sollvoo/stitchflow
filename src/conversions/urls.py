from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'conversions'

urlpatterns = [
    path('', views.UnifiedUploadView.as_view(), name='upload'),
    path('form/<str:format>/', views.FormFragmentView.as_view(), name='form_fragment'),
    path('svg/', RedirectView.as_view(pattern_name='conversions:upload'), name='upload_svg'),
    path('png/', RedirectView.as_view(pattern_name='conversions:upload'), name='upload_png'),
    path('pdf/', RedirectView.as_view(pattern_name='conversions:upload'), name='upload_pdf'),
    path('<uuid:pk>/', views.JobDetailView.as_view(), name='detail'),
    path('<uuid:pk>/status/', views.JobStatusView.as_view(), name='status'),
    path('<uuid:pk>/api/status/', views.JobApiStatusView.as_view(), name='api_status'),
    path('<uuid:pk>/download/', views.JobDownloadView.as_view(), name='download'),
    path('analyze-png/', views.AnalyzePNGView.as_view(), name='analyze_png'),
    path('analyze-svg/', views.AnalyzeSVGView.as_view(), name='analyze_svg'),
    path('analyze-pdf/', views.AnalyzePDFView.as_view(), name='analyze_pdf'),
]
