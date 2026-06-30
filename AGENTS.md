# StitchFlow — Guide pour agents IA et développeurs

## Description du projet

StitchFlow est une application web Django permettant de convertir des fichiers SVG, PNG, JPEG, WebP et PDF en fichiers de broderie `.PES` via Ink/Stitch CLI.

**État actuel (juin 2025) :** Phases 1–6 terminées. Pipeline complet opérationnel. Phase 7 (assistant pré-conversion) et Phase 8 (éditeur SVG) à démarrer.

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Backend | Python 3.14, Django 6 |
| Tâches async | Celery 5 + Redis |
| Frontend | Vite 6, TailwindCSS 4, DaisyUI 5 |
| Interactivité | HTMX 2, AlpineJS 3 |
| Base de données | SQLite (MVP) → PostgreSQL |
| Conversion | Ink/Stitch CLI |

## Environnement virtuel Python

**TOUJOURS utiliser le venv du projet :**

```bash
source /Users/hugobonnet/Developer/StitchFlow/.venv/bin/activate
```

Ne jamais utiliser le Python système ou créer un nouveau venv pour ce projet. Le venv est à `.venv/` à la racine.

## Lancer le projet

### Prérequis

1. Activer le venv : `source .venv/bin/activate`
2. Copier `.env.example` en `.env` et remplir les valeurs
3. Redis doit tourner (voir ci-dessous)
4. Ink/Stitch doit être installé (voir ci-dessous)

### Serveur Django

```bash
source .venv/bin/activate
python src/manage.py runserver 8001
```

Accessible sur : http://localhost:8001
(Port 8001 utilisé car 8000 est réservé à FlowDo)

### Vite (assets frontend) — depuis src/frontend/

```bash
cd src/frontend
npm run dev
```

Accessible sur : http://localhost:5173 (assets servis en dev)

Pour la production :
```bash
cd src/frontend
npm run build
```

### Worker Celery

```bash
source .venv/bin/activate
cd src && celery -A stitchflow worker -l info
```

Ou depuis la racine avec PYTHONPATH :
```bash
source .venv/bin/activate
PYTHONPATH=src celery -A stitchflow worker -l info
```

### Redis

Vérifier si Redis tourne :
```bash
redis-cli ping
# Doit retourner : PONG
```

Installer via Homebrew si nécessaire :
```bash
brew install redis
brew services start redis
```

Attention : Si vous avez déjà Redis dans un autre projet (ex : `~/Documents/FlowDo`), vérifiez qu'une instance tourne avant d'en démarrer une nouvelle.

### Migrations

```bash
source .venv/bin/activate
python src/manage.py makemigrations
python src/manage.py migrate
```

### Superuser admin

```bash
source .venv/bin/activate
python src/manage.py createsuperuser
```

---

## Installation de VTracer CLI (binaire vendor/)

Requis pour la vectorisation PNG/JPEG/WebP/PDF → SVG (vectoriseur primaire, ARM64-safe) :

```bash
mkdir -p vendor
curl -L -o /tmp/vtracer.tar.gz \
  https://github.com/visioncortex/vtracer/releases/download/0.6.4/vtracer-aarch64-apple-darwin.tar.gz
tar -xzf /tmp/vtracer.tar.gz -C vendor/
rm /tmp/vtracer.tar.gz
chmod +x vendor/vtracer
```

Vérification : `vendor/vtracer --version` doit afficher `visioncortex VTracer 0.6.4`.

Le binaire est ignoré par git (`.gitignore`). À re-télécharger après un clone.

**Fallback automatique** : si `vendor/vtracer` absent, le pipeline tente VTracer Python, puis potrace, puis Inkscape.

---

## Installation de potrace

Requis pour la vectorisation PNG → SVG avec fidélité couleurs (fallback si VTracer absent) :

```bash
brew install potrace
```

Vérification : `potrace --version` doit afficher `potrace 1.16` ou supérieur.

Le pipeline utilise potrace comme étape intermédiaire (VTracer → **potrace** → Inkscape fallback).
Chaque couleur détectée par MEDIANCUT est tracée séparément → les paths SVG portent la vraie couleur.

---

## Installation d'Ink/Stitch

### Présentation

Ink/Stitch est une extension Inkscape qui peut aussi être appelée en ligne de commande :
```bash
./inkstitch --extension=zip --format-pes=True input.svg > output.zip
```

Documentation officielle : https://inkstitch.org/docs/command-line

### Étapes d'installation sur macOS

1. **Inkscape** est déjà installé via `brew install --cask inkscape` ✅

