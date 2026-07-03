import csv
import json
import shutil
import tempfile
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.paginator import Paginator
from django.views.generic import CreateView, DetailView, View
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse, HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from PIL import Image

from .models import ConversionJob
from .forms import SVGUploadForm, PNGUploadForm, PDFUploadForm
from .tasks import process_conversion_job, finalize_svg_to_pes


class UnifiedUploadView(View):
    _FORMAT_TO_FORM: dict[str, type] = {
        'svg': SVGUploadForm,
        'png': PNGUploadForm,
        'jpeg': PNGUploadForm,
        'webp': PNGUploadForm,
        'pdf': PDFUploadForm,
    }

    def get(self, request: HttpRequest) -> HttpResponse:
        return render(request, 'conversions/upload_unified.html')

    def post(self, request: HttpRequest) -> HttpResponse:
        file = request.FILES.get('original_file')
        if not file:
            return render(request, 'conversions/upload_unified.html',
                          {'error': 'Aucun fichier sélectionné.'})

        fmt = self._detect_format(file)
        form_class = self._FORMAT_TO_FORM.get(fmt)
        if form_class is None:
            return render(request, 'conversions/upload_unified.html',
                          {'error': 'Format non supporté. Formats acceptés : SVG, PNG, JPEG, WebP, PDF.'})

        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            job = self._save_job(form, request.user if request.user.is_authenticated else None)
            excluded_colors_raw = request.POST.get('excluded_colors', '').strip()
            if excluded_colors_raw:
                job.conversion_metadata = {'excluded_colors': excluded_colors_raw}
                job.save(update_fields=['conversion_metadata'])
            process_conversion_job.delay(str(job.id))
            messages.success(request, 'Fichier reçu. La conversion est en cours.')
            return redirect(reverse('conversions:detail', kwargs={'pk': job.id}))

        return render(request, 'conversions/upload_unified.html', {'form': form})

    @staticmethod
    def _detect_format(file) -> str:
        file.seek(0)
        magic = file.read(12)
        file.seek(0)

        if magic[:4] == b'%PDF':
            return 'pdf'
        if magic[:4] == b'\x89PNG':
            return 'png'
        if magic[:3] == b'\xff\xd8\xff':
            return 'jpeg'
        if magic[:4] == b'RIFF' and magic[8:12] == b'WEBP':
            return 'webp'

        header = magic.decode('utf-8', errors='ignore')
        if '<?xml' in header or '<svg' in header.lower():
            return 'svg'
        file.seek(0)
        header_long = file.read(512).decode('utf-8', errors='ignore')
        file.seek(0)
        if '<svg' in header_long.lower():
            return 'svg'

        ext = Path(file.name).suffix.lower()
        return {
            '.svg': 'svg', '.png': 'png', '.jpg': 'jpeg',
            '.jpeg': 'jpeg', '.webp': 'webp', '.pdf': 'pdf',
        }.get(ext, 'unknown')

    @staticmethod
    def _save_job(form, user=None) -> ConversionJob:
        job: ConversionJob = form.save(commit=False)
        for attr in ('_svg_original_stem', '_raster_original_stem', '_pdf_original_stem'):
            stem = getattr(form, attr, None)
            if stem:
                job.original_filename = stem
                break
        if 'n_colors' in form.cleaned_data:
            job.n_colors = form.cleaned_data['n_colors'] or 6
        if 'remove_background' in form.cleaned_data:
            job.remove_background = form.cleaned_data['remove_background']
        if user is not None:
            job.user = user
        job.save()
        return job


class FormFragmentView(View):
    _FORM_CLASSES: dict[str, type] = {
        'svg': SVGUploadForm,
        'png': PNGUploadForm,
        'jpeg': PNGUploadForm,
        'webp': PNGUploadForm,
        'pdf': PDFUploadForm,
    }

    def get(self, request: HttpRequest, format: str) -> HttpResponse:
        form_class = self._FORM_CLASSES.get(format)
        if not form_class:
            return render(request, 'conversions/partials/form_unknown.html')
        form = form_class()
        tpl = (
            'conversions/partials/form_svg.html'
            if format == 'svg'
            else 'conversions/partials/form_raster.html'
        )
        return render(request, tpl, {'form': form, 'format': format})


