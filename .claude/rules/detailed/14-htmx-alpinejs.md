---
description: HTMX + AlpineJS — coordination, polling Celery, patterns courants
paths: ["**/templates/**/*.html", "**/static/js/**"]
priority: medium
tags: [frontend, htmx, alpinejs]
---

# HTMX + AlpineJS — StitchFlow

## HTMX

- **`hx-swap="outerHTML"`** pour les partials qui se remplacent eux-mêmes
- **`hx-boost`** sur les liens si nécessaire pour navigation SPA-like
- **`hx-include`** pour inclure des champs supplémentaires dans une requête
- **CSRF** : le middleware Django injecte le header automatiquement via `django-htmx` ou `{% csrf_token %}`

## Polling Celery via HTMX

Pattern auto-stop:
1. Partial retourne le bloc avec `hx-trigger="every 2s"` si `pending` ou `processing`
2. Quand `completed` ou `failed`, le partial ne contient plus `hx-trigger` → polling s'arrête
3. Jamais de JS custom pour ça — HTMX gère seul

```html
{% if not job.is_terminal %}
  <div hx-get="{% url 'conversions:status' job.id %}"
       hx-trigger="every 2s"
       hx-swap="outerHTML"
       id="status-block">
    <!-- spinner DaisyUI -->
    <span class="loading loading-spinner"></span>
    {{ job.get_status_display }}
  </div>
{% else %}
  <!-- Pas de hx-trigger ici → polling stoppé -->
  <div id="status-block">
    {% if job.status == 'completed' %}
      <a href="{% url 'conversions:download' job.id %}" class="btn btn-success">
        Télécharger le .PES
      </a>
    {% elif job.status == 'failed' %}
      <div class="alert alert-error">{{ job.error_message }}</div>
    {% endif %}
  </div>
{% endif %}
```

## AlpineJS

- Toujours initialiser avec `x-data` au niveau du composant le plus haut
- Pas de `window.Alpine` custom — Alpine est déjà initialisé dans `main.js`
- `x-cloak` pour éviter le flash de contenu non-initialisé
