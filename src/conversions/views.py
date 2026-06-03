from collections import Counter

from django.views.generic import CreateView, DetailView, View
from django.contrib import messages
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse_lazy
from PIL import Image

from .models import ConversionJob
from .forms import SVGUploadForm, PNGUploadForm
from .tasks import process_conversion_job


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
        self.object.source_format = 'png'
        self.object.original_filename = getattr(form, '_png_original_stem', '')
        self.object.n_colors = form.cleaned_data.get('n_colors') or 6
        self.object.remove_background = form.cleaned_data.get('remove_background', False)
        self.object.save(update_fields=[
            'source_format', 'original_filename', 'n_colors', 'remove_background',
        ])
        process_conversion_job.delay(str(self.object.id))
        messages.success(self.request, 'Image reçue. La conversion est en cours.')
        return response

    def get_success_url(self):
        return reverse_lazy('conversions:detail', kwargs={'pk': self.object.id})


class JobDetailView(DetailView):
    model = ConversionJob
    template_name = 'conversions/detail.html'
    context_object_name = 'job'


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
        return render_to_string(
            'conversions/partials/conversion_status.html',
            {'job': job},
            request=request,
        )


class AnalyzePNGView(View):
    """Analyse rapide d'un PNG et retourne un fragment HTMX avec suggestions de paramètres."""

    def post(self, request):
        file = request.FILES.get('original_file')
        if not file:
            return HttpResponse('', content_type='text/html')

        try:
            with Image.open(file) as img:
                rgb = img.convert('RGB')
                total_pixels = rgb.width * rgb.height

                unique_colors = rgb.getcolors(maxcolors=total_pixels)

                if unique_colors is not None:
                    # Comptage exact pour logos et aplats
                    white_pixels = sum(
                        count for count, (r, g, b) in unique_colors
                        if r > 230 and g > 230 and b > 230
                    )
                    significant_colors = sum(
                        1 for count, (r, g, b) in unique_colors
                        if not (r > 230 and g > 230 and b > 230)
                        and count / total_pixels > 0.01
                    )
                else:
                    # Fallback MEDIANCUT pour images complexes
                    quantized = rgb.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
                    counts = Counter(quantized.get_flattened_data())
                    palette = quantized.getpalette()
                    white_pixels = 0
                    significant_colors = 0
                    for idx, count in counts.items():
                        r = palette[idx * 3]
                        g = palette[idx * 3 + 1]
                        b = palette[idx * 3 + 2]
                        if r > 230 and g > 230 and b > 230:
                            white_pixels += count
                        elif count / total_pixels > 0.01:
                            significant_colors += 1

                has_white_background = (white_pixels / total_pixels) > 0.70
                n_colors = max(2, min(significant_colors, 12))

                # Heuristique largeur broderie selon résolution pixel
                if rgb.width >= 600:
                    suggested_width = 120
                elif rgb.width <= 200:
                    suggested_width = 50
                else:
                    suggested_width = 80
        except Exception:
            return HttpResponse('', content_type='text/html')

        return render(request, 'conversions/partials/png_suggestions.html', {
            'n_colors': n_colors,
            'has_white_background': has_white_background,
            'total_significant': significant_colors,
            'suggested_width': suggested_width,
        })


class JobDownloadView(View):
    """Sert le fichier .PES généré avec le nom original du SVG."""

    def get(self, request, pk):
        job = get_object_or_404(ConversionJob, pk=pk)

        if job.status != ConversionJob.Status.COMPLETED or not job.output_file:
            raise Http404('Fichier non disponible.')

        # Utiliser le nom original du SVG, fallback sur l'ID court
        stem = job.original_filename.strip() or f"stitch_{str(job.id)[:8]}"
        filename = f"{stem}.pes"

        response = FileResponse(job.output_file.open('rb'), as_attachment=True)
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