class UploadView(CreateView):
    model = ConversionJob
    form_class = SVGUploadForm
    template_name = 'conversions/upload.html'

    def form_valid(self, form):
        response = super().form_valid(form)

        # Stocker le nom de fichier original (avant renommage UUID) pour le téléchargement
        original_stem = getattr(form, '_svg_original_stem', '')
        if original_stem:
            self.object.original_filename = original_stem
            self.object.save(update_fields=['original_filename'])

        process_conversion_job.delay(str(self.object.id))
        messages.success(self.request, 'Fichier reçu. La conversion est en cours.')
        return response

    def get_success_url(self):
        return reverse_lazy('conversions:detail', kwargs={'pk': self.object.id})


class UploadPNGView(CreateView):
    model = ConversionJob
    form_class = PNGUploadForm
    template_name = 'conversions/upload_png.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        # source_format est déjà défini par form.save() (png/jpeg/webp)
        self.object.original_filename = getattr(form, '_raster_original_stem', '')
        self.object.n_colors = form.cleaned_data.get('n_colors') or 6
        self.object.remove_background = form.cleaned_data.get('remove_background', False)
        self.object.save(update_fields=[
            'original_filename', 'n_colors', 'remove_background',
        ])
        process_conversion_job.delay(str(self.object.id))
        messages.success(self.request, 'Image reçue. La conversion est en cours.')
        return response

    def get_success_url(self):
        return reverse_lazy('conversions:detail', kwargs={'pk': self.object.id})


class UploadPDFView(CreateView):
    model = ConversionJob
    form_class = PDFUploadForm
    template_name = 'conversions/upload_pdf.html'

    def form_valid(self, form):
        response = super().form_valid(form)
        # source_format = 'pdf' déjà défini par form.save()
        self.object.original_filename = getattr(form, '_pdf_original_stem', '')
        self.object.n_colors = form.cleaned_data.get('n_colors') or 6
        self.object.remove_background = form.cleaned_data.get('remove_background', False)
        self.object.save(update_fields=[
            'original_filename', 'n_colors', 'remove_background',
        ])
        process_conversion_job.delay(str(self.object.id))
        messages.success(self.request, 'PDF reçu. La conversion est en cours.')
        return response

    def get_success_url(self):
        return reverse_lazy('conversions:detail', kwargs={'pk': self.object.id})


class JobListView(View):
    """Redirige vers le nouveau dashboard historique."""

    def get(self, request: HttpRequest) -> HttpResponse:
        return redirect('conversions:history')


class HistoryView(View):
    """Dashboard historique paginé avec filtres, recherche, score qualité, re-conversion, CSV."""

    def get(self, request: HttpRequest) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect(f'/auth/login/?next=/conversions/history/')

        qs = ConversionJob.objects.filter(user=request.user).order_by('-created_at')

        search_query = request.GET.get('q', '').strip()
        status_filter = request.GET.get('status', '')
        format_filter = request.GET.get('format', '')
        date_filter = request.GET.get('date', '')

        if search_query:
            qs = qs.filter(original_filename__icontains=search_query)

        if status_filter in ('completed', 'failed', 'processing', 'pending'):
            qs = qs.filter(status=status_filter)
        elif status_filter == 'in_progress':
            qs = qs.filter(status__in=[ConversionJob.Status.PENDING, ConversionJob.Status.PROCESSING])

        if format_filter in ('svg', 'png', 'jpeg', 'webp', 'pdf'):
            qs = qs.filter(source_format=format_filter)

        if date_filter == '7d':
            from django.utils import timezone
            from datetime import timedelta
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=7))
        elif date_filter == '30d':
            from django.utils import timezone
            from datetime import timedelta
            qs = qs.filter(created_at__gte=timezone.now() - timedelta(days=30))

        paginator = Paginator(qs, 24)
        page_number = request.GET.get('page', 1)
        page_obj = paginator.get_page(page_number)

        # query_string sans le paramètre page pour les liens de pagination et CSV
        params = request.GET.copy()
        params.pop('page', None)
        query_string = params.urlencode()

        return render(request, 'conversions/history.html', {
            'page_obj': page_obj,
            'search_query': search_query,
            'status_filter': status_filter,
            'format_filter': format_filter,
            'date_filter': date_filter,
            'total_count': qs.count(),
            'query_string': query_string,
        })


