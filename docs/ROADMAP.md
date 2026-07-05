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

## Phase 7 — Assistant pré-conversion + sélection guidée des couleurs ✅

Objectif : analyser le fichier source AVANT la conversion, prévenir les problèmes, et donner à l'utilisateur un contrôle simple sur ses couleurs de fils. Réduire les conversions ratées en informant et guidant en amont.

> **Priorité haute** : c'est la fonctionnalité qui différencie StitchFlow des convertisseurs gratuits. Un brodeur qui voit ses fils avant de lancer est un brodeur qui comprend et qui revient.

### 7a — Avertissements intelligents (bloquants et suggestions) ✅
- [x] Analyse SVG : détection des paths trop petits (< 2mm² à la taille cible) — badge `badge-error`
- [x] Détection des éléments `<text>` non convertis en paths — badge `badge-warning` "Convertir en courbes dans votre outil source"
- [x] Détection du nombre de couleurs > 10 — badge `badge-warning` avec le nombre exact
- [x] Pour PNG/JPEG : avertissement si DPI EXIF < 150 — badge `badge-warning` "Résultat flou probable"
- [x] Avertissements affichés dans les partials HTMX existants (`png_suggestions.html`, `svg_suggestions.html`)

### 7b — Sélection et aperçu des couleurs avant conversion ✅
- [x] Après analyse PNG/JPEG/PDF : afficher les N couleurs détectées avec swatches + pourcentage de surface
- [x] Slider "Nombre de fils" met à jour live les swatches (actifs/grisés) via AlpineJS pur + event `ncolors-changed`
- [x] Clic sur swatch pour exclure une couleur — les exclues sont grisées + barrées
- [x] `excluded_colors` transmis dans le POST → stocké dans `conversion_metadata` → appliqué dans `tasks.py` avant `validate_svg_content`
- [x] Pour SVG direct : afficher les fills uniques comme swatches (exclusion possible)
- [x] Nouvelle fonction `remove_excluded_colors_from_svg()` dans `svg_utils.py`

### 7c — Résumé "ce que va faire la machine" avant conversion ✅
- [x] Estimation du nombre de fils, temps de broderie (~600 pts/min), dimensions finales
- [x] Indicateur brodabilité : 🟢 ≤6 couleurs, pas de texte, pas de petits paths / 🟡 7-10 ou avertissements / 🔴 >10 couleurs
- [x] Affiché dans `partials/pre_conversion_summary.html` (inclus dans png_suggestions + svg_suggestions)

---

## Phase 8 — Correction SVG avant conversion (intervention légère) ✅

Objectif : permettre d'ajuster le SVG vectorisé **après** la vectorisation PNG→SVG mais **avant** Ink/Stitch. Corriger les cas où la vectorisation automatique n'est pas parfaite, sans avoir besoin d'un éditeur complet.

> Approche : SVG natif dans le navigateur + Alpine.js + HTMX. Pas de bibliothèque JS externe dans cette phase.

### 8a — Visualisation du SVG intermédiaire
- [x] Partial `conversions/svg_editor.html` : affichage SVG inline avec zoom + pan (CSS `transform-origin`)
- [x] Pipeline modifié : PNG upload → vectorisation → **pause sur le SVG** → validation utilisateur → PES (`ConversionJob.Status.AWAITING_SVG_VALIDATION`)
- [x] Option "Convertir directement" pour bypasser et garder le comportement actuel
- [x] Affichage comparatif : image source à gauche / SVG vectorisé à droite

