import uuid
from pathlib import Path

from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import ConversionJob


class SVGUploadForm(forms.ModelForm):
    target_width_mm = forms.IntegerField(
        required=False,
        min_value=20,
        max_value=360,
        label='Largeur souhaitée (mm)',
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Ex : 100',
        }),
    )

    class Meta:
        model = ConversionJob
        fields = ['original_file']
        widgets = {
            'original_file': forms.FileInput(attrs={
                'accept': '.svg,image/svg+xml',
                'class': 'file-input file-input-bordered w-full',
            }),
        }

    def clean_original_file(self):
        file = self.cleaned_data.get('original_file')
        if not file:
            raise ValidationError('Aucun fichier sélectionné.')

        # Size check
        max_size = getattr(settings, 'SVG_MAX_FILE_SIZE', 10 * 1024 * 1024)
        if file.size > max_size:
            raise ValidationError(
                f'Fichier trop volumineux. Maximum : {max_size // (1024 * 1024)} Mo.'
            )

        # Extension check
        name = file.name.lower()
        if not name.endswith('.svg'):
            raise ValidationError('Seuls les fichiers .svg sont acceptés.')

        # Basic SVG content check (first bytes)
        file.seek(0)
        header = file.read(512).decode('utf-8', errors='ignore').strip()
        file.seek(0)
        if '<svg' not in header.lower() and '<?xml' not in header.lower():
            raise ValidationError('Le fichier ne semble pas être un SVG valide.')

        # Conserver le nom original sanitisé avant le renommage UUID
        self._svg_original_stem = Path(file.name).stem[:200]

        # Rename to avoid path traversal and collisions
        file.name = f"{uuid.uuid4().hex}.svg"

        return file

    def save(self, commit: bool = True) -> ConversionJob:
        instance = super().save(commit=False)
        instance.target_width_mm = self.cleaned_data.get('target_width_mm')
        if commit:
            instance.save()
        return instance


class PNGUploadForm(forms.ModelForm):
    n_colors = forms.IntegerField(
        required=False,
        min_value=2,
        max_value=16,
        initial=6,
        label='Nombre de couleurs',
        widget=forms.NumberInput(attrs={
            'class': 'range range-primary range-sm',
            'min': '2',
            'max': '16',
            'step': '1',
            'x-model': 'nColors',
        }),
    )
    remove_background = forms.BooleanField(
        required=False,
        label='Supprimer le fond automatiquement (IA)',
        widget=forms.CheckboxInput(attrs={
            'class': 'checkbox checkbox-primary',
            'x-model': 'removeBg',
        }),
    )
    target_width_mm = forms.IntegerField(
        required=False,
        min_value=20,
        max_value=360,
        label='Largeur souhaitée (mm)',
        widget=forms.NumberInput(attrs={
            'class': 'input input-bordered w-full',
            'placeholder': 'Ex : 80',
            'x-model': 'targetWidth',
        }),
    )

    class Meta:
        model = ConversionJob
        fields = ['original_file']
        widgets = {
            'original_file': forms.FileInput(attrs={
                'accept': '.png,image/png',
                'class': 'file-input file-input-bordered w-full',
            }),
        }

    def clean_original_file(self):
        file = self.cleaned_data.get('original_file')
        if not file:
            raise ValidationError('Aucun fichier sélectionné.')

        max_size = 20 * 1024 * 1024  # 20 Mo pour PNG (plus lourd que SVG)
        if file.size > max_size:
            raise ValidationError(
                f'Fichier trop volumineux. Maximum : {max_size // (1024 * 1024)} Mo.'
            )

        if not file.name.lower().endswith('.png'):
            raise ValidationError('Seuls les fichiers .png sont acceptés.')

        file.seek(0)
        magic = file.read(4)
        file.seek(0)
        if magic != b'\x89PNG':
            raise ValidationError('Le fichier ne semble pas être un PNG valide.')

        self._png_original_stem = Path(file.name).stem[:200]
        file.name = f"{uuid.uuid4().hex}.png"

        return file

    def save(self, commit: bool = True) -> ConversionJob:
        instance = super().save(commit=False)
        instance.target_width_mm = self.cleaned_data.get('target_width_mm')
        if commit:
            instance.save()
        return instance
