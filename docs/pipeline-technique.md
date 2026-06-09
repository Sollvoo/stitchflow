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
           1. validate_svg_content()
           2. remove_background_fill()        ← raster seulement
           3. filter_micro_paths()
           4. reorder_svg_paths_for_minimal_jumps()
           5. group_paths_by_color()
           6. scale_svg_to_width_mm()         ← si target_width_mm défini
           7. force_max_svg_colors(max=10)
           8. snap_svg_colors_to_brother_palette()
           9. group_paths_by_color()          ← bis après fusion
          10. normalize_stroke_only_paths()
                        │
                        ▼
              convert_svg_to_pes()  [Ink/Stitch CLI]
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
| 1 | `validate_svg_content()` | Vérifie éléments brodables (path/rect/circle...) avec fill ou stroke |
| 2 | `remove_background_fill()` | Supprime fills blanc (L*>92) couvrant >85% viewBox. ⚠️ Seulement pour raster, pas SVG direct. Ne supprime pas les shapes avec >12 segments SVG (formes de design). |
| 3 | `filter_micro_paths()` | Supprime paths < 0.5 mm² (bruit vectorisation) |
| 4 | `reorder_svg_paths_for_minimal_jumps()` | Greedy nearest-neighbor sur centroids → minimise sauts |
| 5 | `group_paths_by_color()` | Regroupe paths plats (VTracer) par couleur → moins de changements fil |
| 6 | `scale_svg_to_width_mm()` | Redimensionne à target_width_mm (ratio conservé) |
| 7 | `force_max_svg_colors(10)` | Fusionne itérativement couleurs Lab les plus proches → ≤10 fils (Brother PR1050X) |
| 8 | `snap_svg_colors_to_brother_palette()` | Snappe fill + stroke → fil Brother le plus proche (CIE Lab). Palette : InkStitch Brother Embroidery.gpl |
| 9 | `group_paths_by_color()` | Re-groupement après fusion couleurs |
| 10 | `normalize_stroke_only_paths()` | Convertit paths stroke-only (fill=none, stroke=#hex) en fill=#hex. Rend le texte vectorisé brodable. |

**Ordre critique :** `force_max_colors` AVANT `snap` (réduction d'abord, snap sur couleurs réduites = plus précis).

### 5. Conversion Ink/Stitch

**Fichier :** `conversions/services/inkstitch.py`

```bash
inkstitch --extension=zip --format-pes=True input.svg > output.zip
```

- Timeout : 300s (configurable via `INKSTITCH_TIMEOUT`)
- Extrait le premier `.pes` du ZIP stdout

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

*Dernière mise à jour : Phase 6 — corrections qualité + paramètres adaptatifs*
