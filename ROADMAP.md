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

### 4e — Qualité excellence broderie (refonte pipeline PDF + raster) ✅
- [x] PDF vectoriel : extraction directe via `pdftocairo -svg` sans rasterisation (bypass double perte d'info)
- [x] Détection automatique PDF vectoriel vs scanné (comptage `<path>` vs `<image>` dans le SVG extrait)
- [x] Pipeline PDF vectoriel : post-traitement SVG (suppression strokes parasites + simplification Inkscape)
- [x] Erreur explicite pour PDFs avec dégradés de couleur (non brodables)
- [x] Quantification PIL avant VTracer (`_quantize_to_n_colors`, dither=NONE) : élimine l'antialiasing à la source
- [x] Machine cible documentée : Brother entrepreneur pro X PR1050X (10 aiguilles, 360×200mm, PES v1)
- [x] Fix bug couleurs `rgb(X%,Y%,Z%)` dans SVG pdftocairo → `#RRGGBB` (Ink/Stitch ValueError)
- [x] Analyse automatique PDF à l'upload : bandeau dynamique (vectoriel ✓ vs scanné), dimensions, largeur pré-remplie
- [x] Score qualité broderie 0–100 : 5 critères pondérés (fils, points, dimensions, sauts, densité) — affiché dans l'UI avec détails dépliables

### 4f — Fidélité couleurs & score strict ✅
- [x] Routeur logo/photo : `_detect_image_type()` via `getcolors(maxcolors=min(200, n_colors*20))` — logos → potrace direct, photos → VTracer
- [x] FASTOCTREE remplace MEDIANCUT dans `_quantize_to_n_colors()` et `_vectorize_potrace()` — meilleure fidélité perceptuelle
- [x] Snap couleurs SVG → palette Brother : `thread_color.py`, distance CIE Lab (stdlib math), palette `InkStitch Brother Embroidery.gpl` (~60 fils)
- [x] Score qualité renforcé : 7 critères (ajout fidélité couleurs Lab 18% + couverture vectorisation 12%)
- [x] Gate critique : si `min(points, fidélité, couverture) < 20` → score capé à 40/100 — impossible d'avoir 85+ sur une vectorisation vide
- [x] Fichiers de test synthétiques ajoutés : `tests/png/10-degrade-multicouleur.png`, `tests/png/11-logo-transparent-alpha.png`, `tests/jpeg/12-logo-formes-simple.jpg`

### 4g — Auto-détection & qualité score (session courante) ✅
- [x] Auto-analyse PNG améliorée : quantize 32 couleurs (était 12) + seuil 0.5% (était 1%) + cap à 16 (était 12)
- [x] Détection fond transparent via canal alpha RGBA — plus de faux-négatifs sur logos PNG transparents
- [x] Heuristique largeur via DPI EXIF si disponible, fallback pixel inchangé
- [x] Score qualité : seuils resserrés fils (8-10 → 60pts, était 75) + sauts (<0.5% excellent, était <1%)
- [x] Breakdown debug JSON dans chaque conversion Celery (`logger.debug`) + `raw_value`/`thresholds` par critère
- [x] `raw_score_before_gate` et `gate_applied` exposés dans `conversion_metadata`
- [x] Bibliothèque de fixtures par catégories broderie : `tests/fixtures/` (logos, écusson, texte, géométrique, pdf) + script `generate_fixtures.py`

---

## Phase 5 — Interface unifiée drag-and-drop ✅

Objectif : un seul point d'entrée pour tous les formats. Zéro friction.

### Frontend
- [x] Zone de dépôt unique (`/conversions/`) avec drag-and-drop AlpineJS — animation `dragover`, badge format détecté
- [x] Détection du type de fichier côté client (type MIME + fallback extension) → affichage du label format détecté
- [x] Chargement dynamique HTMX du fragment de formulaire selon le format détecté (`htmx.ajax GET /conversions/form/<format>/`)
- [x] Fragment SVG : formulaire minimal (target_width_mm uniquement)
- [x] Fragment PNG/JPEG/WebP/PDF : slider n_colors + toggle remove_background + target_width_mm
- [x] Analyse automatique déclenchée dès le drop (fetch POST → analyze-svg/png/pdf → Alpine.initTree)
- [x] Page d'accueil (`/`) simplifiée : un seul bouton CTA "Convertir un fichier"
- [x] Bouton "Convertir" grisé si pas de fichier ou format non supporté (Alpine `:disabled`)

### Backend
- [x] `UnifiedUploadView` (GET + POST `/conversions/`) : détecte le format réel via magic bytes, dispatch vers SVGUploadForm / PNGUploadForm / PDFUploadForm
- [x] `FormFragmentView` (GET `/conversions/form/<format>/`) : retourne le fragment de formulaire adapté
- [x] Redirections backward compat : `/conversions/svg/`, `/conversions/png/`, `/conversions/pdf/` → 302 vers `/conversions/`
- [x] Validation magic bytes côté serveur indépendamment du type MIME client (sécurité)

---

## Phase 6 — Qualité vectorisation avancée ✅

Objectif : éliminer les artefacts les plus courants (sauts excessifs, micro-paths parasites, couleurs mal groupées) pour atteindre un score qualité moyen ≥ 75 sur les logos et écussons courants.

> **Prérequis qualité SaaS** : cette phase doit être terminée avant toute ouverture commerciale.

### 6a — Réduction des sauts de fil (priorité 1) ✅
- [x] Réordonner les paths SVG avant Ink/Stitch : algo greedy nearest-neighbor sur les centroids des paths — minimise les déplacements à vide
- [x] Implémentation dans `services/svg_utils.py` : `reorder_svg_paths_for_minimal_jumps(svg_path)`
- [x] Appel automatique dans `tasks.py` après `validate_svg_content`, avant scaling + conversion PES
- [x] Réordonne les paths DANS chaque `<g>` ET les groupes eux-mêmes (nearest-neighbor sur centroïdes moyens)

### 6b — Filtrage des micro-paths parasites ✅
- [x] Détecter et supprimer les paths SVG dont la surface est < 0.1mm² à la taille cible (seuil abaissé de 0.5 → 0.1mm² pour conserver les petits détails de design)
- [x] Ces micro-paths génèrent des points isolés + sauts parasites sans contribution visuelle
- [x] Implémentation : `filter_micro_paths(svg_path, target_width_mm, min_area_mm2=0.1)` dans `svg_utils.py`
- [x] Garde anti-vide : ne supprime jamais le dernier path (conserve le plus grand si tous filtrés)
- [x] Avertissement dans les logs si > 10% des paths supprimés (signe d'une vectorisation de mauvaise qualité)

### 6c — Amélioration détection logo vs photo ✅
- [x] Ajouter `_compute_local_variance()` : variance moyenne des blocs 8×8 en niveaux de gris
- [x] Logos = variance ≤ 60 → potrace ; photos = variance ≥ 200 → VTracer ; ambiguë → fallback getcolors
- [x] Log du critère utilisé + score d'entropie à chaque routage

### 6d — Tests d'intégration automatisés sur fixtures ✅
- [x] Script `tests/run_integration.py` : passe chaque fixture dans le pipeline complet via HTTP + Celery
- [x] Endpoint JSON `GET /conversions/<uuid>/api/status/` ajouté dans views.py + urls.py
- [x] Compare score obtenu vs score attendu défini dans `tests/fixtures/README.md`
- [x] Rapport JSON en sortie : pass/fail par catégorie + score moyen par catégorie

### 6e — Corrections qualité post-tests ✅
- [x] `remove_background_fill(svg_path)` dans `svg_utils.py` : supprime les fills blanc/quasi-blanc (L* > 92) couvrant > 85% du viewBox — élimine le fond blanc qui rendait le preview invisible
- [x] `force_max_svg_colors(svg_path, max_colors=10)` dans `svg_utils.py` : fusionne itérativement les couleurs les plus proches (Lab) jusqu'à ≤10 fils — garantit la compatibilité Brother PR1050X (10 aiguilles)
- [x] Gate scoring SVG direct : pour les SVG uploadés directement, la fidélité couleurs (dépendante d'Ink/Stitch, hors contrôle) n'active plus le cap à 40 — score 40→84 sur texte-contours-fins.svg
- [x] Formule fidélité couleurs allégée : coefficient 1.2× au lieu de 2× — Δ Lab 63 donne score 25 au lieu de 0 (plus réaliste perceptuellement)
- [x] Ordre pipeline optimisé : `remove_background_fill` → `filter_micro_paths` → `reorder_paths` → `snap_colors` → `force_max_svg_colors` → `convert_to_pes`

### 6f — Améliorations qualité cas complexes ✅
- [x] Fix preview renderer : `generate_pes_preview()` réécrit avec Pillow — itère sur `pattern.stitches`, ignore JUMP/TRIM, pas de lignes parasites, couleurs fidèles par fil
- [x] Filtrage COLOR_BREAK PES v1 amélioré : `_filter_pes_v1_color_breaks()` passe en logique glissante (blanc encadré de deux non-blancs = COLOR_BREAK) au lieu d'alternance stricte — gère les designs avec vrai fil blanc
- [x] Suppression fond de page PDF : `_remove_pdf_page_background()` dans `pdf_processing.py` — supprime le premier rect/path couvrant > 90% du viewBox (fond de page pdftocairo coloré)
- [x] Ordre pipeline corrigé : `force_max_svg_colors` AVANT `snap_svg_colors` — snap plus précis sur couleurs déjà réduites
- [x] `snap_svg_colors_to_brother_palette()` étend le snap aux attributs `stroke` (en plus de `fill`) — réduit Δ Lab pour texte/contours
- [x] `normalize_stroke_only_paths()` dans `svg_utils.py` : convertit les paths stroke-only (fill=none, stroke=#hex) en fill=#hex — texte vectorisé en contours devient brodable
- [x] `remove_background_fill()` amélioré : ne supprime plus les shapes avec >12 segments SVG (hexagones, silhouettes) — évite la suppression d'éléments de design complexes
- [x] Paramètres potrace adaptatifs : pour n_colors > 8 → `--turdsize=1`, `--opttolerance=0.1` — meilleure fidélité sur designs complexes
- [x] Paramètres VTracer adaptatifs : pour n_colors > 8 → `--filter_speckle=2`, `--color_precision=8`, `--path_precision=4`, `gradient_step = max(8, 256 // n_colors)`
- [x] Documentation pipeline créée : `docs/pipeline-technique.md` — description complète de chaque étape

---

## Phase 7 — Assistant pré-conversion

Objectif : analyser le fichier source AVANT la conversion pour prévenir les problèmes et guider l'utilisateur. Réduire les conversions "Problématique" en informant en amont.

- [ ] Analyse SVG source : détection des paths trop petits (< 2mm à la taille cible) — avertissement bloquant
- [ ] Détection des éléments `<text>` non convertis en paths — suggestion de vectoriser dans l'outil source
- [ ] Détection du nombre de couleurs excessif (> 10 pour PR1050X) — suggestion de réduction
- [ ] Détection des zones à densité trop haute (risque de chevauchements de points à la broderie)
- [ ] Avertissements distincts : bloquants 🔴 (conversion impossible) vs suggestions 🟡 (résultat dégradé)
- [ ] Affiché dans l'UI via HTMX entre le drop et le bouton "Convertir" — zéro friction
- [ ] Pour PNG/JPEG : avertissement si image < 300 DPI estimé (flou probable après vectorisation)

---

## Phase 8 — Éditeur SVG intermédiaire (léger)

Objectif : permettre d'ajuster le SVG vectorisé **avant** d'envoyer à Ink/Stitch, sans bloquer sur un éditeur full-featured. Corriger 80% des cas problématiques en 20% de l'effort d'un éditeur complet.

> Approche : SVG natif dans le navigateur + Alpine.js + HTMX. Pas de Fabric.js dans cette phase.

### 8a — Visualisation du SVG intermédiaire
- [ ] Nouvelle page/partial `conversions/svg_editor.html` affichée après vectorisation PNG→SVG, avant Ink/Stitch
- [ ] Pipeline modifié : PNG upload → vectorisation → **pause** → validation utilisateur → PES
- [ ] Affichage SVG inline avec zoom + pan (CSS `transform-origin`)
- [ ] Option "Convertir directement" pour bypasser l'éditeur (comportement actuel)

### 8b — Ajustement des couleurs
- [ ] Liste des couleurs détectées dans le SVG avec swatch coloré + compteur de paths
- [ ] Fusionner deux couleurs proches (drag ou sélection manuelle) → merge des paths SVG côté serveur
- [ ] Supprimer une couleur entière (retire tous les paths de cette couleur du SVG)
- [ ] Endpoint HTMX `POST /conversions/<id>/svg/merge-colors/` et `/remove-color/`

### 8c — Validation et relance
- [ ] Bouton "Valider et convertir en PES" → reprend le pipeline à l'étape Ink/Stitch
- [ ] Le SVG modifié remplace `vectorized_svg_file` du job, nouveau `ConversionJob` créé pour traçabilité
- [ ] Prévisualisation live du SVG modifié avant validation

---

## Phase 9 — Authentification & multi-utilisateurs

Objectif : ouvrir l'outil à plusieurs utilisateurs avec des comptes distincts. Prérequis pour le SaaS.

> **Pourquoi après l'éditeur SVG** : les fonctionnalités de correction (phases 6-8) doivent être stables avant d'y attacher des comptes. Sinon les migrations de données deviennent complexes.

- [ ] Auth Django basique : `django.contrib.auth` + formulaires login/register/logout
- [ ] `ConversionJob.user = ForeignKey(User, null=True)` — ownership des jobs
- [ ] Accès restreint : un utilisateur ne voit que ses propres jobs
- [ ] Sessions anonymes tolérées (jobs sans user) — transition douce
- [ ] Page profil minimale : email, nb conversions, quota restant

---

## Phase 10 — Dashboard & historique

Objectif : donner à l'utilisateur une vue sur ses conversions passées et ses statistiques.

- [ ] Liste paginée des jobs (`/conversions/history/`) avec filtres statut + format + date
- [ ] Re-conversion depuis un job existant (re-uploader le même fichier avec nouveaux paramètres)
- [ ] Comparaison côte à côte de deux conversions (score, fils, points)
- [ ] Export CSV des métadonnées de conversion (pour analyse)
- [ ] Stats globales : score moyen par format, temps moyen, formats les plus utilisés

---

## Phase 11 — SaaS & monétisation

Objectif : transformer l'outil en service commercial. Le marché est réel (gap entre services manuels $10-75/24h et aucun automatique sérieux).

> **Positionnement** : "Conversion automatique instantanée pour logos simples et écussons — pas pour photos complexes". Prix cible : €2-5/conversion.

- [ ] Système de crédits : X conversions/mois selon le plan
- [ ] Plans tarifaires (ex: Free 3/mois, Pro €9/mois illimité, Pay-as-you-go €3/conversion)
- [ ] Paiement Stripe (checkout + webhooks)
- [ ] Migration PostgreSQL + stockage S3 (media)
- [ ] Docker Compose + déploiement VPS (Hetzner, Fly.io, Railway)
- [ ] CI/CD GitHub Actions (tests + lint + deploy auto)
- [ ] Page marketing / landing page (bénéfices vs services manuels : instantané, pas 24h d'attente)
- [ ] API REST pour intégrations tierces (ateliers de broderie, e-commerce)

---

## Phase 12 — Éditeur SVG complet (long terme)

Objectif : éditeur professionnel dans le navigateur pour les utilisateurs avancés qui veulent contrôle total.

- [ ] Éditeur visuel full-featured (SVG.js ou Fabric.js)
- [ ] Changer les couleurs de fil depuis la palette Brother (~60 fils)
- [ ] Changer l'ordre de broderie (drag-and-drop des couches)
- [ ] Modifier le type de point (satin, remplissage, courant) — nécessite intégration Ink/Stitch params
- [ ] Modifier la densité par zone
- [ ] Prévisualisation animée stitch-par-stitch (simulation de broderie en JS)
- [ ] Historique des modifications (undo/redo)
- [ ] Compatibilité multi-machines : DST, JEF, VP3, HUS — via pyembroidery
