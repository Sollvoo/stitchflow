---
description: HTMX + AlpineJS - coordination, polling Celery, patterns courants
paths: ["**/templates/**/*.html", "**/static/js/**"]
priority: medium
tags: [frontend, htmx, alpinejs]
---

# HTMX + AlpineJS - StitchFlow

## HTMX

- **`hx-swap="outerHTML"`** pour les partials qui se remplacent eux-memes
- **`hx-boost`** si necessaire pour une navigation plus fluide
- **`hx-include`** pour inclure des champs supplementaires dans une requete
- **CSRF** : toujours preservé via Django et les formulaires `{% csrf_token %}`

## Polling Celery via HTMX

Pattern auto-stop :
1. Le partial retourne le bloc avec `hx-trigger="every 2s"` si `pending` ou `processing`
2. Quand `completed` ou `failed`, le partial ne contient plus `hx-trigger`
3. Eviter le JS custom si HTMX suffit

```html
{% if not job.is_terminal %}
  <div hx-get="{% url 'conversions:status' job.id %}"
       hx-trigger="every 2s"
       hx-swap="outerHTML"
       id="status-block">
    <span class="loading loading-spinner"></span>
    {{ job.get_status_display }}
  </div>
{% else %}
  <div id="status-block">
    {% if job.status == 'completed' %}
      <a href="{% url 'conversions:download' job.id %}" class="btn btn-success">
        Telecharger le .PES
      </a>
    {% elif job.status == 'failed' %}
      <div class="alert alert-error">{{ job.error_message }}</div>
    {% endif %}
  </div>
{% endif %}
```

## AlpineJS

- Initialiser avec `x-data` au niveau du composant le plus haut possible
- Pas de bootstrap custom inutile si `main.js` initialise deja Alpine
- Utiliser `x-cloak` pour eviter le flash de contenu non initialise