2. **Installer Ink/Stitch** :
   - Télécharger la dernière release depuis https://inkstitch.org (v3.2.2 en juin 2025)
   - Version macOS ARM disponible
   - Suivre les instructions d'installation du site officiel
   - L'extension s'installe dans `~/.config/inkscape/extensions/`

3. **Configurer le chemin** dans `.env` :
   ```
   INKSTITCH_EXECUTABLE=/chemin/vers/inkstitch
   ```
   L'exécutable se trouve typiquement dans :
   `~/.config/inkscape/extensions/inkstitch/inkstitch`

4. **Tester** :
   ```bash
   ~/.config/inkscape/extensions/inkstitch/inkstitch --help
   ```

### Si Ink/Stitch n'est pas installé

La conversion échouera avec `FileNotFoundError`. Le job passera en statut `failed` avec le message d'erreur. Le reste de l'application (upload, affichage des jobs, HTMX) fonctionne sans Ink/Stitch.

---

## Machine cible

**Brother entrepreneur pro X PR1050X** — machine de broderie professionnelle 10 aiguilles.

| Contrainte | Valeur |
|---|---|
| Aiguilles | 10 → max 10 fils distincts par design (idéal : ≤7) |
| Zone de broderie max | 360×200mm (grand cercle), 200×200mm (standard) |
| Format natif | PES (v1 universel recommandé, v6 supporté) |
| Points max recommandés | <500k par fichier |
| Vitesse estimée | ~600 points/min |

Tout design converti doit être compatible avec ces limites. Une conversion à 115 fils est physiquement impossible sur cette machine.

---

## Architecture du projet

```
StitchFlow/
├── src/                         ← tout le code source
│   ├── manage.py                ← commande Django (python src/manage.py ...)
│   ├── stitchflow/              ← config Django
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── celery.py
│   │   └── __init__.py
│   ├── core/                    ← app Django HomeView + templates base
│   │   ├── views.py             ← HomeView
│   │   ├── urls.py
│   │   └── templates/
│   │       ├── base.html        ← layout principal (django_vite)
│   │       └── home.html
│   ├── conversions/             ← app Django pipeline complet
│   │   ├── models.py            ← ConversionJob (UUID, statuts, FileField)
│   │   ├── views.py             ← UnifiedUploadView, FormFragmentView, status API
│   │   ├── urls.py
│   │   ├── forms.py             ← SVGUploadForm, PNGUploadForm, PDFUploadForm
│   │   ├── tasks.py             ← process_conversion_job() Celery
│   │   ├── services/
│   │   │   ├── inkstitch.py     ← convert_svg_to_pes() via CLI
│   │   │   ├── validation.py    ← validate_svg_content()
│   │   │   ├── previews.py      ← generate_pes_preview() + extract_pes_metadata() + score qualité
│   │   │   ├── svg_utils.py     ← post-traitement SVG (filtrage, reorder, fusion couleurs, stroke-fix)
│   │   │   ├── png_processing.py ← vectorisation PNG/JPEG/WebP → SVG (VTracer, potrace)
│   │   │   ├── pdf_processing.py ← extraction SVG depuis PDF (pdftocairo, pdf2image)
│   │   │   ├── thread_color.py  ← snap couleurs SVG → palette Brother (CIE Lab)
│   │   │   └── _vtracer_helper.py ← helper CLI vendor/vtracer ARM64
│   │   └── templates/
│   │       └── conversions/
│   │           ├── upload_unified.html  ← interface drag-and-drop unique (Phase 5)
│   │           ├── upload.html          ← upload SVG direct (legacy)
│   │           ├── upload_pdf.html      ← upload PDF (legacy)
│   │           ├── upload_png.html      ← upload PNG (legacy)
│   │           ├── detail.html          ← page de résultat
│   │           └── partials/
│   │               ├── conversion_status.html  ← fragment HTMX polling
│   │               ├── form_svg.html            ← fragment formulaire SVG
│   │               ├── form_raster.html         ← fragment formulaire PNG/JPEG/WebP/PDF
│   │               ├── form_unknown.html        ← fragment format non reconnu
│   │               ├── svg_suggestions.html     ← analyse SVG uploadé
│   │               ├── png_suggestions.html     ← analyse PNG uploadé
│   │               └── pdf_suggestions.html     ← analyse PDF uploadé
│   └── frontend/                ← projet Vite (npm, assets)
│       ├── package.json
│       ├── vite.config.js
│       ├── node_modules/        ← ignoré git
│       ├── assets/              ← sources JS/CSS (input Vite)
│       │   ├── main.js
│       │   └── styles.css
│       └── static/dist/         ← build Vite (généré, ignoré git)
├── .Codex/                     ← règles et commandes Codex
│   ├── rules/
│   │   ├── 00-index.md
│   │   └── detailed/            ← règles détaillées (sécurité, style, etc.)
│   └── commands/
│       └── commit.md
├── docs/
│   └── pipeline-technique.md    ← documentation complète du pipeline (MAINTENIR À JOUR)
├── tests/
│   ├── manual/                  ← fichiers source pour tests manuels via l'UI
│   │   ├── svg/                 ← 9 SVGs numérotés 01-09 (+ 05b)
│   │   ├── png/                 ← 11 PNGs numérotés 01-11
│   │   ├── jpeg/                ← 2 JPEGs
│   │   ├── pdf/                 ← 4 PDFs (vectoriels + scannés)
│   │   └── webp/                ← 1 WebP
│   ├── fixtures/                ← fixtures pour run_integration.py
│   │   ├── logos/, ecusson/, texte/, geometrique/, pdf/
│   ├── results/                 ← PES générés localement (gitignored)
│   ├── run_integration.py       ← tests E2E automatisés (Phase 6d)
│   └── generate_fixtures.py     ← génère tests/fixtures/
├── vendor/
│   └── vtracer                  ← binaire ARM64 (gitignored, re-télécharger après clone)
├── .env                         ← secrets locaux (ignoré git)
├── .env.example
├── .gitignore
├── AGENTS.md                    ← ce fichier
├── ROADMAP.md
├── pyproject.toml
├── db.sqlite3                   ← base de données locale (ignorée git)
└── media/                       ← fichiers uploadés (ignorés git)
```

