from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    path('register/', views.SignUpView.as_view(), name='register'),
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/machine/', views.MachineProfileView.as_view(), name='profile_machine'),
    path('change-email/', views.ChangeEmailView.as_view(), name='change_email'),

    # Mot de passe oublié (envoi email)
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='users/password_reset.html',
        email_template_name='users/emails/password_reset_body.html',
        subject_template_name='users/emails/password_reset_subject.txt',
        success_url='/auth/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url='/auth/password-reset/complete/',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html',
    ), name='password_reset_complete'),

    # Changement de mot de passe (utilisateur connecté)
    path('password-change/', auth_views.PasswordChangeView.as_view(
        template_name='users/password_change.html',
        success_url='/auth/password-change/done/',
    ), name='password_change'),
    path('password-change/done/', auth_views.PasswordChangeDoneView.as_view(
        template_name='users/password_change_done.html',
    ), name='password_change_done'),
]