### 8b — Ajustement des couleurs sur le SVG
- [x] Liste des couleurs du SVG vectorisé avec swatch + nombre de paths par couleur
- [x] Supprimer une couleur entière (retire tous ses paths du SVG) — `SvgRemoveColorView`
- [x] Fusionner manuellement deux couleurs (glisser une vers l'autre, ou sélection) — `SvgMergeColorsView`
- [x] Endpoint HTMX `POST /conversions/<id>/svg/remove-color/` et `/merge-colors/`

### 8c — Validation et relance
- [x] Bouton "Valider et convertir en PES" → reprend le pipeline à l'étape Ink/Stitch uniquement — `SvgValidateView` + `finalize_svg_to_pes`
- [x] Le SVG modifié remplace `vectorized_svg_file` du job — même UUID, pas de nouveau job
- [x] Prévisualisation live du SVG modifié avant validation (rechargement HTMX du SVG inline)

### 8d — Finitions éditeur & corrections qualité ✅

Objectif : solidifier la base avant la beta. Corriger le bug couleurs, éliminer les frictions restantes, enrichir l'éditeur SVG avec la vraie palette de fils.

- [x] **Bug fix prioritaire** : couleur disparaissant entre la prévisualisation (3 couleurs) et le PES final (2 couleurs) — cause identifiée : deux couleurs SVG proches mappent vers le même fil Brother après snap. Correction UX : preview du fil Brother estimé + badge "⚠ fusionné" affiché dans l'éditeur pour chaque couleur — `get_snap_preview()` dans `thread_color.py`
- [x] **Texte → courbes automatique** : `convert_text_to_paths(svg_path)` dans `svg_utils.py` — appel `inkscape --actions=select-all;object-to-path --export-type=svg` avant `validate_svg_content()` dans `tasks.py`. Syntaxe Inkscape 1.4.4+ (action `object-to-path`, pas `ObjectToPath`)
- [x] **Color picker palette Brother** dans l'éditeur SVG : bouton 🎨 par couleur → modal DaisyUI avec les ~60 fils Brother (filtrable par nom) → `SvgChangeColorView` + endpoint `POST /conversions/<id>/svg/change-color/` + `change_svg_color()` dans `svg_utils.py`
- [x] Afficher le nom du fil Brother le plus proche de chaque couleur SVG dans l'éditeur — `get_brother_palette()` + `get_snap_preview()` injectés dans le contexte éditeur via `_render_svg_editor_response()`

### 8e — Stabilisation pipeline SVG→PES (Ink/Stitch) ✅

Objectif : corriger les problèmes structurels entre la vectorisation SVG et la conversion Ink/Stitch. Les phases précédentes ont optimisé PNG→SVG mais pas la préparation du SVG pour Ink/Stitch, ce qui causait des résultats catastrophiques sur les designs avec fond (tatami de fond, namespace manquant, paths non fermés).

- [x] **Fix `remove_background_fill` pour rectangles arrondis** : shapes ≤20 segments couvrant >80% du viewBox supprimées (les fonds vectorisés en coins arrondis passaient le filtre >12 segments et finissaient en tatami massif)
- [x] **Injection namespace `xmlns:inkstitch`** : `inject_inkstitch_namespace()` — injection textuelle (ElementTree n'émet la déclaration que si un attribut du namespace est sérialisé)
- [x] **Fermeture automatique des paths non fermés** : `close_open_paths()` — ferme chaque sous-path fill sans `Z` (skip running_stitch, stroke-only, et sous-path suivi d'un `m` relatif)
- [x] **Injection intelligente des attributs de point Ink/Stitch** : `inject_inkstitch_params()` — contour fin (<1mm) → `running_stitch`. ⚠️ L'injection `fill_method=auto_fill` prévue a été ABANDONNÉE et l'annotation systématique existante SUPPRIMÉE : mesuré en A/B, 5 annotations font passer Ink/Stitch de 5.7s à timeout 300s (voir converter-memory.md S9)
- [x] **Téléchargement du SVG vectorisé** : bouton "Télécharger SVG" dans l'éditeur et la page résultat — endpoint `GET /conversions/<uuid>/svg/download/`

---

## Phase 9 — Authentification & comptes utilisateurs ✅

Objectif : ouvrir l'outil à plusieurs utilisateurs avec des comptes distincts. Prérequis pour la beta fermée et le SaaS.

> C'est la phase la plus courte techniquement (~1 semaine) mais elle débloque tout : historique personnel, quota, paiement futur.

- [x] Auth Django basique : app `users/` avec `LoginView`, `SignUpView`, `LogoutView`, `ProfileView` — email comme identifiant (username=email), compte activé immédiatement
- [x] Formulaires : `EmailLoginForm` (lookup User par email + authenticate), `SignUpForm` (validation email unique + mdp), `ProfileForm` (prénom/nom)
- [x] Routes : `/auth/login/`, `/auth/register/`, `/auth/logout/`, `/auth/profile/`
- [x] `ConversionJob.user = ForeignKey(User, null=True, on_delete=SET_NULL)` — ownership des jobs, migration `0007_add_user_to_conversion_job`
- [x] Jobs anonymes tolérés : vues détail accessibles par UUID sans auth, liste protégée
- [x] Page "Mes conversions" (`/conversions/mes-conversions/`) : liste des jobs du user connecté avec aperçu + statut — `JobListView`
- [x] Navbar mise à jour : avatar dropdown (Mes conversions / Profil / Déconnexion) si connecté, boutons Connexion + S'inscrire sinon
- [x] `settings.py` : `LOGIN_URL`, `LOGIN_REDIRECT_URL`, `LOGOUT_REDIRECT_URL` configurés

---

## Phase 10 — Dashboard & historique (beta) ✅

Objectif : donner à l'utilisateur une vue sur ses conversions passées. Nécessaire pour la beta — l'utilisatrice doit pouvoir retrouver ses fichiers convertis.

> **Objectif beta** : valider avec l'utilisatrice cible que StitchFlow remplace ses conversions simples à €10/unité.
> **Stratégie complète** : voir `docs/strategie-marketing.md`

### Prérequis avant d'ouvrir la beta

- [ ] **Conversation avec l'utilisatrice beta** : lui expliquer le projet commercial, valider le prix (€3/conv.), sonder son réseau — à faire avant tout lancement public (voir `docs/strategie-marketing.md §2`)
- [ ] **Retirer le lien "Télécharger le SVG" de la page résultat** (`partials/conversion_status.html`) — utile en debug pendant la beta pour diagnostiquer où un problème s'est produit dans le pipeline, mais expose un artefact technique sans valeur pour l'utilisatrice finale. À retirer (ou masquer derrière un mode debug) avant l'ouverture publique
- [x] **Landing page** `/landing/` avec liste d'attente email — hero + bénéfices + encart honnêteté scope, model `WaitlistEmail` dans `core/` (email unique, doublon silencieux), admin

### Auth & sécurité ✅
- [x] Réinitialisation de mot de passe par email (`/auth/password-reset/`) — Django PasswordResetView + Gmail SMTP
- [x] Changement de mot de passe en étant connecté (`/auth/password-change/`)
- [x] Changement d'email avec confirmation mot de passe (`/auth/change-email/`)
- [x] Corrections UI auth : prénom/nom avant email dans l'inscription, lien "Mot de passe oublié ?" dans login
- [x] Navbar connectée : bouton "Prénom ▾" avec dropdown lisible (email + Mes conversions + Profil + Déconnexion)
- [x] Page profil restructurée : section Informations + section Sécurité (email + mot de passe)

### Dashboard ✅
- [x] Liste paginée des jobs (`/conversions/history/`) avec filtres statut + format + date (12 par page)
- [x] Re-conversion depuis un job existant (`POST /conversions/<uuid>/reconvert/`) — copie le fichier source + relance le pipeline
- [x] Téléchargement du PES depuis l'historique (menu contextuel par job)
- [x] Score qualité visible dans l'historique — badge coloré ★ XX/100 par job terminé
- [x] Export CSV des métadonnées (`/conversions/history/export-csv/`) — ID, fichier, format, statut, score, points, fils, largeur, date

---

## Phase 11 — Éditeur broderie avancé ✅

Objectif : passer de l'éditeur léger (supprimer/fusionner/recolorer) à un contrôle professionnel sur le rendu broderie. Développer en fonction des retours de la beta.

> À prioriser par ordre d'impact décroissant : ce qui cause le plus d'erreurs ou de frustration d'abord.

- [x] **Réordonner les couches de broderie** : drag-and-drop des couleurs pour changer l'ordre de broderie (quelle zone est cousue en premier)
- [x] **Choix du type de point** : remplissage (auto_fill) vs point courant (running_stitch) — par zone/couleur — injecte params Ink/Stitch dans le SVG (`inkstitch:stroke_method`)
- [x] **Densité par zone** : régler la densité des points couleur par couleur — injecte `inkstitch:row_spacing_mm` dans le SVG
- [x] **Historique undo/redo** des modifications dans l'éditeur (snapshots fichiers, stack 20 niveaux)

### Post-beta — à prioriser selon retours

> Déplacé hors du chemin beta (juillet 2026) : valeur incrémentale non validée par des retours utilisateurs, la preview statique existe déjà. À remonter si l'utilisatrice beta exprime le besoin ("ça m'éviterait des tests machine").

- [ ] **Prévisualisation animée** : simulation stitch-par-stitch dans le navigateur (JS + pyembroidery data) — voir la broderie se dessiner avant lancement machine
- [ ] Éditeur visuel full-featured si besoin (SVG.js ou Fabric.js) — évaluer après retours beta

---

## Phase 12 — SaaS & monétisation

Objectif : transformer l'outil en service commercial. La beta a validé la valeur, il faut maintenant la monétiser.

> **Positionnement** : €3/conversion recommandé (vs €10 prestataire). Cible : artisanes et ateliers indépendants.
> **Stratégie complète** : voir `docs/strategie-marketing.md`

### Modèle tarifaire (affiné juin 2025)

| Plan | Prix | Quota | Cible |
|------|------|-------|-------|
| Free | €0 | 3 conversions/mois | Discovery |
| Starter | €9/mois | 15 conversions/mois | Artisane occasionnelle |
| Pro | €19/mois | 50 conversions/mois | Artisane régulière |
| Pay-as-you-go | €3/conversion | Illimité à l'unité | Usage ponctuel |

> Pas de plan illimité à prix fixe : les coûts Celery + Ink/Stitch scalent linéairement avec l'usage.

### Essai anonyme sans inscription

- [ ] 2 conversions anonymes par session (cookie + fallback IP via Redis) — zéro friction d'entrée avant compte
- [ ] Affichage "Il vous reste X conversions gratuites" → CTA inscription naturel

### Paiement et infrastructure

- [ ] Système de quotas mensuels par plan (`UserQuota` model, reset le 1er du mois)
- [ ] Paiement Stripe (checkout + webhooks `invoice.paid`, `customer.subscription.deleted`)
- [ ] Page upgrade en compte : comparaison des plans avec CTA Stripe checkout
- [ ] Migration PostgreSQL + stockage S3 (media)
- [ ] Docker Compose + déploiement VPS (Hetzner, Fly.io, ou Railway)
- [ ] CI/CD GitHub Actions (tests + lint + deploy auto)

### Marketing

- [ ] Landing page complète (avant/après, preview fils, témoignage beta, comparaison vs prestataire humain)
- [ ] Ouverture inscription publique
- [ ] Présence passive sur r/embroidery + groupes Facebook broderie FR (après validation beta)

---

## Phase 13 — Multi-machines & détection de complexité

Objectif : étendre le marché au-delà de la machine Brother, et être honnête sur les limites de l'outil.

### 13a — Profil machine utilisateur (initialisation) — PRIORITÉ AVANT PHASE 12

Objectif : stocker la machine de l'utilisateur dans son profil et adapter toutes les contraintes en conséquence. Essentiel pour accueillir plusieurs beta users avec des machines différentes dès l'ouverture.

**Modèles pris en charge initialement :**

| Modèle | Aiguilles | Zone max | Format natif |
|--------|-----------|----------|--------------|
| Brother PR1050X | 10 | 360×200mm | PES v1 |
| Brother PE800 | 1 | 130×180mm | PES v1 |
| Brother SE700 | 1 | 180×130mm | PES v1 |
| Janome MC500E | 1 | 200×200mm | JEF |
| Personnalisé | custom | custom | PES/DST/JEF |

- [x] Modèle `UserProfile` créé dans `users/models.py` (OneToOne User, signal post_save + data migration pour users existants) — l'app n'avait pas de models.py
- [x] Champ `machine_model` (TextChoices) + `machine_needles` + `machine_hoop_width_mm` + `machine_hoop_height_mm` + `machine_format` (PES/DST/JEF/VP3)
- [x] Page "Ma machine" (`/auth/profile/machine/`) : dropdown modèles + champs custom si "Personnalisé", auto-remplissage Alpine.js, presets forcés côté serveur dans `clean()`
- [x] `force_max_svg_colors()` utilise `machine_max_threads` du profil — ⚠️ délibérément distinct de `machine_needles` : les machines mono-aiguille (PE800, SE700, MC500E) brodent le multicolore par re-enfilage, fusionner à 1 couleur serait destructeur (max_threads=8 pour elles)
- [x] Score qualité : seuils fils et dimensions paramétrés par le profil (`extract_pes_metadata(machine=...)`, défaut None = PR1050X — protège le benchmark)
- [x] Jobs anonymes : défauts PR1050X (décision utilisateur)
- [x] Export multi-format : `convert_pes_to_format()` (pyembroidery) si `machine_format != PES` — le PES reste la source de vérité preview/métadonnées (DST ne stocke pas les couleurs)

### 13b — Détection de complexité ✅ (base)

- [x] **Détection de complexité** dans l'analyse pré-conversion : photo réaliste (ratio couleurs uniques >0.25 sur miniature 256px → badge rouge "recommander un prestataire"), dégradés (top 8 couleurs <40% des pixels → badge rouge), >15 couleurs → badge orange "qualité non garantie". Seuils mesurés sur tests/ réels — la variance locale était inutilisable (bords nets des logos ≈ 1100+).
- [ ] Support Brother multi-modèles supplémentaires (PR680W, PR1055X, etc.)

### 13c — API & intégrations (post-SaaS)

- [ ] API REST pour intégrations tierces (ateliers de broderie, e-commerce Shopify/WooCommerce)
- [ ] Webhooks de notification (job terminé, erreur)

### 13d — Barre de progression réelle & estimation fiable ✅

Objectif : remplacer le spinner + barre indéterminée par un suivi réel de la conversion. Consultation `/stitch-advisor` : la promesse marketing "30 secondes" (`differenciateurs.md`) doit rester un plafond, pas une moyenne — cible P50 SVG ≤ 8s, P95 raster ≤ 15s.

- [x] `ConversionJob.progress_pct` / `progress_step` / `duration_seconds` (migration `0008`) — mis à jour à chaque étape majeure du pipeline via `_set_progress()` dans `tasks.py`
- [x] Barre de progression réelle dans `conversion_status.html` (largeur pilotée par `progress_pct`, plus d'animation indéterminée), polling HTMX réduit à 1s
- [x] `services/estimation.py` : estimation du temps basée sur la moyenne des 20 dernières conversions complétées du même format (repli sur heuristique statique si <5 échantillons)
- [x] Instrumentation `logger.debug('[timing] ...')` par étape du pipeline (Inkscape prep, tri/couleurs, Ink/Stitch CLI) — mesure objective pour cibler une future optimisation, aucune régression qualité (benchmark 95.4/100 confirmé après implémentation)
- [x] Vérification ciblée de `generate_pes_preview()` : déjà un rendu de vrais points de broderie (pas un simple remplissage vectoriel) — conservé tel quel
- [ ] **Suivi futur** : analyser les logs `[timing]` sur des cas réels pour identifier objectivement le goulot d'étranglement (cascade de vectorisation VTracer→potrace→Inkscape suspectée) avant toute optimisation de performance ciblée
