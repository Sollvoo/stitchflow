from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.decorators import method_decorator
from django.views import View

import json

from .forms import ChangeEmailForm, EmailLoginForm, MachineProfileForm, ProfileForm, SignUpForm
from .models import MACHINE_PRESETS, UserProfile


class LoginView(View):
    template_name = 'users/login.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect('conversions:upload')
        return render(request, self.template_name, {'form': EmailLoginForm()})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = EmailLoginForm(request.POST, request=request)
        if form.is_valid():
            login(request, form.get_user())
            if request.POST.get('remember_me'):
                request.session.set_expiry(60 * 60 * 24 * 30)  # 30 jours
            else:
                request.session.set_expiry(0)  # expire à la fermeture du navigateur
            next_url = request.GET.get('next', '/conversions/')
            return redirect(next_url)
        return render(request, self.template_name, {'form': form})


class LogoutView(View):
    def post(self, request: HttpRequest) -> HttpResponse:
        logout(request)
        return redirect('/')


class SignUpView(View):
    template_name = 'users/register.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            return redirect('conversions:upload')
        return render(request, self.template_name, {'form': SignUpForm()})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Bienvenue, {user.first_name or user.email} !')
            return redirect('conversions:upload')
        return render(request, self.template_name, {'form': form})


@method_decorator(login_required, name='dispatch')
class ProfileView(View):
    template_name = 'users/profile.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, {'form': ProfileForm(instance=request.user)})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profil mis à jour.')
            return redirect('users:profile')
        return render(request, self.template_name, {'form': form})


@method_decorator(login_required, name='dispatch')
class MachineProfileView(View):
    template_name = 'users/profile_machine.html'

    def _get_profile(self, request: HttpRequest) -> UserProfile:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        return profile

    def _context(self, form: MachineProfileForm) -> dict:
        return {
            'form': form,
            'machine_presets_json': json.dumps(MACHINE_PRESETS),
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        form = MachineProfileForm(instance=self._get_profile(request))
        return render(request, self.template_name, self._context(form))

    def post(self, request: HttpRequest) -> HttpResponse:
        form = MachineProfileForm(request.POST, instance=self._get_profile(request))
        if form.is_valid():
            form.save()
            messages.success(request, 'Machine mise à jour.')
            return redirect('users:profile_machine')
        return render(request, self.template_name, self._context(form))


@method_decorator(login_required, name='dispatch')
class ChangeEmailView(View):
    template_name = 'users/change_email.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name, {'form': ChangeEmailForm(user=request.user)})

    def post(self, request: HttpRequest) -> HttpResponse:
        form = ChangeEmailForm(request.POST, user=request.user)
        if form.is_valid():
            new_email = form.cleaned_data['email']
            request.user.email = new_email
            request.user.username = new_email
            request.user.save(update_fields=['email', 'username'])
            messages.success(request, f'Email mis à jour : {new_email}')
            return redirect('users:profile')
        return render(request, self.template_name, {'form': form})
