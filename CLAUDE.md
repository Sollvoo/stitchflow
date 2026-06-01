# StitchFlow — Guide pour agents IA et développeurs

## Description du projet

StitchFlow est une application web Django permettant de convertir des fichiers SVG en fichiers de broderie `.PES` via Ink/Stitch CLI. Elle est conçue pour évoluer progressivement vers PNG → SVG → PES avec IA et corrections humaines.

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
source /Users/hugobonnet/Documents/StitchFlow/.venv/bin/activate
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
python manage.py runserver
```

Accessible sur : http://localhost:8000

### Vite (assets frontend)

```bash
npm run dev
```

Accessible sur : http://localhost:5173 (assets servis en dev)

Pour la production :
```bash
npm run build
```

### Worker Celery

```bash
source .venv/bin/activate
celery -A stitchflow worker -l info
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
python manage.py makemigrations
python manage.py migrate
```

### Superuser admin

```bash
source .venv/bin/activate
python manage.py createsuperuser
```

---

## Installation d'Ink/Stitch

### Présentation

Ink/Stitch est une extension Inkscape qui peut aussi être appelée en ligne de commande :
```bash
./inkstitch --extension=zip --format-pes=True input.svg > output.zip
```

Documentation officielle : https://inkstitch.org/docs/command-line

### Étapes d'installation sur macOS

1. **Installer Inkscape** (prérequis) :
   ```bash
   brew install --cask inkscape
   ```
   Ou télécharger depuis https://inkscape.org/release/

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
   inkstitch --help
   # ou
   /chemin/vers/inkstitch --help
   ```

### Si Ink/Stitch n'est pas installé

La conversion échouera avec `FileNotFoundError`. Le job passera en statut `failed` avec le message d'erreur. Le reste de l'application (upload, affichage des jobs, HTMX) fonctionne sans Ink/Stitch.

---

## Architecture du projet

```
stitchflow/
├── manage.py
├── pyproject.toml           ← dépendances Python
├── package.json             ← dépendances npm
├── vite.config.js           ← config Vite
├── .env.example             ← variables d'environnement à copier
├── CLAUDE.md                ← ce fichier
├── ROADMAP.md               ← feuille de route
├── stitchflow/              ← config Django
│   ├── settings.py
│   ├── urls.py
│   ├── celery.py
│   └── __init__.py          ← auto-discover Celery
├── frontend/                ← app Django pour les assets
│   ├── views.py             ← HomeView
│   ├── urls.py
│   ├── assets/              ← sources JS/CSS (input Vite)
│   │   ├── main.js          ← entrypoint Vite
│   │   └── styles.css       ← TailwindCSS + DaisyUI
│   ├── static/dist/         ← build Vite (généré, ignoré git)
│   └── templates/
│       ├── base.html        ← layout principal
│       └── home.html        ← page d'accueil
└── conversions/             ← app Django pour les conversions
    ├── models.py            ← ConversionJob
    ├── views.py             ← UploadView, DetailView, StatusView, DownloadView
    ├── urls.py
    ├── forms.py             ← SVGUploadForm avec validation
    ├── tasks.py             ← tâche Celery process_conversion_job
    ├── services/
    │   ├── inkstitch.py     ← convert_svg_to_pes() — intégration CLI
    │   ├── validation.py    ← validate_svg_structure()
    │   └── previews.py      ← stub Phase 2
    └── templates/
        └── conversions/
            ├── upload.html
            ├── detail.html
            └── partials/
                └── conversion_status.html  ← fragment HTMX
```

---

## Pipeline SVG → PES

1. Utilisateur uploade un `.svg` via le formulaire
2. `SVGUploadForm` valide : extension, taille (10 Mo max), contenu XML, renomme avec UUID
3. `ConversionJob` créé en base (status = `pending`)
4. Tâche Celery `process_conversion_job` lancée avec `.delay(job_id)`
5. Le worker Celery :
   - Passe le job en `processing`
   - Appelle `convert_svg_to_pes(input_path, output_dir)`
   - `inkstitch --extension=zip --format-pes=True input.svg` → stdout binaire = ZIP
   - Extrait le `.pes` du ZIP
   - Sauvegarde dans `media/conversions/outputs/`
   - Passe en `completed` (ou `failed` si erreur)
6. La page de détail utilise HTMX (`hx-trigger="every 2s"`) pour interroger `/conversions/<id>/status/`
7. Le partial se rafraîchit jusqu'à statut terminal, puis affiche le bouton de téléchargement

---

## Conventions de développement

- **Pas de secrets** dans le code — utiliser `.env` via `python-decouple`
- **Chemins via `Path`** — jamais de strings hardcodées pour les chemins système
- **Fichiers uploadés** — toujours renommer avec UUID, jamais faire confiance au nom utilisateur
- **Commandes externes** — toujours via `subprocess.run` dans `services/inkstitch.py`, jamais directement dans les vues
- **Statuts job** — utiliser `ConversionJob.Status.*`, jamais les strings directement
- **Types** — typer les fonctions autant que possible
- **Migrations** — toujours committer les migrations avec le code qui les génère

## Points d'attention pour les futurs agents IA

- Le venv est à `.venv/` — toujours l'activer avant toute commande Python
- `DATABASE_URL` dans `.env` pour switcher SQLite → PostgreSQL (`dj-database-url`)
- `INKSTITCH_EXECUTABLE` doit pointer vers le vrai exécutable Ink/Stitch
- TailwindCSS v4 : config CSS-first (`@import "tailwindcss"` dans styles.css), pas de `tailwind.config.js`
- DaisyUI v5 : `@plugin "daisyui"` dans le CSS, pas dans une config JS
- Vite root : `frontend/assets/`, outDir : `frontend/static/dist/`
- Le manifest Vite est à `frontend/static/dist/.vite/manifest.json`
- HTMX polling : le partial `conversion_status.html` inclut son propre `hx-trigger` uniquement si le job n'est pas terminal
- Pour ajouter PostgreSQL : `pip install psycopg[binary]` + `DATABASE_URL=postgresql://...` dans `.env`