class ReconvertView(View):
    """Crée un nouveau job à partir du fichier source d'un job existant."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect('users:login')

        original = get_object_or_404(ConversionJob, pk=pk)
        if original.user and original.user != request.user:
            return redirect('conversions:history')

        new_job = ConversionJob.objects.create(
            source_format=original.source_format,
            original_filename=original.original_filename,
            target_width_mm=original.target_width_mm,
            n_colors=original.n_colors,
            remove_background=original.remove_background,
            user=request.user if request.user.is_authenticated else None,
        )

        if original.original_file:
            old_path = Path(original.original_file.path)
            if old_path.exists():
                new_name = f'conversions/uploads/{new_job.id}{old_path.suffix}'
                new_path = Path(settings.MEDIA_ROOT) / new_name
                new_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(old_path, new_path)
                new_job.original_file = new_name
                new_job.save(update_fields=['original_file'])

        process_conversion_job.delay(str(new_job.id))
        return redirect('conversions:detail', pk=new_job.id)


class ExportCSVView(View):
    """Exporte les conversions de l'utilisateur au format CSV."""

    def get(self, request: HttpRequest) -> HttpResponse:
        if not request.user.is_authenticated:
            return redirect('users:login')

        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = 'attachment; filename="stichflow-conversions.csv"'
        response.write('﻿')

        writer = csv.writer(response)
        writer.writerow(['ID', 'Fichier', 'Format', 'Statut', 'Score qualité', 'Points', 'Fils', 'Largeur (mm)', 'Date'])

        jobs = ConversionJob.objects.filter(user=request.user).order_by('-created_at')
        for job in jobs:
            meta = job.conversion_metadata or {}
            writer.writerow([
                str(job.id),
                job.original_filename or '',
                job.source_format,
                job.get_status_display(),
                meta.get('quality_score', ''),
                meta.get('stitch_count', ''),
                meta.get('thread_count', ''),
                job.target_width_mm or '',
                job.created_at.strftime('%d/%m/%Y %H:%M'),
            ])

        return response


class JobDetailView(DetailView):
    model = ConversionJob
    template_name = 'conversions/detail.html'
    context_object_name = 'job'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.object.status == ConversionJob.Status.AWAITING_SVG_VALIDATION:
            ctx.update(_build_svg_editor_context(self.object))
        return ctx


class JobStatusView(View):
    """Renvoie uniquement le fragment de statut (utilisé par HTMX)."""

    def get(self, request, pk):
        job = get_object_or_404(ConversionJob, pk=pk)
        return HttpResponse(
            self._render_status(request, job),
            content_type='text/html',
        )

    def _render_status(self, request, job):
        from django.template.loader import render_to_string

        if job.status == job.Status.AWAITING_SVG_VALIDATION:
            return _render_svg_editor_response(request, job).content.decode()

        estimated_seconds = None
        if job.status == job.Status.PROCESSING:
            if job.source_format in ('png', 'jpeg', 'webp'):
                n = job.n_colors or 6
                estimated_seconds = 4 + int(n * 1.5) + (4 if job.remove_background else 0)
            elif job.source_format == 'pdf':
                n = job.n_colors or 6
                estimated_seconds = 10 + int(n * 1.5) + (4 if job.remove_background else 0)
            else:
                estimated_seconds = 6

        return render_to_string(
            'conversions/partials/conversion_status.html',
            {'job': job, 'estimated_seconds': estimated_seconds},
            request=request,
        )


def _suggest_width_from_svg(root) -> int:
    """
    Déduit une largeur cible en mm depuis les attributs SVG (viewBox, width, height).
    Retourne une valeur dans [20, 360].
    """
    import re

    def _parse_dim_px(value: str) -> float | None:
        if not value:
            return None
        value = value.strip()
        m = re.match(r'^([\d.]+)(mm|cm|in|pt|px)?$', value)
        if not m:
            return None
        n = float(m.group(1))
        unit = m.group(2) or 'px'
        conversions = {'px': 1.0, 'mm': 2.8346, 'cm': 28.346, 'in': 72.0, 'pt': 1.0}
        return n * conversions.get(unit, 1.0)

    width_mm: float | None = None

    viewbox = root.get('viewBox', '')
    if viewbox:
        parts = viewbox.replace(',', ' ').split()
        if len(parts) == 4:
            try:
                vb_w = float(parts[2])
                width_mm = vb_w * 0.353  # 1px ≈ 0.353mm à 72dpi
            except ValueError:
                pass

    if width_mm is None:
        w_attr = root.get('width', '')
        w_px = _parse_dim_px(w_attr)
        if w_px:
            width_mm = w_px * 0.353

    if width_mm is None:
        return 80

    if width_mm < 50:
        return 80
    if width_mm > 200:
        return 120
    return max(20, min(360, int(width_mm)))


