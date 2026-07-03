from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import MACHINE_PRESETS, UserProfile


class EmailLoginForm(forms.Form):
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={'placeholder': 'votre@email.com', 'autocomplete': 'email'}),
    )
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••', 'autocomplete': 'current-password'}),
    )

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self._user = None

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email', '').strip().lower()
        password = cleaned.get('password', '')
        if not email or not password:
            return cleaned

        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            raise ValidationError('Email ou mot de passe incorrect.')

        authenticated = authenticate(self.request, username=user.username, password=password)
        if authenticated is None:
            raise ValidationError('Email ou mot de passe incorrect.')
        if not authenticated.is_active:
            raise ValidationError('Ce compte est désactivé.')

        self._user = authenticated
        return cleaned

    def get_user(self) -> User:
        return self._user


class SignUpForm(forms.Form):
    email = forms.EmailField(
        label='Adresse email',
        widget=forms.EmailInput(attrs={'placeholder': 'votre@email.com', 'autocomplete': 'email'}),
    )
    first_name = forms.CharField(
        label='Prénom',
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Marie', 'autocomplete': 'given-name'}),
    )
    last_name = forms.CharField(
        label='Nom',
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Dupont', 'autocomplete': 'family-name'}),
    )
    password1 = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': '8 caractères minimum', 'autocomplete': 'new-password'}),
    )
    password2 = forms.CharField(
        label='Confirmer le mot de passe',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••', 'autocomplete': 'new-password'}),
    )

    def clean_email(self) -> str:
        email = self.cleaned_data['email'].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError('Un compte existe déjà avec cet email.')
        return email

    def clean_password1(self) -> str:
        password = self.cleaned_data.get('password1', '')
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password1')
        p2 = cleaned.get('password2')
        if p1 and p2 and p1 != p2:
            self.add_error('password2', 'Les mots de passe ne correspondent pas.')
        return cleaned

    def save(self) -> User:
        email = self.cleaned_data['email']
        password = self.cleaned_data['password1']
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=self.cleaned_data.get('first_name', ''),
            last_name=self.cleaned_data.get('last_name', ''),
        )
        return user


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name']
        labels = {'first_name': 'Prénom', 'last_name': 'Nom'}
        widgets = {
            'first_name': forms.TextInput(attrs={'placeholder': 'Marie'}),
            'last_name': forms.TextInput(attrs={'placeholder': 'Dupont'}),
        }


class MachineProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'machine_model',
            'machine_needles',
            'machine_hoop_width_mm',
            'machine_hoop_height_mm',
            'machine_format',
        ]

    def clean(self):
        cleaned = super().clean()
        model = cleaned.get('machine_model')
        preset = MACHINE_PRESETS.get(model)
        if preset:
            # Modèle connu : les caractéristiques viennent du preset,
            # pas des champs (protège contre une manipulation du POST)
            cleaned['machine_needles'] = preset['needles']
            cleaned['machine_hoop_width_mm'] = preset['hoop_width_mm']
            cleaned['machine_hoop_height_mm'] = preset['hoop_height_mm']
            cleaned['machine_format'] = preset['format']
        return cleaned


class ChangeEmailForm(forms.Form):
    email = forms.EmailField(
        label='Nouvel email',
        widget=forms.EmailInput(attrs={'placeholder': 'nouveau@email.com', 'autocomplete': 'email'}),
    )
    password = forms.CharField(
        label='Mot de passe actuel (confirmation)',
        widget=forms.PasswordInput(attrs={'placeholder': '••••••••', 'autocomplete': 'current-password'}),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_email(self) -> str:
        email = self.cleaned_data['email'].strip().lower()
        if self._user and email == self._user.email.lower():
            raise ValidationError("C'est déjà votre email actuel.")
        if User.objects.filter(email__iexact=email).exclude(pk=self._user.pk if self._user else None).exists():
            raise ValidationError('Un compte existe déjà avec cet email.')
        return email

    def clean_password(self) -> str:
        password = self.cleaned_data['password']
        if self._user and not self._user.check_password(password):
            raise ValidationError('Mot de passe incorrect.')
        return password
