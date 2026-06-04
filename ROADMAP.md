# StitchFlow — Roadmap

## Phase 1 — MVP SVG → PES ✅

Objectif : permettre à un utilisateur d'uploader un SVG et de télécharger un fichier PES.

- [x] Projet Django initialisé
- [x] App `frontend` (Vite, Tailwind, DaisyUI, HTMX, Alpine)
- [x] App `conversions` (modèle, formulaire, vues, services)
- [x] Modèle `ConversionJob` (UUID, statuts, FileField)
- [x] Upload SVG avec validation
- [x] Tâche Celery asynchrone
- [x] Service `inkstitch.py` (intégration CLI)
- [x] Page de statut avec polling HTMX
- [x] Téléchargement du fichier PES (nom basé sur le fichier SVG original)
- [x] Tests unitaires (services, formulaires, utilitaires SVG)
- [x] Validation SVG approfondie (SVG vide, sans chemins brodables, dimensions nulles)
- [x] Prévisualisation du SVG uploadé (côté client via FileReader + AlpineJS)

---

## Phase 2 — Amélioration de la conversion SVG ✅

Objectif : donner plus de contrôle sur la conversion et améliorer le feedback utilisateur.

- [x] Messages d'erreur compréhensibles (SVG sans éléments brodables, inkstitch absent, timeout)
- [x] Prévisualisation PNG du résultat PES (via pyembroidery, rendu server-side)
- [x] Détection et affichage des couleurs de fils (depuis le PES généré, avec swatches colorés)
- [x] Choix de la taille de broderie (largeur cible en mm, ratio préservé)
- [x] Estimation du nombre de points (depuis le PES, affiché après conversion)
- [x] Affichage du temps de broderie estimé (~600 points/min, Brother PR1050X)
- [x] Informations de conversion : dimensions réelles en mm, nombre de fils, points, temps
- [x] Validation SVG étendue : support des fills CSS inline (`style="fill:..."`) en plus des attributs directs

---

## Phase 3 — PNG → SVG → PES ✅

Objectif : accepter des images PNG et les vectoriser automatiquement en SVG.

- [x] Upload PNG (formulaire séparé `/conversions/png/`, validation magic bytes + taille 20 Mo)
- [x] Nettoyage de l'image (contraste × 1.3, netteté × 1.5, lissage — via Pillow)
- [x] Suppression du fond (rembg IA avec fallback seuillage Pillow, optionnel au choix utilisateur)
- [x] Réduction du nombre de couleurs (quantization Pillow MEDIANCUT, 2–16 couleurs, défaut 6)
- [x] Vectorisation PNG → SVG (VTracer primaire ; fallback Inkscape potrace si VTracer crash ARM64)
- [x] Post-traitement SVG Inkscape : suppression raster embedded + conversion fills CSS → attributs directs
- [x] Validation du SVG généré (support attributs directs ET style CSS inline)
- [x] Aperçu comparatif PNG source / SVG vectorisé (dans `conversion_status.html`)
- [x] Tests unitaires : `test_png_forms.py`, `test_png_processing.py`, `test_png_tasks.py` (21 tests)
- [x] Tests de régression validation CSS inline (3 cas : fill CSS, stroke CSS, fill:none)

---

## Phase 4 — Qualité PNG + Smart UX + Nouveaux formats ✅

Objectif : améliorer la fidélité couleurs, rendre l'outil simple pour n'importe quel utilisateur, et accepter tous les formats courants.

### 4a — Amélioration qualité vectorisation PNG ✅
- [x] Résoudre le crash VTracer sur ARM64 macOS (SIGSEGV) — solution : binaire CLI vtracer précompilé ARM64 dans vendor/
- [x] Améliorer la fidélité couleurs PNG→PES : VTracer CLI + consolidation couleurs → aplats propres par couleur
- [x] Pipeline vectorisation : **VTracer CLI** (vendor/vtracer) → VTracer Python → potrace → Inkscape (fallbacks)
- [x] `brew install potrace` documenté dans CLAUDE.md + instructions vtracer CLI dans CLAUDE.md
- [x] Fix bug coordonnées SVG : potrace `--unit 10` → `--unit 1` (coords 10× trop grandes causaient timeout inkstitch)
- [x] Simplification SVG systématique avant inkstitch (pas seulement si >80KB)
- [x] Fix bug fond noir : preprocess_image() aplatissait l'alpha vers noir (RGBA→RGB sans fond blanc)
- [x] Meilleurs paramètres potrace : alphamax 0.1, opttolerance 0.2, turdsize 2 (coins nets, détails préservés)
- [x] Upscale plus fort : _POTRACE_MIN_DIM 400→600 px, cap 2×→3× (meilleure qualité texte)
- [x] Fonction _consolidate_svg_colors() : fusion des couleurs similaires VTracer en N clusters pour aplats broderie

