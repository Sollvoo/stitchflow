---
description: Index regles StitchFlow — navigation rapide et chargement conditionnel
---

# Index Règles Claude Code — StitchFlow

Seul ce fichier est chargé automatiquement. Les autres règles se chargent selon les fichiers modifiés.

## Comment utiliser

- Charger manuellement une règle : `@.claude/rules/detailed/XX-topic.md`
- Auto-chargement : une règle est chargée quand son `paths` match les fichiers touchés.

## Index complet

### Architecture et projet

| # | Fichier | Description | S'applique à |
|---|---|---|---|
| 13 | code-style.md | Ruff, Black, conventions Python | `**/*.py` |
| 07 | security.md | CSRF, secrets, validation fichiers, OWASP | `**/views.py`, `**/settings.py` |

### Backend Django

| # | Fichier | Description | S'applique à |
|---|---|---|---|
| 01 | models.md | Modèles Django, UUID, FileField, statuts | `**/models.py` |
| 02 | views.md | Patterns HTMX, vues génériques, Celery dispatch | `**/views.py` |
| 03 | forms.md | Validation SVG, ModelForm, clean() | `**/forms.py` |

### Frontend

| # | Fichier | Description | S'applique à |
|---|---|---|---|
| 05 | templates.md | Partials HTMX, AlpineJS, DaisyUI | `**/templates/**/*.html` |
| 14 | htmx-alpinejs.md | Coordination HTMX/Alpine, polling Celery | `**/templates/**/*.html` |
