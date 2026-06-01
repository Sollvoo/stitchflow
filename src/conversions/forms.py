import uuid
from pathlib import Path
from django import forms
from django.core.exceptions import ValidationError
from django.conf import settings

from .models import ConversionJob


class SVGUploadForm(forms.ModelForm):
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

        # Rename to avoid path traversal and collisions
        file.name = f"{uuid.uuid4().hex}.svg"

        return file