### 4b — Auto-paramétrage intelligent (Pillow, sans coût) ✅
- [x] Analyse automatique du PNG à l'upload : endpoint HTMX `/conversions/analyze-png/` (Pillow MEDIANCUT 12 couleurs)
- [x] Détection automatique du fond blanc (>70% pixels clairs) → information affichée
- [x] Affichage des valeurs suggérées avec bouton "Appliquer" qui met à jour le slider n_colors
- [x] L'utilisateur peut modifier les valeurs avant de lancer la conversion

### 4c — Support JPEG et WebP ✅
- [x] Accepter JPEG et WebP en plus de PNG
- [x] Conversion interne JPEG/WebP → PNG avant d'entrer dans le pipeline (Pillow, convert_to_png())
- [x] Avertissement visible : "JPEG peut donner des résultats moins nets qu'un PNG ou SVG"
- [x] Validation magic bytes pour JPEG (`\xff\xd8\xff`) et WebP (`RIFF...WEBP`)

### 4d — Support PDF → PES ✅
- [x] Accepter les fichiers PDF (logos, designs livrés par graphistes)
- [x] Rasterisation PDF → PNG haute résolution (300 dpi) via `pdf2image` + `poppler`
- [x] Entrée dans le pipeline PNG → SVG → PES existant
- [x] Gestion des PDFs multi-pages : convertir uniquement la première page par défaut
- [x] Fichiers de test : tests/jpeg/test-photo.jpg, tests/webp/test-logo.webp, tests/pdf/test-logo.pdf
- [ ] Tests unitaires : test_pdf_processing.py, test_vtracer_cli.py

---

## Phase 5 — Interface unifiée drag-and-drop

Objectif : un seul point d'entrée pour tous les formats. Zéro friction.

- [ ] Zone de dépôt unique (`/conversions/`) acceptant SVG, PNG, JPEG, WebP, PDF
- [ ] Détection automatique du type de fichier côté client (type MIME + magic bytes)
- [ ] Affichage dynamique du formulaire adapté selon le type détecté (HTMX/AlpineJS)
- [ ] Paramètres pré-remplis par l'analyse automatique (Phase 4b)
- [ ] Section "Paramètres avancés" collapsible pour les utilisateurs expérimentés
- [ ] Suppression des formulaires séparés `/conversions/svg/` et `/conversions/png/`
- [ ] Page d'accueil simplifiée : une seule action, pas de choix de format

---

## Phase 6 — Assistant qualité broderie

Objectif : analyser automatiquement le design avant conversion et prévenir les problèmes.

- [ ] Détection des détails trop petits pour la broderie (< 2 mm typiquement)
- [ ] Détection du texte trop petit
- [ ] Détection des zones à densité trop haute (risque de chevauchements)
- [ ] Score de qualité broderie (0–100) avec explication des points perdus
- [ ] Suggestions d'amélioration en langage naturel

---

## Phase 7 — Interface de corrections humaines

Objectif : permettre à l'utilisateur de modifier le design directement dans le navigateur.

- [ ] Éditeur visuel (SVG interactif dans le navigateur)
- [ ] Supprimer des zones / couleurs
- [ ] Changer les couleurs de fil
- [ ] Changer l'ordre de broderie
- [ ] Modifier le type de point (satin, remplissage, courant…)
- [ ] Modifier la densité
- [ ] Prévisualisation interactive dans le navigateur (version JavaScript de l'aperçu broderie)
- [ ] Prévisualisation animée stitch-par-stitch avant export (simulation de broderie)
- [ ] Historique des modifications (undo/redo)

---

## Phase 8 — Compatibilité machines

Objectif : adapter le format de sortie selon la machine cible.

- [ ] Choix du modèle de machine à broder (Brother, Janome, Bernina…)
- [ ] Compatibilité multi-format de sortie (PES, DST, JEF, VP3…)
- [ ] Choix de la version PES (v1 universel vs v6 Brother pro — v1 par défaut, stable)
- Note : priorité actuelle = **Brother PR1050X** (machine 10 aiguilles professionnelle, compatible PES v1)

---

## Phase 9 — Produit complet

Objectif : passer d'un outil à une plateforme.

- [ ] Comptes utilisateurs (inscription, connexion, profil)
- [ ] Historique des conversions par utilisateur
- [ ] Migration vers PostgreSQL
- [ ] Stockage cloud (S3 ou compatible) pour les fichiers media
- [ ] Quotas de conversion par compte
- [ ] Bibliothèque de designs (catalogue partagé)
- [ ] Paiements éventuels (Stripe)
- [ ] API REST pour intégrations tierces
- [ ] Docker / Docker Compose pour déploiement simplifié
- [ ] CI/CD (GitHub Actions)
