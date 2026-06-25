from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'conversions'

urlpatterns = [
    path('', views.UnifiedUploadView.as_view(), name='upload'),
    path('history/', views.HistoryView.as_view(), name='history'),
    path('history/export-csv/', views.ExportCSVView.as_view(), name='export_csv'),
    path('mes-conversions/', RedirectView.as_view(pattern_name='conversions:history'), name='job_list'),
    path('form/<str:format>/', views.FormFragmentView.as_view(), name='form_fragment'),
    path('svg/', RedirectView.as_view(pattern_name='conversions:upload'), name='upload_svg'),
    path('png/', RedirectView.as_view(pattern_name='conversions:upload'), name='upload_png'),
    path('pdf/', RedirectView.as_view(pattern_name='conversions:upload'), name='upload_pdf'),
    path('<uuid:pk>/', views.JobDetailView.as_view(), name='detail'),
    path('<uuid:pk>/status/', views.JobStatusView.as_view(), name='status'),
    path('<uuid:pk>/api/status/', views.JobApiStatusView.as_view(), name='api_status'),
    path('<uuid:pk>/download/', views.JobDownloadView.as_view(), name='download'),
    path('<uuid:pk>/reconvert/', views.ReconvertView.as_view(), name='reconvert'),
    path('<uuid:pk>/svg/remove-color/', views.SvgRemoveColorView.as_view(), name='svg_remove_color'),
    path('<uuid:pk>/svg/merge-colors/', views.SvgMergeColorsView.as_view(), name='svg_merge_colors'),
    path('<uuid:pk>/svg/change-color/', views.SvgChangeColorView.as_view(), name='svg_change_color'),
    path('<uuid:pk>/svg/validate/', views.SvgValidateView.as_view(), name='svg_validate'),
    path('analyze-png/', views.AnalyzePNGView.as_view(), name='analyze_png'),
    path('analyze-svg/', views.AnalyzeSVGView.as_view(), name='analyze_svg'),
    path('analyze-pdf/', views.AnalyzePDFView.as_view(), name='analyze_pdf'),
]
