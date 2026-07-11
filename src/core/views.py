from django import forms
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views import View
from django.views.generic import TemplateView

from .models import WaitlistEmail


def ratelimited_view(request, exception=None):
    """Retourne 429 quand le rate limit est atteint (utilisé par RatelimitMiddleware)."""
    return HttpResponse("Trop de requêtes. Veuillez réessayer dans quelques instants.", status=429)


class HomeView(TemplateView):
    template_name = 'home.html'


class WaitlistForm(forms.Form):
    email = forms.EmailField()


class LandingView(View):
    template_name = 'landing.html'

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, self.template_name)

    def post(self, request: HttpRequest) -> HttpResponse:
        form = WaitlistForm(request.POST)
        if not form.is_valid():
            return render(request, self.template_name, {
                'error': 'Adresse email invalide.',
                'email_value': request.POST.get('email', ''),
            })

        email = form.cleaned_data['email'].strip().lower()
        # get_or_create : pas d'IntegrityError sur doublon, et même message de
        # succès qu'un nouvel inscrit (pas de fuite d'info sur les emails déjà inscrits)
        WaitlistEmail.objects.get_or_create(email=email)
        return render(request, self.template_name, {'success': True})