class AnalyzeSVGView(View):
    """Analyse un SVG uploadé et retourne un fragment HTMX avec suggestions et avertissements."""

    def post(self, request: HttpRequest) -> HttpResponse:
        file = request.FILES.get('original_file')
        if not file:
            return HttpResponse('', content_type='text/html')

        try:
            import xml.etree.ElementTree as ET
            from .services.svg_utils import (
                get_svg_dimensions_mm,
                _count_svg_unique_fills,
                _path_bbox_area,
            )

            content = file.read(512 * 1024).decode('utf-8', errors='ignore')
            root = ET.fromstring(content)
            suggested_width = _suggest_width_from_svg(root)

            tmp_svg = Path(tempfile.mktemp(suffix='.svg'))
            tmp_svg.write_text(content, encoding='utf-8')
            try:
                width_mm, height_mm = get_svg_dimensions_mm(tmp_svg)
                n_unique_colors = _count_svg_unique_fills(tmp_svg)
            finally:
                tmp_svg.unlink(missing_ok=True)

            _NS_PATH = '{http://www.w3.org/2000/svg}path'
            _NS_TEXT = '{http://www.w3.org/2000/svg}text'

            vb_parts = root.get('viewBox', '').split()
            if len(vb_parts) == 4 and width_mm and height_mm:
                scale_mm2 = (width_mm / float(vb_parts[2])) * (height_mm / float(vb_parts[3]))
            else:
                scale_mm2 = (25.4 / 96) ** 2

            small_paths_count = sum(
                1 for el in root.iter()
                if el.tag in (_NS_PATH, 'path') and 0 < _path_bbox_area(el.get('d', '')) * scale_mm2 < 2.0
            )
            has_text = any(el.tag in (_NS_TEXT, 'text') for el in root.iter())

            unique_fills = sorted({
                el.get('fill', '') for el in root.iter()
                if el.get('fill', '') not in ('', 'none', 'transparent')
                and not el.get('fill', '').startswith('url(')
            })

            estimated_threads = min(n_unique_colors, 10)
            final_width_mm = suggested_width
            if width_mm and height_mm and width_mm > 0:
                final_height_mm = round(height_mm / width_mm * suggested_width)
            else:
                final_height_mm = suggested_width
            estimated_minutes = max(1, round(
                (final_width_mm * final_height_mm * 0.4 * max(estimated_threads, 1) * 0.7) / 600
            ))

            if n_unique_colors > 10:
                brodability = 'red'
            elif n_unique_colors > 6 or has_text or small_paths_count > 0:
                brodability = 'orange'
            else:
                brodability = 'green'

        except Exception:
            return HttpResponse('', content_type='text/html')

        return render(request, 'conversions/partials/svg_suggestions.html', {
            'very_complex': n_unique_colors > 15,
            'suggested_width': suggested_width,
            'small_paths_count': small_paths_count,
            'has_text': has_text,
            'n_unique_colors': n_unique_colors,
            'unique_fills': unique_fills,
            'color_swatches_json': json.dumps([{'hex': h} for h in unique_fills]),
            'estimated_threads': estimated_threads,
            'final_width_mm': final_width_mm,
            'final_height_mm': final_height_mm,
            'estimated_minutes': estimated_minutes,
            'brodability': brodability,
        })


