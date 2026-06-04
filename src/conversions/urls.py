from django.urls import path
from . import views

app_name = 'conversions'

urlpatterns = [
    path('', views.UploadView.as_view(), name='upload'),
    path('png/', views.UploadPNGView.as_view(), name='upload_png'),
    path('pdf/', views.UploadPDFView.as_view(), name='upload_pdf'),
    path('<uuid:pk>/', views.JobDetailView.as_view(), name='detail'),
    path('<uuid:pk>/status/', views.JobStatusView.as_view(), name='status'),
    path('<uuid:pk>/download/', views.JobDownloadView.as_view(), name='download'),
    path('analyze-png/', views.AnalyzePNGView.as_view(), name='analyze_png'),
    path('analyze-svg/', views.AnalyzeSVGView.as_view(), name='analyze_svg'),
]
