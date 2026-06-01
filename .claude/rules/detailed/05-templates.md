---
description: Templates Django — partials HTMX, AlpineJS, DaisyUI, base layout
paths: ["**/templates/**/*.html"]
priority: medium
tags: [frontend, htmx, alpinejs]
---

# Templates — StitchFlow

## Conventions de base

```html
{% extends "base.html" %}
{% block content %}
<!-- contenu de la page -->
{% endblock content %}
```

## Pattern HTMX polling (statut Celery)

Le partial `conversion_status.html` inclut son propre `hx-trigger` **uniquement si le job n'est pas terminal**.
Quand terminal, le HTML retourné ne contient pas de `hx-trigger` → le polling s'arrête automatiquement.

```html
{% if not job.is_terminal %}
<div hx-get="{% url 'conversions:status' job.id %}"
     hx-trigger="every 2s"
     hx-swap="outerHTML">
{% endif %}
```

## DaisyUI

- Utiliser les composants DaisyUI (card, badge, btn, loading, alert)
- Classes Tailwind directement dans les templates — pas de CSS custom sauf dans `styles.css`
- Thème par défaut, pas de configuration custom nécessaire pour le MVP

## AlpineJS

```html
<!-- Pattern filename display sur input file -->
<div x-data="{ filename: '' }">
  <input type="file"
         @change="filename = $event.target.files[0]?.name || ''">
  <span x-text="filename || 'Aucun fichier'"></span>
</div>
```

## Assets Vite

```html
{% load django_vite %}
{% vite_asset 'main.js' %}  {# dans base.html uniquement #}
```