class AnalyzePNGView(View):
    """Analyse rapide d'un PNG et retourne un fragment HTMX avec suggestions de paramètres."""

    def post(self, request: HttpRequest) -> HttpResponse:
        file = request.FILES.get('original_file')
        if not file:
            return HttpResponse('', content_type='text/html')

        try:
            with Image.open(file) as img:
                has_transparent_bg = False
                if img.mode in ('RGBA', 'LA', 'PA'):
                    alpha = list(img.convert('RGBA').get_flattened_data(3))
                    transparent_pixels = sum(1 for a in alpha if a < 30)
                    has_transparent_bg = transparent_pixels / len(alpha) > 0.10

                rgb = img.convert('RGB')
                img_w, img_h = rgb.width, rgb.height
                total_pixels = img_w * img_h

                # Quantize à 64 couleurs — évite la fusion prématurée des couleurs
                # distinctes lors du MEDIANCUT (était 32 auparavant)
                quantized = rgb.quantize(colors=64, method=Image.Quantize.MEDIANCUT)
                counts = Counter(quantized.get_flattened_data())
                palette = quantized.getpalette()

                # Seuil 0.3% — capture les petites zones colorées
                # ex: les étoiles dans un écusson représentent ~2-3% des pixels
                _MIN_RATIO = 0.003
                near_white_pixels = 0
                significant_colors = 0
                color_swatches: list[dict] = []
                for idx, count in sorted(counts.items(), key=lambda x: -x[1]):
                    r = palette[idx * 3]
                    g = palette[idx * 3 + 1]
                    b = palette[idx * 3 + 2]
                    # Détection fond clair par luminance perceptuelle (capture crème/beige)
                    luminance = 0.299 * r + 0.587 * g + 0.114 * b
                    if luminance > 230:
                        near_white_pixels += count
                    elif count / total_pixels >= _MIN_RATIO:
                        significant_colors += 1
                        color_swatches.append({
                            'hex': f'#{r:02x}{g:02x}{b:02x}',
                            'pct': round(count / total_pixels * 100, 1),
                        })

                has_white_background = (
                    near_white_pixels / total_pixels > 0.55 or has_transparent_bg
                )
                # +1 quand fond détecté : VTracer utilise n_colors pour quantiser TOUTE
                # l'image fond inclus ; sans ce +1, un cluster est "gaspillé" sur le fond
                # et le design perd une couleur après suppression du fond.
                n_colors_recommended = significant_colors + (1 if has_white_background else 0)
                n_colors = max(2, min(n_colors_recommended, 16))
                capped = n_colors_recommended > 16

                # Largeur : DPI EXIF si disponible, sinon heuristique pixel
                dpi_info = img.info.get('dpi') or img.info.get('jfif_density')
                if dpi_info and isinstance(dpi_info, (tuple, list)) and dpi_info[0] > 0:
                    suggested_width = round(img_w / dpi_info[0] * 25.4)
                    suggested_width = max(30, min(360, suggested_width))
                    low_dpi_warning = dpi_info[0] < 150
                    dpi_value: int | None = round(dpi_info[0])
                elif img_w >= 600:
                    suggested_width = 120
                    low_dpi_warning = False
                    dpi_value = None
                elif img_w <= 200:
                    suggested_width = 50
                    low_dpi_warning = False
                    dpi_value = None
                else:
                    suggested_width = 80
                    low_dpi_warning = False
                    dpi_value = None

                # Détection de complexité (Phase 13b) — seuils mesurés sur tests/ :
                # photo bruit : ratio=0.95, top8=0.03 · dégradé : ratio=0.004, top8=0.03
                # logos/écussons : ratio≤0.024, top8≥0.69
                thumb = rgb.copy()
                thumb.thumbnail((256, 256))
                thumb_pixels = thumb.width * thumb.height
                unique_colors = thumb.getcolors(maxcolors=thumb_pixels) or []
                n_unique = len(unique_colors) or thumb_pixels
                top8_share = sum(
                    c for c, _ in sorted(unique_colors, key=lambda x: -x[0])[:8]
                ) / thumb_pixels if unique_colors else 0.0

                is_photo_like = n_unique / thumb_pixels > 0.25
                # Dégradé : aucune couleur ne domine (pas d'aplats) sans être une photo
                has_gradient = not is_photo_like and top8_share < 0.4

            estimated_threads = min(n_colors, significant_colors)
            final_height_mm = round(suggested_width * img_h / img_w) if img_w > 0 else suggested_width
            estimated_minutes = max(1, round(
                (suggested_width * final_height_mm * 0.4 * max(estimated_threads, 1) * 0.7) / 600
            ))

            very_complex = significant_colors > 15

            if is_photo_like or has_gradient or significant_colors > 10:
                brodability = 'red'
            elif significant_colors > 6 or low_dpi_warning:
                brodability = 'orange'
            else:
                brodability = 'green'

        except Exception:
            return HttpResponse('', content_type='text/html')

        return render(request, 'conversions/partials/png_suggestions.html', {
            'is_photo_like': is_photo_like,
            'has_gradient': has_gradient,
            'very_complex': very_complex,
            'n_colors': n_colors,
            'has_white_background': has_white_background,
            'has_bg_bonus': has_white_background,
            'embroidery_colors': significant_colors,
            'total_significant': significant_colors,
            'suggested_width': suggested_width,
            'capped': capped,
            'low_dpi_warning': low_dpi_warning,
            'dpi_value': dpi_value,
            'color_swatches_json': json.dumps(color_swatches),
            'estimated_threads': estimated_threads,
            'final_width_mm': suggested_width,
            'final_height_mm': final_height_mm,
            'estimated_minutes': estimated_minutes,
            'brodability': brodability,
        })


