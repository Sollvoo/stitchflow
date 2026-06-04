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
            'x-model': 'targetWidth',
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


_RASTER_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp')
_RASTER_ACCEPT = '.png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp'


def _detect_raster_format(magic: bytes, filename: str) -> str:
    """Détecte le format raster depuis les magic bytes. Lève ValidationError si non reconnu."""
    if magic[:4] == b'\x89PNG':
        return 'png'
    if magic[:3] == b'\xff\xd8\xff':
        return 'jpeg'
    if magic[:4] == b'RIFF' and magic[8:12] == b'WEBP':
        return 'webp'
    ext = Path(filename).suffix.lower()
    raise ValidationError(
        f'Format non reconnu. Formats acceptés : PNG, JPEG, WebP (extension : {ext}).'
    )


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
                'accept': _RASTER_ACCEPT,
                'class': 'file-input file-input-bordered w-full',
            }),
        }

    def clean_original_file(self):
        file = self.cleaned_data.get('original_file')
        if not file:
            raise ValidationError('Aucun fichier sélectionné.')

        max_size = 20 * 1024 * 1024
        if file.size > max_size:
            raise ValidationError(
                f'Fichier trop volumineux. Maximum : {max_size // (1024 * 1024)} Mo.'
            )

        ext = Path(file.name).suffix.lower()
        if ext not in _RASTER_EXTENSIONS:
            raise ValidationError(
                f'Format non accepté ({ext}). Formats acceptés : PNG, JPEG, WebP.'
            )

        file.seek(0)
        magic = file.read(12)
        file.seek(0)
        fmt = _detect_raster_format(magic, file.name)

        self._raster_original_stem = Path(file.name).stem[:200]
        self._raster_source_format = fmt
        file.name = f"{uuid.uuid4().hex}{ext}"

        return file

    def save(self, commit: bool = True) -> ConversionJob:
        instance = super().save(commit=False)
        instance.target_width_mm = self.cleaned_data.get('target_width_mm')
        instance.source_format = getattr(self, '_raster_source_format', 'png')
        if commit:
            instance.save()
        return instance


class PDFUploadForm(forms.ModelForm):
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
                'accept': '.pdf,application/pdf',
                'class': 'file-input file-input-bordered w-full',
            }),
        }

    def clean_original_file(self):
        file = self.cleaned_data.get('original_file')
        if not file:
            raise ValidationError('Aucun fichier sélectionné.')

        max_size = 50 * 1024 * 1024  # 50 Mo pour PDF
        if file.size > max_size:
            raise ValidationError(
                f'Fichier trop volumineux. Maximum : {max_size // (1024 * 1024)} Mo.'
            )

        if not file.name.lower().endswith('.pdf'):
            raise ValidationError('Seuls les fichiers .pdf sont acceptés.')

        file.seek(0)
        magic = file.read(4)
        file.seek(0)
        if magic != b'%PDF':
            raise ValidationError('Le fichier ne semble pas être un PDF valide.')

        self._pdf_original_stem = Path(file.name).stem[:200]
        file.name = f"{uuid.uuid4().hex}.pdf"

        return file

    def save(self, commit: bool = True) -> ConversionJob:
        instance = super().save(commit=False)
        instance.target_width_mm = self.cleaned_data.get('target_width_mm')
        instance.source_format = 'pdf'
        if commit:
            instance.save()
        return instance
