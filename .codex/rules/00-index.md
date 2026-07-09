---
description: Index des regles Codex StitchFlow - navigation rapide et chargement conditionnel
---

# Index Regles Codex - StitchFlow

Ce fichier sert de point d'entree pour les regles locales Codex du projet.

## Comment utiliser

- Charger manuellement une regle : `.codex/rules/detailed/XX-topic.md`
- Utiliser cet index pour trouver rapidement la regle adaptee a la surface touchee
- Si une regle manque cote Codex, se rabattre sur l'equivalent dans `.claude/`

## Index complet

### Architecture et projet

| # | Fichier | Description | S'applique a |
|---|---|---|---|
| 13 | code-style.md | Ruff, Black, conventions Python | `**/*.py` |
| 07 | security.md | CSRF, secrets, validation fichiers, OWASP | `**/views.py`, `**/settings.py` |

### Backend Django

| # | Fichier | Description | S'applique a |
|---|---|---|---|
| 01 | models.md | Modeles Django, UUID, FileField, statuts | `**/models.py` |
| 02 | views.md | Patterns HTMX, vues generiques, dispatch Celery | `**/views.py` |

### Frontend

| # | Fichier | Description | S'applique a |
|---|---|---|---|
| 05 | templates.md | Partials HTMX, AlpineJS, DaisyUI | `**/templates/**/*.html` |
| 14 | htmx-alpinejs.md | Coordination HTMX/Alpine, polling Celery | `**/templates/**/*.html` |
| 15 | design-system.md | Theme StitchFlow, tokens Tailwind, usage DaisyUI | `src/frontend/assets/styles.css`, `**/templates/**/*.html` |

## Notes

- L'index Claude mentionne `03-forms.md`, mais ce fichier n'existe pas actuellement dans `.claude/rules/detailed/`.
- Le miroir Codex reproduit volontairement uniquement les ressources reelles presentes dans le depot.