class AnalyzePDFView(View):
    """
    Analyse rapide d'un PDF uploadé : détecte vectoriel vs scanné via pdftocairo,
    extrait les dimensions, retourne un fragment HTMX avec suggestion.
    """

    def post(self, request):
        import tempfile
        from pathlib import Path as _Path
        from .services.pdf_processing import (
            extract_vector_svg_from_pdf,
            is_vector_pdf_svg,
            PDFExtractionError,
        )

        file = request.FILES.get('original_file')
        if not file:
            return HttpResponse('', content_type='text/html')

        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                for chunk in file.chunks():
                    f.write(chunk)
                tmp_pdf = _Path(f.name)

            tmp_svg = tmp_pdf.with_suffix('.svg')
            is_vector = False
            width_mm = height_mm = suggested_width = None

            try:
                extract_vector_svg_from_pdf(tmp_pdf, tmp_svg)
                is_vector = is_vector_pdf_svg(tmp_svg)

                if is_vector and tmp_svg.exists():
                    import xml.etree.ElementTree as ET
                    import re as _re
                    root = ET.parse(tmp_svg).getroot()
                    for attr in ('width', 'height'):
                        val = root.get(attr, '').strip()
                        m = _re.match(r'^([0-9.]+)pt$', val)
                        if m:
                            mm = round(float(m.group(1)) * 0.3527, 1)
                            if attr == 'width':
                                width_mm = mm
                            else:
                                height_mm = mm

                    if width_mm:
                        if width_mm < 20:
                            suggested_width = 40
                        elif width_mm > 360:
                            suggested_width = 200
                        else:
                            suggested_width = int(width_mm)

            except (PDFExtractionError, Exception):
                pass
            finally:
                tmp_pdf.unlink(missing_ok=True)
                if tmp_svg.exists():
                    tmp_svg.unlink(missing_ok=True)

        except Exception:
            return HttpResponse('', content_type='text/html')

        return render(request, 'conversions/partials/pdf_suggestions.html', {
            'is_vector': is_vector,
            'width_mm': width_mm,
            'height_mm': height_mm,
            'suggested_width': suggested_width,
        })


class JobApiStatusView(View):
    """Retourne le statut et les métadonnées de conversion au format JSON (pour tests d'intégration)."""

    def get(self, request: HttpRequest, pk: str) -> JsonResponse:
        job = get_object_or_404(ConversionJob, pk=pk)
        meta = job.conversion_metadata or {}
        return JsonResponse({
            'status': job.status,
            'quality_score': meta.get('quality_score'),
            'thread_count': meta.get('thread_count'),
            'stitch_count': meta.get('stitch_count'),
            'error_message': job.error_message or None,
        })


