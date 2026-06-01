---
description: Vues Django — patterns HTMX, vues génériques, dispatch Celery
paths: ["**/views.py", "**/views/**/*.py"]
priority: medium
tags: [backend, htmx]
---

# Vues Django — StitchFlow

## Pattern upload + Celery

```python
class UploadView(CreateView):
    model = ConversionJob
    form_class = SVGUploadForm

    def form_valid(self, form):
        job = form.save()
        process_conversion_job.delay(str(job.id))  # Toujours str() pour UUID
        return redirect('conversions:detail', pk=job.pk)
```

## Pattern partial HTMX

```python
class JobStatusView(DetailView):
    model = ConversionJob
    template_name = 'conversions/partials/conversion_status.html'

    def get_object(self):
        return get_object_or_404(ConversionJob, pk=self.kwargs['pk'])
```

## Règles

- **Jamais de logique métier dans les vues** — passer par `services/`
- **`get_object_or_404`** pour tous les accès par PK/UUID
- **`FileResponse`** pour servir les fichiers binaires (PES) avec `as_attachment=True`
- **Partials HTMX** : template_name séparé dans `partials/`, retourner `TemplateResponse`
- **Validation** : toujours via le formulaire, jamais directement dans la vue
