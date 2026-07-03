# Pipeline technique StitchFlow

> Mettre à jour ce document à chaque modification du pipeline de conversion.

## Vue d'ensemble

```
Fichier source (SVG / PNG / JPEG / WebP / PDF)
        │
        ▼
[Détection format via magic bytes]
        │
   ┌────┴─────────────────────────────────────┐
   │ SVG direct        │ Raster (PNG/JPEG/WebP)│ PDF
   │                   │                       │
   ▼                   ▼                       ▼
source_svg_path   Vectorisation          Extraction SVG
(pas de traitement)   (§ Vectorisation)   (pdftocairo)
   │                   │                       │
   └───────────────────┴───────────────────────┘
                        │
                        ▼
              [Pipeline SVG → PES commun]
                        │
           0. remove_excluded_colors_from_svg()  ← si couleurs exclues
           1. prepare_svg_for_inkstitch()         ← normalisation complète
              ├─ Inkscape CLI : object-to-path, clone-unlink,
              │   selection-ungroup, object-to-path×2, vacuum-defs
              ├─ _inline_svg_styles()     ← style= CSS → attributs explicites
              ├─ _remove_invisible_elements()  ← display:none, opacity:0, fill:none
              ├─ _strip_clip_path_refs()  ← retire clip-path et mask
              └─ _strip_fill_method_annotations() ← purge fill_method hérités (S9)
           2. validate_svg_content()
           3. remove_background_fill()        ← raster seulement
           4. filter_micro_paths()
           5. reorder_svg_paths_for_minimal_jumps()
           6. group_paths_by_color()
           7. scale_svg_to_width_mm()         ← si target_width_mm défini
           8. force_max_svg_colors(max=machine.max_threads)  ← profil machine (défaut 10)
           9. snap_svg_colors_to_brother_palette()
          10. group_paths_by_color()          ← bis après fusion
          11. inject_inkstitch_params()       ← contours fins <1mm → running_stitch
          12. normalize_stroke_only_paths()   ← skip paths inkstitch:stroke_method
          13. close_open_paths()              ← ferme les sous-paths fill sans Z
          14. inject_inkstitch_namespace()    ← garantit xmlns:inkstitch sur le root
                        │
                        ▼
              convert_svg_to_pes()  [Ink/Stitch CLI]
                        │
              convert_pes_to_format()  ← si machine_format != PES (DST/JEF/VP3)
                        │
                        ▼
              generate_pes_preview()  [pyembroidery]
              extract_pes_metadata()  [pyembroidery + scoring]
```

---

## Étapes détaillées

### 1. Détection et routing

**Fichier :** `conversions/views.py` → `UnifiedUploadView`

- Détecte le format via **magic bytes** (pas le type MIME client)
- SVG → branche C
- PNG/JPEG/WebP/PDF scanné → branche B
- PDF vectoriel → branche A

### 2. Branche A — PDF vectoriel

**Fichier :** `conversions/services/pdf_processing.py`

- `extract_vector_svg_from_pdf()` : pdftocairo `-svg -f 1 -l 1`
- `is_vector_pdf_svg()` : détecte PDF vectoriel (≥5 paths, 0 images)
- `postprocess_vector_svg()` :
  - Refuse les dégradés (`GradientNotSupportedError`)
  - Supprime les strokes parasites pdftocairo
  - Normalise `rgb(X%,Y%,Z%)` → `#RRGGBB`
  - Simplifie via Inkscape

### 3. Branche B — Raster (PNG/JPEG/WebP/PDF scanné)

**Fichier :** `conversions/services/png_processing.py`

#### 3a. Prétraitement
- `convert_to_png()` : JPEG/WebP → PNG temporaire
- `convert_pdf_to_png()` : PDF → PNG 300dpi via pdf2image
- `validate_png()` : magic bytes + dimensions (≤ 5000×5000 px)
- `preprocess_image()` : contraste/netteté adaptatif (logo: ×1.1, photo: ×1.3+×1.5)
- `remove_background()` : rembg IA ou fallback seuillage Pillow (pixels > 230 → transparent)

#### 3b. Vectorisation
- `vectorize_to_svg(n_colors)` :
  1. `_flatten_alpha()` : RGBA → RGB sur fond blanc
  2. `_detect_image_type()` : logo (variance ≤60) ou photo (variance ≥200)
  3. **Logo** → `_vectorize_potrace()` (couleurs exactes via getcolors)
  4. **Photo/fallback** → `_quantize_to_n_colors()` FASTOCTREE (sans dithering) puis :
     - VTracer CLI (vendor/vtracer ARM64-safe) → `_consolidate_svg_colors()`
     - Fallback VTracer Python subprocess
     - Fallback potrace MEDIANCUT
     - Fallback Inkscape trace