class JobDownloadView(View):
    """Sert le fichier .PES généré avec le nom original du SVG."""

    def get(self, request, pk):
        job = get_object_or_404(ConversionJob, pk=pk)

        if job.status != ConversionJob.Status.COMPLETED or not job.output_file:
            raise Http404('Fichier non disponible.')

        # Utiliser le nom original du SVG, fallback sur l'ID court
        # Extension dérivée du fichier réel (PES par défaut, DST/JEF/VP3 selon profil machine)
        stem = job.original_filename.strip() or f"stitch_{str(job.id)[:8]}"
        ext = Path(job.output_file.name).suffix or '.pes'
        filename = f"{stem}{ext}"

        response = FileResponse(job.output_file.open('rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class SvgDownloadView(View):
    """Sert le SVG vectorisé (ou le SVG source pour un upload SVG direct)."""

    def get(self, request, pk):
        job = get_object_or_404(ConversionJob, pk=pk)

        file_field = None
        if job.vectorized_svg_file:
            file_field = job.vectorized_svg_file
        elif job.source_format == 'svg' and job.original_file:
            file_field = job.original_file

        if file_field is None:
            raise Http404('SVG non disponible.')

        stem = job.original_filename.strip() or f"stitch_{str(job.id)[:8]}"
        response = FileResponse(
            file_field.open('rb'),
            as_attachment=True,
            content_type='image/svg+xml',
        )
        response['Content-Disposition'] = f'attachment; filename="{stem}.svg"'
        return response


def _build_svg_editor_context(job: ConversionJob) -> dict:
    from .services.svg_utils import get_svg_colors_with_count, get_stitch_types, get_stitch_densities
    from .services.thread_color import get_snap_preview, get_brother_palette

    svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name if job.vectorized_svg_file else None
    svg_colors = get_svg_colors_with_count(svg_path) if svg_path and svg_path.exists() else []
    snap_preview = get_snap_preview([c['hex'] for c in svg_colors])
    snap_by_hex = {s['svg_hex']: s for s in snap_preview}
    stitch_types = get_stitch_types(svg_path) if svg_path and svg_path.exists() else {}
    densities = get_stitch_densities(svg_path) if svg_path and svg_path.exists() else {}

    colors_with_snap = [
        {
            **c,
            'brother_hex': snap_by_hex.get(c['hex'], {}).get('brother_hex', c['hex']),
            'brother_name': snap_by_hex.get(c['hex'], {}).get('brother_name', ''),
            'collision': snap_by_hex.get(c['hex'], {}).get('collision', False),
            'stitch_type': stitch_types.get(c['hex'], 'auto_fill'),
            'density': densities.get(c['hex'], 0.4),
        }
        for c in svg_colors
    ]
    history = job.conversion_metadata.get('svg_history', {'past': [], 'future': []})

    return {
        'svg_colors': svg_colors,
        'colors_with_snap': colors_with_snap,
        'brother_palette': get_brother_palette(),
        'can_undo': bool(history.get('past')),
        'can_redo': bool(history.get('future')),
    }


def _render_svg_editor_response(request: HttpRequest, job: ConversionJob) -> HttpResponse:
    from django.template.loader import render_to_string

    ctx = _build_svg_editor_context(job)
    html = render_to_string(
        'conversions/partials/conversion_status.html',
        {'job': job, **ctx},
        request=request,
    )
    return HttpResponse(html, content_type='text/html')


def _snapshot_before_edit(job: ConversionJob, svg_path: Path) -> None:
    """Sauvegarde un snapshot SVG avant chaque opération d'édition."""
    from .services.svg_utils import save_svg_snapshot
    if not svg_path.exists():
        return
    history = job.conversion_metadata.get('svg_history', {'past': [], 'future': []})
    new_history = save_svg_snapshot(svg_path, Path(settings.MEDIA_ROOT), str(job.id), history)
    job.conversion_metadata['svg_history'] = new_history
    job.save(update_fields=['conversion_metadata'])


class SvgRemoveColorView(View):
    """Supprime tous les éléments d'une couleur donnée du SVG vectorisé."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import remove_excluded_colors_from_svg

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        color = request.POST.get('color', '').strip()
        if not color.startswith('#'):
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        if svg_path.exists():
            _snapshot_before_edit(job, svg_path)
            n = remove_excluded_colors_from_svg(svg_path, [color])
            if n > 0:
                job.save(update_fields=['updated_at'])

        return _render_svg_editor_response(request, job)


class SvgMergeColorsView(View):
    """Fusionne deux couleurs du SVG vectorisé (source → target)."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import merge_svg_colors

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        source = request.POST.get('source', '').strip()
        target = request.POST.get('target', '').strip()
        if not source.startswith('#') or not target.startswith('#') or source == target:
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        if svg_path.exists():
            _snapshot_before_edit(job, svg_path)
            n = merge_svg_colors(svg_path, source, target)
            if n > 0:
                job.save(update_fields=['updated_at'])

        return _render_svg_editor_response(request, job)


class SvgChangeColorView(View):
    """Remplace une couleur SVG par un fil Brother choisi par l'utilisateur."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import change_svg_color
        import re as _re

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        old_color = request.POST.get('old_color', '').strip().lower()
        new_color = request.POST.get('new_color', '').strip().lower()
        _hex_re = _re.compile(r'^#[0-9a-f]{6}$')
        if not _hex_re.match(old_color) or not _hex_re.match(new_color) or old_color == new_color:
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        if svg_path.exists():
            _snapshot_before_edit(job, svg_path)
            n = change_svg_color(svg_path, old_color, new_color)
            if n > 0:
                job.save(update_fields=['updated_at'])

        return _render_svg_editor_response(request, job)


class SvgUndoView(View):
    """Annule la dernière opération d'édition SVG."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import undo_svg

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        history = job.conversion_metadata.get('svg_history', {'past': [], 'future': []})
        success, new_history = undo_svg(svg_path, Path(settings.MEDIA_ROOT), history)
        if success:
            job.conversion_metadata['svg_history'] = new_history
            job.save(update_fields=['conversion_metadata', 'updated_at'])

        return _render_svg_editor_response(request, job)


class SvgRedoView(View):
    """Rétablit la dernière opération annulée."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import redo_svg

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        history = job.conversion_metadata.get('svg_history', {'past': [], 'future': []})
        success, new_history = redo_svg(svg_path, Path(settings.MEDIA_ROOT), history)
        if success:
            job.conversion_metadata['svg_history'] = new_history
            job.save(update_fields=['conversion_metadata', 'updated_at'])

        return _render_svg_editor_response(request, job)


class SvgResetView(View):
    """Restaure le SVG à son état initial (avant toute édition)."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import reset_svg

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        history = job.conversion_metadata.get('svg_history', {'past': [], 'future': []})
        success, new_history = reset_svg(svg_path, Path(settings.MEDIA_ROOT), history)
        if success:
            job.conversion_metadata['svg_history'] = new_history
            job.save(update_fields=['conversion_metadata', 'updated_at'])

        return _render_svg_editor_response(request, job)


class SvgReorderColorsView(View):
    """Réordonne les couches de couleurs du SVG (ordre de broderie)."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import reorder_svg_colors
        import json as _json

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        try:
            ordered = _json.loads(request.POST.get('colors', '[]'))
        except (ValueError, TypeError):
            return HttpResponse(status=400)

        if not isinstance(ordered, list) or not all(isinstance(h, str) for h in ordered):
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        if svg_path.exists():
            _snapshot_before_edit(job, svg_path)
            reorder_svg_colors(svg_path, ordered)
            job.save(update_fields=['updated_at'])

        return _render_svg_editor_response(request, job)


class SvgSetStitchTypeView(View):
    """Définit le type de point (auto_fill / running_stitch) pour une couleur."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import set_stitch_type

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        color = request.POST.get('color', '').strip().lower()
        stitch_type = request.POST.get('stitch_type', '').strip()
        if not color.startswith('#') or stitch_type not in ('auto_fill', 'running_stitch'):
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        if svg_path.exists():
            _snapshot_before_edit(job, svg_path)
            n = set_stitch_type(svg_path, color, stitch_type)
            if n > 0:
                job.save(update_fields=['updated_at'])

        return _render_svg_editor_response(request, job)


class SvgSetDensityView(View):
    """Définit la densité de point (mm entre rangées) pour une couleur."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from .services.svg_utils import set_stitch_density

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION or not job.vectorized_svg_file:
            return HttpResponse(status=400)

        color = request.POST.get('color', '').strip().lower()
        try:
            density = float(request.POST.get('density', ''))
        except (ValueError, TypeError):
            return HttpResponse(status=400)

        if not color.startswith('#') or not (0.1 <= density <= 2.0):
            return HttpResponse(status=400)

        svg_path = Path(settings.MEDIA_ROOT) / job.vectorized_svg_file.name
        if svg_path.exists():
            _snapshot_before_edit(job, svg_path)
            n = set_stitch_density(svg_path, color, density)
            if n > 0:
                job.save(update_fields=['updated_at'])

        return _render_svg_editor_response(request, job)


class SvgValidateView(View):
    """Valide le SVG édité et lance la conversion PES (finalize_svg_to_pes)."""

    def post(self, request: HttpRequest, pk) -> HttpResponse:
        from django.template.loader import render_to_string

        job = get_object_or_404(ConversionJob, pk=pk)
        if job.status != ConversionJob.Status.AWAITING_SVG_VALIDATION:
            return HttpResponse(status=400)

        job.status = ConversionJob.Status.PENDING
        job.save(update_fields=['status', 'updated_at'])
        finalize_svg_to_pes.delay(str(job.id))

        html = render_to_string(
            'conversions/partials/conversion_status.html',
            {'job': job},
            request=request,
        )
        return HttpResponse(html, content_type='text/html')