---

## Pipeline technique

Documentation complète du pipeline de conversion : `docs/pipeline-technique.md`

**Règle obligatoire :** Mettre à jour `docs/pipeline-technique.md` à chaque modification du pipeline (nouvelles étapes, paramètres modifiés, nouveaux services).

### Résumé pipeline SVG → PES

```
Source → [Vectorisation si raster] → validate → remove_bg → filter_micro → reorder
→ group_colors → scale → force_max_colors(10) → snap_brother → group_colors
→ normalize_stroke → Ink/Stitch CLI → PES → preview + score
```

Fichier principal : `conversions/tasks.py` → `process_conversion_job()`

---

## Conventions de développement

- **Pas de secrets** dans le code — utiliser `.env` via `python-decouple`
- **Chemins via `Path`** — jamais de strings hardcodées pour les chemins système
- **Fichiers uploadés** — toujours renommer avec UUID, jamais faire confiance au nom utilisateur
- **Commandes externes** — toujours via `subprocess.run` dans `services/inkstitch.py`, jamais directement dans les vues
- **Statuts job** — utiliser `ConversionJob.Status.*`, jamais les strings directement
- **Types** — typer les fonctions autant que possible
- **Migrations** — toujours committer les migrations avec le code qui les génère

## Règle de mise à jour de la Roadmap

**Obligatoire à chaque fin de session de développement :**
- Cocher `[x]` dans `ROADMAP.md` tous les éléments terminés dans la session
- Ajouter les nouvelles fonctionnalités décidées (même non implémentées)
- Ne jamais laisser la roadmap en décalage avec l'état réel du code
- Si une Phase est entièrement cochée, ajouter ✅ à son titre

---

## Points d'attention pour les agents IA

- Le venv est à `.venv/` à la racine — **toujours l'activer** avant toute commande Python
- `manage.py` est dans `src/` → commande : `python src/manage.py`
- Celery : `cd src && celery -A stitchflow worker` ou `PYTHONPATH=src celery -A stitchflow worker`
- Vite : `cd src/frontend && npm run dev` ou `npm run build`
- `DATABASE_URL` dans `.env` pour switcher SQLite → PostgreSQL (`dj-database-url`)
- `INKSTITCH_EXECUTABLE` doit pointer vers le vrai exécutable Ink/Stitch
- TailwindCSS v4 : config CSS-first (`@import "tailwindcss"` dans styles.css), pas de `tailwind.config.js`
- DaisyUI v5 : `@plugin "daisyui"` dans le CSS
- Vite root : `src/frontend/assets/`, outDir : `src/frontend/static/dist/`
- Le manifest Vite est à `src/frontend/static/dist/.vite/manifest.json`
- HTMX polling : le partial `conversion_status.html` inclut son propre `hx-trigger` uniquement si le job n'est pas terminal
- Pour ajouter PostgreSQL : `pip install psycopg[binary]` + `DATABASE_URL=postgresql://...` dans `.env`
- `BASE_DIR` dans settings.py pointe vers `src/` ; `BASE_DIR.parent` = racine du projet