**Paramètres adaptatifs potrace (n_colors > 8) :**
- `--turdsize=1` (était 2) → préserve plus de petits détails
- `--opttolerance=0.1` (était 0.2) → courbes plus précises

**Paramètres adaptatifs VTracer (n_colors > 8) :**
- `--filter_speckle=2` (était 4) → préserve plus de détails fins
- `--color_precision=8` (était 6) → meilleure précision couleur
- `--path_precision=4` (était 3) → courbes plus précises
- `gradient_step = max(8, 256 // n_colors)` (était max(16,...))

### 4. Pipeline SVG → PES commun

**Fichier :** `conversions/tasks.py`

| Étape | Fonction | Description |
|-------|----------|-------------|
| 0 | `remove_excluded_colors_from_svg()` | Supprime les couleurs exclues par l'utilisateur |
| 1 | `prepare_svg_for_inkstitch()` | **Normalisation complète** — voir détail ci-dessous |
| 2 | `validate_svg_content()` | Vérifie éléments brodables (path/rect/circle...) avec fill ou stroke |
| 3 | `remove_background_fill()` | Supprime fills blanc (L*>92) couvrant >85% viewBox. ⚠️ Seulement pour raster. |
| 4 | `filter_micro_paths()` | Supprime paths < 0.5 mm² (bruit vectorisation) |
| 5 | `reorder_svg_paths_for_minimal_jumps()` | Greedy nearest-neighbor sur centroids → minimise sauts |
| 6 | `group_paths_by_color()` | Regroupe paths plats (VTracer) par couleur → moins de changements fil |
| 7 | `scale_svg_to_width_mm()` | Redimensionne à target_width_mm (ratio conservé) |
| 8 | `force_max_svg_colors(machine.max_threads)` | Fusionne itérativement couleurs Lab les plus proches → ≤N fils (profil machine, défaut 10) |
| 9 | `snap_svg_colors_to_brother_palette()` | Snappe fill + stroke → fil Brother le plus proche (CIE Lab) |
| 10 | `group_paths_by_color()` | Re-groupement après fusion couleurs |
| 11 | `inject_inkstitch_params()` | Contours fins (<1mm de largeur bbox) → `inkstitch:stroke_method=running_stitch`. Ne touche jamais un attribut existant (choix éditeur préservés). |
| 12 | `normalize_stroke_only_paths()` | Convertit paths stroke-only en fill. Skip les paths `inkstitch:stroke_method`. |
| 13 | `close_open_paths()` | Ferme chaque sous-path fill sans `Z` — un path fill non fermé est ignoré silencieusement par Ink/Stitch. Skip running_stitch/stroke-only et sous-path suivi d'un `m` relatif. |
| 14 | `inject_inkstitch_namespace()` | Garantit `xmlns:inkstitch` sur le root (injection textuelle — ElementTree ne l'émet que si un attribut du namespace est sérialisé). |

**Ordre critique :** `force_max_colors` AVANT `snap` (réduction d'abord, snap sur couleurs réduites = plus précis). `inject_inkstitch_params` AVANT `normalize_stroke_only_paths` (sinon plus de strokes à marquer). `close_open_paths` APRÈS (pour fermer aussi les fills issus de strokes convertis).

**⚠️ Interdit — `inkstitch:fill_method="auto_fill"`** : mesuré S9 en A/B contrôlé, 5 annotations font passer Ink/Stitch de 5.7s à timeout 300s. Le remplissage par défaut d'Ink/Stitch est correct ; `prepare_svg_for_inkstitch` purge désormais les annotations héritées (`_strip_fill_method_annotations`).

**Profil machine** : `_resolve_machine_params(job)` dans `tasks.py` — profil du user (`UserProfile.machine_params()`, get_or_create lazy) ou défauts PR1050X pour les jobs anonymes. Propagé à `force_max_svg_colors`, `extract_pes_metadata(machine=...)` (seuils fils + dimensions du scoring) et à l'export multi-format.

#### Détail étape 1 : `prepare_svg_for_inkstitch()`

**Fichier :** `conversions/services/svg_utils.py`

Deux sous-étapes exécutées systématiquement :

**A — Inkscape CLI** (si Inkscape disponible, timeout 60s) :
```
select-all;object-to-path      → textes, formes géométriques → paths
select-all;clone-unlink         → <use> et clones → éléments standalone
select-all;selection-ungroup    → aplatit les groupes, applique les transforms imbriqués
select-all;object-to-path       → 2ème passe pour les éléments nouvellement exposés
vacuum-defs                     → nettoie les <defs> inutilisées
```

**B — Python lxml-free** (toujours, même sans Inkscape) :
- `_inline_svg_styles()` : `style="fill:red"` → attribut `fill="#ff0000"` explicite. Normalise aussi les couleurs nommées et `rgb(r,g,b)`.
- `_remove_invisible_elements()` : supprime `display:none`, `visibility:hidden`, `opacity:0`, et `fill:none` sans stroke.
- `_strip_clip_path_refs()` : retire les attributs `clip-path=` et `mask=` (éléments brodés en totalité, sans clipping).

### 5. Conversion Ink/Stitch

**Fichier :** `conversions/services/inkstitch.py`

```bash
inkstitch --extension=zip --format-pes=True input.svg > output.zip
```

- Timeout : 300s (configurable via `INKSTITCH_TIMEOUT`)
- Extrait le premier `.pes` du ZIP stdout

### 5b. Export multi-format (profil machine)

**Fichier :** `conversions/services/inkstitch.py` → `convert_pes_to_format(pes_path, 'DST'|'JEF'|'VP3')`

Si `machine_format != PES` : `pyembroidery.read(pes)` → `pyembroidery.write(pattern, .dst/.jef/.vp3)`. Le PES intermédiaire reste la source de vérité pour la preview et les métadonnées (DST ne stocke pas les couleurs). En cas d'échec d'export, le PES est conservé comme output. `JobDownloadView` dérive l'extension du fichier réel.

### 6. Preview et métadonnées

**Fichier :** `conversions/services/previews.py`

- `generate_pes_preview()` : renderer Pillow custom — itère sur `pattern.stitches`, dessine uniquement les `STITCH` (cmd=0), ignore `JUMP`/`TRIM`/`END`. Pas de lignes parasites entre blocs. Couleurs extraites du threadlist filtré (sans COLOR_BREAK blancs PES v1). Mise à l'échelle ≤ 1200px, linewidth=3.
- `extract_pes_metadata()` + `_compute_quality_score()` :
  - Filtre les COLOR_BREAK « White » PES v1 avant de compter les fils
  - Score 0-100 sur 7 critères (voir § Scoring)

---

## Score qualité broderie

### Critères (7 pondérés)

| Critère | Poids | Seuils clés |
|---------|-------|-------------|
| Fils | 18% | ≤7 idéal (100), ≤10 machine (60), ≤15 difficile (25), >15 impossible (0) |
| Points | 18% | 2k-50k excellent (100), <500 pauvre (20), >500k dépasse limite (0) |
| Dimensions | 14% | Dans zone 360×200mm (100), hors zone (55 ou 0) |
| Sauts | 10% | <0.5% excellent (100), <2% normal (80), <8% mauvais (45), ≥8% critique (10) |
| Densité | 10% | 1-20 pts/mm² optimal (100), <0.3 presque vide (20), >50 très dense (15) |
| Fidélité couleurs | 18% | Distance Lab SVG→PES : 100 - (Δ Lab × 1.2) × ratio fils |
| Couverture vectorisation | 12% | Couleurs obtenues / couleurs demandées (N/A pour SVG direct) |

### Gate critique

- Si min(stitches_score, fidelity_score, coverage_score) < 20 → score capé à 40
- Si min(...) < 40 → score capé à 65

### Labels

| Score | Label | Badge DaisyUI |
|-------|-------|---------------|
| ≥85 | Excellent | success |
| ≥70 | Bon | info |
| ≥50 | Acceptable | warning |
| <50 | Problématique | error |

---

## Filtrage COLOR_BREAK PES v1

PES v1 insère un fil « White » neutre entre chaque vraie couleur (COLOR_BREAK marker). Ce pattern d'alternance strict (Couleur-Blanc-Couleur-Blanc...) est détecté automatiquement par `_filter_pes_v1_color_breaks()` et filtré avant le scoring et l'affichage UI.

Sans ce filtrage, un design 10 couleurs apparaîtrait comme 19 fils (score fils très dégradé).

---

## Palette Brother

**Fichier :** `conversions/services/thread_color.py`

Localisation automatique de `InkStitch Brother Embroidery.gpl` :
1. Via `INKSTITCH_EXECUTABLE` (remontée depuis le bundle)
2. Chemins standards macOS/Linux

Si absent → snap désactivé silencieusement (log WARNING).

---

## Machine cible

**Brother entrepreneur pro X PR1050X**

| Contrainte | Valeur | Conséquence dans le pipeline |
|---|---|---|
| Aiguilles | 10 (idéal ≤7) | `force_max_svg_colors(10)` |
| Zone broderie | 360×200mm | Alerte score dimensions |
| Format natif | PES v1 | `--format-pes=True` |
| Vitesse estimée | ~600 pts/min | `time_minutes = stitches / 600` |

---

## Dépendances externes

| Outil | Rôle | Requis |
|-------|------|--------|
| Ink/Stitch CLI | SVG → PES | Oui |
| Inkscape CLI | Simplification SVG, trace | Optionnel (fallback) |
| VTracer CLI | Vectorisation PNG → SVG | Optionnel (vendor/vtracer) |
| potrace | Vectorisation logos multi-couleurs | Optionnel (brew install potrace) |
| rembg | Suppression fond IA | Optionnel (fallback Pillow) |
| pdf2image + poppler | PDF scanné → PNG | Optionnel |
| pyembroidery | Lecture PES + preview PNG | Oui |

---

## Fichiers clés

| Fichier | Rôle |
|---------|------|
| `conversions/tasks.py` | Orchestrateur Celery (pipeline complet) |
| `conversions/services/png_processing.py` | Vectorisation raster → SVG |
| `conversions/services/svg_utils.py` | Post-traitement SVG (filtrage, reorder, fusion, stroke-fix) |
| `conversions/services/thread_color.py` | Snap couleurs → palette Brother |
| `conversions/services/previews.py` | Preview PNG + score qualité |
| `conversions/services/inkstitch.py` | Intégration CLI Ink/Stitch |
| `conversions/services/pdf_processing.py` | Extraction PDF vectoriel |
| `conversions/services/validation.py` | Validation structure SVG |

---

## Éditeur SVG avancé (Phase 11)

L'éditeur permet de modifier le SVG vectorisé **avant** la conversion finale Ink/Stitch. Toutes les modifications se font in-place sur le fichier `vectorized_svg_file`.

### Opérations disponibles

| Opération | Route | Fonction service |
|-----------|-------|-----------------|
| Supprimer une couleur | `POST /<uuid>/svg/remove-color/` | `remove_excluded_colors_from_svg()` |
| Fusionner deux couleurs | `POST /<uuid>/svg/merge-colors/` | `merge_svg_colors()` |
| Remapper vers palette Brother | `POST /<uuid>/svg/change-color/` | `change_svg_color()` |
| Réordonner les couches | `POST /<uuid>/svg/reorder-colors/` | `reorder_svg_colors()` |
| Changer type de point | `POST /<uuid>/svg/set-stitch-type/` | `set_stitch_type()` |
| Régler la densité | `POST /<uuid>/svg/set-density/` | `set_stitch_density()` |
| Annuler (undo) | `POST /<uuid>/svg/undo/` | `undo_svg()` |
| Rétablir (redo) | `POST /<uuid>/svg/redo/` | `redo_svg()` |
| Valider → PES | `POST /<uuid>/svg/validate/` | `finalize_svg_to_pes.delay()` |

### Attributs Ink/Stitch injectés dans le SVG

| Paramètre | Attribut SVG | Valeurs |
|-----------|-------------|---------|
| Type de point (contour) | `inkstitch:stroke_method` | `running_stitch` |
| Densité | `inkstitch:row_spacing_mm` | `0.20` → `1.00` (défaut `0.40`) |

Le namespace `http://inkstitch.org/namespace` est déclaré automatiquement sur l'élément `<svg>` racine lors de la première injection d'attributs Ink/Stitch.

### Historique undo/redo

Avant chaque opération d'édition, un snapshot du SVG est sauvegardé dans `media/conversions/snapshots/{job_id}/snap_N.svg`. Le stack (max 20 niveaux) est stocké dans `ConversionJob.conversion_metadata['svg_history']` :
```json
{"past": ["conversions/snapshots/.../snap_0.svg", ...], "future": []}
```

---

*Dernière mise à jour : Phase 8e/13a — stabilisation Ink/Stitch (close_open_paths, namespace, purge fill_method) + profil machine (max_threads, hoop, export multi-format)*
