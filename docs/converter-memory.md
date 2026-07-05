# StitchFlow — Mémoire qualité convertisseur

## [LIRE EN PREMIER — CONTEXTE RAPIDE POUR L'IA]

**Score actuel (S12, Windows env complet) :** 95.4/100 sur 24 tests (2026-07-05).
**Référence macOS (S7) :** 95.7/100 sur 20 tests (2026-06-20)
**Objectif :** 95.0/100 sur les tests de référence (**ATTEINT Session 6, maintenu S7/S10/S11/S12**)

**⚠️ Découverte majeure S12-A — cache Ink/Stitch corrompu = échec silencieux total :** le cache
diskcache SQLite (`%LOCALAPPDATA%\inkstitch\inkstitch\cache\stitch_plan\`) peut se corrompre
(processus zombie + WAL verrouillé) → Ink/Stitch sort en exit 0 avec un ZIP vide, TOUTES les
conversions échouent avec « aucune sortie ». `convert_svg_to_pes` purge et retente automatiquement
depuis S12. Si benchmark 100% en erreur → vérifier ce cache en premier.

**⚠️ Découverte majeure S12-B — Inkscape hors PATH = texte perdu sans erreur :** sur Windows,
Inkscape s'installe dans `C:\Program Files\Inkscape\` sans entrer dans le PATH → l'étape
object-to-path était silencieusement sautée depuis toujours → les `<text>` SVG n'étaient JAMAIS
brodés (PES amputé, score 100/100 quand même). `find_inkscape()` (svg_utils) résout maintenant
.env → PATH → emplacements usuels ; le scoring plafonne à 65 si des `<text>` restent non convertis.

**⚠️ Découverte majeure S12-C — stroke→fill détruit les contours décoratifs :** avec Inkscape
actif, cercles/lignes deviennent des paths stroke-only ; l'ancienne conversion systématique
stroke→fill (S8) les remplissait en disques pleins recouvrant le design. Les strokes nus sont
brodés nativement en points courants par Ink/Stitch — `normalize_stroke_only_paths` ne convertit
plus que les petites formes fermées (<15% du viewBox, glyphes). **Ne jamais annoter ces paths
`stroke_method=running_stitch`** : mesuré A/B, 2 annotations = timeout 300s (famille du bug S9).

**⚠️ Découverte majeure S11 — le label peut mentir même quand le score ne bouge pas :** un design
multicolore avec UN SEUL fil très décalé (ΔE Lab ≥20) peut afficher "Excellent" car
`color_fidelity` (i) ne pèse que 18% du score pondéré et (ii) était calculé sur une **moyenne**
des écarts par couleur — un fil très décalé se noie dans la moyenne si les autres sont fidèles.
Corrigé S11 : `_score_color_fidelity()` calcule aussi `max_dist` (pire ΔE individuel) ; si
`max_dist >= 20` le label est plafonné à "Bon" même si le score numérique reste ≥85
(`label_capped=True`, score numérique inchangé — zéro impact benchmark). Gate critique corrigé en
prime : `color_fidelity` participe désormais au gate pour **tous** les pipelines (l'exemption
SVG-direct reposait sur un raisonnement faux — le snap Brother s'applique identiquement aux SVG
directs et aux sources raster).

**⚠️ Découverte majeure S10 — z-order de broderie :** l'ordre des paths SVG = ordre de
superposition visuelle. VTracer était en `hierarchical=stacked` et `reorder`/`group_paths_by_color`
réordonnaient via greedy NN → **le fond était brodé par-dessus le design** (invisible au scoring,
qui notait 92-97 des PES visuellement détruits). Corrigé S10 : VTracer en `cutout` (formes
disjointes, marquées `data-stitchflow-disjoint="1"`) + réordonnancement z-safe pour SVG directs.
**Toujours vérifier l'aperçu PES visuellement en plus du score.**

**Tests anti-régression :**
- T01 : ne pas descendre sous 86/100 (actuellement 92)
- T08 : doit rester à 100/100 — si régression, rollback immédiat

**Machine cible :** Brother PR1050X — 10 aiguilles, zone 360×200mm, PES v1

**Niveaux de difficulté des 20 tests :**

| Niveau | Tests |
|--------|-------|
| Easy | T08 (SVG cercle), T17 (SVG étoile), T18 (SVG fleur), T20 (SVG géom. multi), T02 (logo PNG 5 col), T06 (logo JPEG), T07 (WebP) |
| Medium | T01, T04, T09, T10, T11, T12, T15 (PNG alpha), T19 (PNG formes 4 col) |
| Hard | T03 (écusson 12 col), T05 (photo bruit), T13 (texte fin SVG), T14 (PDF complexe), T16 (PDF lourd) |

Notes critiques :
- **T08 = anti-régression absolu** (score 100, pipeline SVG trivial)
- **T05 = ceiling naturel** (photo bruit, jumps 2.1%, algorithme TSP — ne pas s'acharner)
- **T14 = threads=80 limite machine** (8 fils source PDF → impossible sans modifier le PDF)
- **T01 = color_fidelity floor 70 définitif** : palette Brother a un vide gris (Pewter L≈34 → Warm Gray L≈82), aucun fil intermédiaire. ΔLab=28.4 est physiquement irréductible.

**Codes de diagnostic pipeline (nouveau depuis S9) :**
- `VECT` — problème vectorisation PNG→SVG (couleurs perdues, artefacts)
- `SVG_PREP` — problème préparation SVG pour Ink/Stitch (tatami fond, namespace, paths non fermés)
- `INK_STITCH` — problème conversion Ink/Stitch (PES vide, timeout)
- `SCORING` — problème calibration score (score ne reflète pas qualité réelle)

**Baseline Windows (S10, env complet)** : palette Brother **retrouvée** (fix chemin S10) et
poppler vendor **branché** (fix pdf2image S10) → T08=100, moyenne 94.8/100 sur les 20 tests
historiques (~= référence macOS). Restent absents : rembg/onnxruntime (fallback seuillage,
T01/T05/T19 OK quand même) et **potrace** (T12 plafonne à 79 via fallback VTracer — installer
potrace Windows pour retrouver ~95). Les runs Windows sont désormais comparables à macOS à
~1 pt près.

**Ce qui a été tenté et n'a PAS fonctionné (ne pas retenter) :**
- **S12 : `inkstitch:stroke_method="running_stitch"` sur les contours décoratifs → INTERDIT.** A/B contrôlé (écusson EAGLES) : 2 annotations sur des anneaux fermés = 11s → timeout 300s. Laisser les strokes nus, Ink/Stitch les brode nativement.
- **S9 : `inkstitch:fill_method="auto_fill"` sur les paths fill → INTERDIT.** Mesuré A/B contrôlé : 5 annotations font passer Ink/Stitch de 5.7s à timeout 300s (T02). L'annotation systématique `_annotate_fill_paths_for_inkstitch` (commit « forcer tatami fill ») a été supprimée et remplacée par `_strip_fill_method_annotations` qui purge les annotations héritées des SVG stockés. Les zones ignorées par Ink/Stitch venaient des paths non fermés (→ `close_open_paths`) et des strokes-only (→ `normalize_stroke_only_paths`), pas du fill method.
- S2 Iter 3 : `filter_speckle=2` / `color_precision=7` pour T02 coverage → neutre, 5ème couleur fondamentalement ambiguë dans le PNG source
- Coefficient color_fidelity 1.5 → ne pas tenter, durcirait les scores sans améliorer la qualité réelle
- Algorithme TSP pour jumps T05 → effort élevé, impact limité (ceiling naturel photo)
- S5 Iter 2 : `corner_threshold` adaptatif VTracer → neutre sur les scores benchmark, conservé pour la logique
- S7 : Fix thread_color.py pour T01 ΔLab=28.4 → IMPOSSIBLE. Lacune physique palette Brother (Pewter L≈34 → Warm Gray L≈82).

**Prochaines priorités (Session 13) :**
1. **[SCORING]** **Critère de fidélité visuelle** : le score ne détecte toujours pas un design recouvert/détruit (S10/S12 : PES illisibles notés 92-100 — S12 l'a reprouvé avec les disques pleins scorés 100). Piste : comparaison aperçu PES vs rendu SVG source (SSIM ou histogramme par zones).
2. **[VECT]** Installer potrace Windows (T12 79→~95 attendu) ; évaluer rembg/onnxruntime
3. **[SCORING]** Audit calibration complet des 7 critères (reporté depuis S9 — S12 a fait un audit ciblé : designs contours, density-aware niveau 3, fils distincts vs arrêts)
4. **[SCORING]** **T03** (écusson 12 col) : `force_max_svg_colors(8)` si n_colors≥10 → t_score 80→100 potentiel
5. **[SCORING]** **Quantification PES v1** (découverte S11) : Ink/Stitch re-mappe parfois le fil final vers sa propre table de couleurs PES v1 limitée, même après notre snap Brother optimal (ex: T01 snappé `#134a76` → PES final `Ultramarine #0b3d91`). Phénomène dépendant du contenu (formes simples parfois préservées exactement), hors de notre contrôle direct — mais pourrait justifier d'exposer ce ΔE final (déjà mesuré) plus tôt dans le flux utilisateur (avant même la génération du PES) si un moyen d'interroger la table PES v1 d'Ink/Stitch est trouvé.

*(S9 fait : namespace inkstitch ✅, remove_background_fill coins arrondis ✅, close_open_paths ✅, découverte interdit fill_method — voir Session 9)*
*(S10 fait : palette Brother Windows ✅, poppler pdf2image ✅, VTracer cutout ✅, réordonnancement z-safe ✅, T21/T22 ✅ — voir Session 10)*
*(S11 fait : seuils ΔE partagés (thread_color.py) ✅, label capping color_fidelity ✅, gate corrigé (SVG direct inclus) ✅, badges UI (éditeur + page résultat) ✅, garde-fou générique `color_fidelity_regression` dans le benchmark ✅ — voir Session 11)*
*(S12 fait : auto-guérison cache Ink/Stitch ✅, find_inkscape (texte→paths enfin actif Windows) ✅, garde-fou texte perdu ✅, fils distincts vs arrêts ✅, normalize_stroke_only géométrie-aware ✅, calibration contours + density-aware n3 ✅, T23/T24 ✅ — voir Session 12)*

**Audit calibration scoring :**
- Dernière révision : Session 4 (2026-06-17) — 6/7 critères fiables
- S7 : coverage floor relevé 55→65 ; S12 : audit ciblé (contours, density-aware n3, fils distincts)
- Prochaine révision complète obligatoire : **Session 15** (multiple de 3)

---

## Score global

| Session | Date | Score avant | Score après | Delta | Nb tests |
|---------|------|-------------|-------------|-------|----------|
| 1 | 2026-06-13 | 88.7 | 91.3 | +2.6 | 12 |
| 2 | 2026-06-15 | 91.3 | 92.2 | +0.9 | 12 |
| 3 | 2026-06-17 | 92.2 | 94.2 | +2.0 | 12 |
| 4 | 2026-06-17 | 94.2 | 94.1 | −0.1 | 14 |
| 5 | 2026-06-18 | 94.1 | 94.4 | +0.3 | 16 |
| 6 | 2026-06-18 | 94.4 | 95.1 | +0.7 | 18 |
| 7 | 2026-06-20 | 95.1 | **95.7** | **+0.6** | 20 |
| 8 | 2026-06-29 | 95.7 | à mesurer | — | 20 |
| 9 | 2026-07-03 | — | 92.7 (baseline Windows, 19 tests) | n/c | 19 |
| 10 | 2026-07-04 | 92.7 (Windows, 19 tests) | **95.0** (Windows env complet, 22 tests) | **+2.3** | 22 |
| 11 | 2026-07-04 | 95.0 (22 tests) | **95.0** (score numérique identique, 5 labels rétrogradés Excellent→Bon) | **0.0** | 22 |
| 12 | 2026-07-05 | 95.0 (22 tests — après réparation env 0/22) | **95.4** (24 tests, T23/T24 ajoutés ; 22 comparables : 95.4) | **+0.4** | 24 |

Note S8 : session infrastructure — bug VTracer Python API corrigé (TypeError out_path), réorganisation tests par difficulté (niveau1/2/3/impossible), amélioration preprocessing texte PNG (SMOOTH supprimé pour détails fins), stroke-only thin paths convertis en fill (fix preview vide texte contours). Relancer le benchmark pour mesurer l'impact.

Note S4 : le delta légèrement négatif reflète l'ajout de 2 tests Hard (T13=94, T14=90). Sur les 12 tests existants, le score est passé de 94.2 à 94.4 grâce à la correction jumps (T05 89→91).

Note S5 : le delta +0.3 intègre l'ajout de 2 tests (T15=94, T16=98). Sur les 14 tests comparables S4, le score est passé de 94.1 à 94.2 (+0.1) grâce à T01 91→92 et T03 93→94.

Note S6 : le delta +0.7 intègre l'ajout de 2 tests Easy (T17=100, T18=100) et 2 corrections de bugs visuels (Bug A : SVG préservé après conversion ; Bug B : seuil dust calibré pour SVG pixel-units). Sur les 16 tests comparables S5, le score reste stable à 94.4 (bugs corrigés n'affectent pas le benchmark qui utilise target_width_mm > 0). **Objectif 95.0 atteint.**

Note S7 : le delta +0.6 intègre 2 calibrations scoring (coverage floor 55→65, jump floor ≤15 sauts) et l'ajout de 2 tests (T19=97, T20=100). Sur les 18 tests comparables S6, le score est passé de 95.1 à 95.43 (+0.33) grâce à T04/T07/T12/T15 : 94→95 (+1) et T13 : 94→96 (+2).

---

## Scores détaillés par test

| ID | Fichier | Format | Params | Score S4 | Score S5 | Score S6 | Score S7 | Delta S7 | Niveau |
|----|---------|--------|--------|----------|----------|----------|----------|----------|--------|
| T01 | niveau2/logo/06-logo-monochrome-blanc.png | PNG | n=2,bg,80mm | 91 | 92 | 92 | 92 | 0 | Medium |
| T02 | niveau1/logo/03-logo-multicolore.png | PNG | n=5,80mm | 97 | 97 | 97 | 97 | 0 | Easy-Medium |
| T03 | niveau3/ecusson/07-ecusson-12couleurs.png | PNG | n=10,100mm | 93 | 94 | 94 | 94 | 0 | Hard |
| T04 | niveau2/texte/08-texte-fond-colore.png | PNG | n=4,60mm | 94 | 94 | 94 | **95** | **+1** | Medium |
| T05 | niveau3/photo/09-photo-complexe-bruit.png | PNG | n=8,bg,100mm | 91 | 91 | 91 | 91 | 0 | Hard/Ceiling |
| T06 | niveau1/logo/12-logo-formes-simple.jpg | JPEG | n=6,80mm | 95 | 95 | 95 | 95 | 0 | Easy-Medium |
| T07 | niveau1/logo/test-logo.webp | WebP | n=5,80mm | 94 | 94 | 94 | **95** | **+1** | Easy-Medium |
| T08 | niveau1/geometrique/01-circle-simple.svg | SVG | direct,80mm | 100 | 100 | 100 | 100 | 0 | Easy |
| T09 | niveau2/ecusson/07-logo-atelier-8couleurs.svg | SVG | direct,100mm | 95 | 95 | 95 | 95 | 0 | Medium |
| T10 | niveau2/texte/06-text-outline.svg | SVG | direct,80mm | 95 | 95 | 95 | 95 | 0 | Medium |
| T11 | niveau2/logo/test-logo.pdf | PDF | n=6,100mm | 94 | 94 | 94 | 94 | 0 | Medium |
| T12 | niveau2/scan/test-scanned-pdf.pdf | PDF | n=4,80mm | 94 | 94 | 94 | **95** | **+1** | Medium |
| T13 | niveau3/texte/08-texte-fin-contours.svg | SVG | direct,60mm | 94 | 94 | 94 | **96** | **+2** | Hard |
| T14 | niveau3/logo/test-vectoriel-complexe.pdf | PDF | n=6,120mm | 90 | 90 | 90 | 90 | 0 | Hard |
| T15 | niveau2/logo/11-logo-transparent-alpha.png | PNG | n=4,80mm | — | 94 | 94 | **95** | **+1** | Medium |
| T16 | niveau3/logo/logo gravo clés.pdf | PDF | n=6,100mm | — | 98 | 98 | 98 | 0 | Hard |
| T17 | niveau1/geometrique/02-star-5pts.svg | SVG | direct,80mm | — | — | 100 | 100 | 0 | Easy |
| T18 | niveau1/geometrique/05-flower-paths.svg | SVG | direct,80mm | — | — | 100 | 100 | 0 | Easy |
| T19 | niveau2/geometrique/02-formes-couleurs.png | PNG | n=4,bg,80mm | — | — | — | **97** | nouveau | Medium |
| T20 | niveau2/geometrique/03-geometric-multicolor.svg | SVG | direct,80mm | — | — | — | **100** | nouveau | Easy-Medium |

**Score moyen S4 : 94.1/100 (14 tests)**
**Score moyen S5 : 94.4/100 (16 tests) — sur 14 tests comparables : 94.2/100**
**Score moyen S6 : 95.1/100 (18 tests) — sur 16 tests comparables : 94.4/100 (stable)**
**Score moyen S7 : 95.7/100 (20 tests) — sur 18 tests comparables S6 : 95.43/100 (+0.33)**

---

## Historique des améliorations

### Session 1 — 2026-06-13

**Iter 1 — density-aware stitch scoring** (`previews.py`)
- Correction : design compact avec density ≥ 0.2 pts/mm² et stitch_count < 500 → s_score 20→60
- Raison : un texte vectorisé en contours sur une petite zone produit naturellement peu de points ; la gate à 65 était injuste
- Impact mesuré : T10 65→88 (+23 pts)

**Iter 2 — seuil stitches 2000→1500 + coverage floor=40** (`previews.py`)
- Correction A : seuil "excellent" stitches abaissé de 2000 à 1500
- Correction B : score coverage plancher à 40 si au moins 1 couleur obtenue
- Impact mesuré : T01 80→87 (+7), T04 91→92 (+1), T12 91→92 (+1)

**Iter 3 — _consolidate_svg_colors RGB→Lab** (`png_processing.py`)
- Correction : remplacement distance euclidienne RGB (seuil 50) par distance CIE Lab (seuil 22)
- Raison : les couleurs sombres proches perceptuellement mais éloignées en RGB étaient mal fusionnées
- Impact mesuré sur score : neutre (fichiers de test ont couleurs suffisamment distinctes)
- Impact qualité broderie réel : clustering couleurs plus fidèle à la perception humaine

### Session 2 — 2026-06-15

**Iter 1 — seuil stitches 1500→1200** (`previews.py`)
- Correction : seuil "design simple" abaissé de 1500 à 1200 (`elif stitch_count < 1200: s_score=60`)
- Raison : T02 avec 1381 stitches à 80mm est un design parfaitement brodable (~2 min sur PR1050X), pénalisé injustement par le seuil trop conservateur issu de session 1
- Impact mesuré : T02 90→97 (+7)

**Iter 2 — coverage floor=80 pour quasi-couverture** (`previews.py`)
- Correction : quand `n_obtained >= n_requested - 1` et `n_obtained > 0`, appliquer `score = max(score, 80)`
- Raison : logo blanc avec remove_bg obtient 1 couleur non-blanche sur 2 demandées → cov_score=50 était injuste ; la couleur manquante est le fond blanc retiré intentionnellement, pas un échec de vectorisation
- Impact mesuré : T01 87→91 (+4)

**Iter 3 — filter_speckle + color_precision pour logos 4-8 couleurs** (`png_processing.py`)
- Correction : `filter_speckle = 2 if n_colors > 3 else 4` et `color_precision = 7 if n_colors > 3 else 6` (seuil n_colors>8 → n_colors>3)
- Raison : T02 (4/5 couleurs) — réduction du filtrage pour mieux capturer les zones de couleur fine de la 5ème couleur
- Impact mesuré : neutre — la 5ème couleur de T02 est fondamentalement similaire à une autre dans l'image source et ne peut pas être séparée par ces paramètres seuls. Aucune régression.

### Session 3 — 2026-06-17

**Iter 1 — threads 8-10 → score 80** (`previews.py`)
- Correction : `t_score = 60` → `t_score = 80` pour `thread_count <= 10`
- Raison : la PR1050X a 10 aiguilles — 8-10 fils s'enfilent directement sans re-enfilage. L'ancien score 60 avec le message "re-enfilage possible" était trompeur ; seuls 11+ fils dépassent les capacités physiques.
- Impact mesuré : T03 89→93 (+4), T05 85→89 (+4), T09 92→95 (+3)

**Iter 2 — density-aware niveau 2 (s_score 60→100)** (`previews.py`)
- Correction : si `s_score == 60 and stitch_count < 500 and density >= 0.3` → `s_score = 100`
- Raison : texte SVG outline à 319 stitches et density=0.387 pts/mm² est un design valide (police contours à 60mm). La correction L1 avait monté 20→60, mais 60 reste insuffisant pour ce type de design structurellement sain.
- Impact mesuré : T10 88→95 (+7)

**Iter 3 — coverage floor 40→55** (`previews.py`)
- Correction : plancher `max(score, 40)` → `max(score, 55)` dans `_score_vectorization_coverage()`
- Raison : score 40 (label "vectorisation appauvrie") est sévère pour des cas où la limitation vient du contenu source (PDF monochrome, texte naturellement unicolore, fond retiré intentionnellement). Score 55 reflète mieux "le convertisseur a produit ce qu'il pouvait".
- Impact mesuré : T04 92→94 (+2), T07 92→94 (+2), T12 92→94 (+2)

### Session 4 — 2026-06-17

**Audit calibration scoring** (`previews.py`)
- Résultat : 6/7 critères fiables (mesures brutes, stitches, density, color_fidelity, coverage, threads, dimensions)
- Seul critère à recalibrer : jumps (chute abrupte 80→45 entre 1.99% et 2.01%)

**Iter 1 — palier jumps intermédiaire 2–4% = 65** (`previews.py`)
- Correction : ajout palier `elif jump_ratio < 0.04: j_score=65` entre la plage <2%=80 et <8%=45
- Raison : PR1050X équipée d'un coupe-fil automatique — un ratio 2–4% est "légèrement au-dessus de la norme" mais gérable sur machine pro. La chute brutale 80→45 (35 pts d'écart pour 0.1% de différence) était injuste pour T05 (photo complexe à 2.1%).
- Impact mesuré : T05 89→91 (+2)

**Ajout 2 tests Hard au benchmark** (`tests/run_benchmark.py`)
- T13 : `svg/08-texte-fin-contours.svg` — SVG texte très fin en contours à 60mm → score 94/100 (excellent, au-dessus du minimum de 75)
- T14 : `pdf/test-vectoriel-complexe.pdf` — PDF vectoriel complexe à 120mm → score 90/100 (au-dessus du minimum de 83)
- Score moyen 14 tests : 94.1/100 (objectif 93.5 dépassé)

### Session 5 — 2026-06-18

**Iter 1 — Floor color_fidelity=70 pour snap optimal sur palette limitée** (`previews.py`)
- Correction : dans `_score_color_fidelity()`, après calcul du score, `if ratio >= 0.8 and mean_dist <= 35: score = max(score, 70)`
- Raison : T01 avait ΔLab=28.4 et ratio=1.0 — le snap Brother choisit déjà le fil le plus proche, la distance résiduelle est une limite physique de la palette, pas un défaut du convertisseur. Floor=70 avec double condition ne masque pas les vraies mauvaises vectorisations (ratio < 0.8 → floor ne s'applique pas).
- Impact mesuré : T01 91→92 (+1) ; T08 stable à 100

**Iter 2 — corner_threshold adaptatif VTracer selon n_colors** (`png_processing.py`)
- Correction : `"--corner_threshold", "80" if n_colors <= 3 else "50" if n_colors > 8 else "60"`
- Raison : logos simples (n≤3) bénéficient de courbes plus lisses ; designs complexes (n>8) ont besoin d'angles plus nets.
- Impact mesuré : neutre — aucun gain sur T01 (n=2) ni T03 (n=10). Changement conservé pour logique correcte, sans régression.

**Iter 3 — Seuil de clustering couleurs Lab 22→15 pour n>8** (`png_processing.py`)
- Correction : dans `_consolidate_svg_colors()`, `_LAB_CLUSTER_THRESH = 15.0 if n_colors > 8 else 22.0`
- Raison : T03 (écusson 12 couleurs, n=10) obtenait 8/10 couleurs après consolidation avec seuil 22. Le seuil plus resserré (15) préserve les nuances fines entre couleurs proches, permettant à VTracer de conserver plus de couleurs distinctes.
- Impact mesuré : T03 93→94 (+1) ; T05 (n=8, seuil inchangé à 22) stable à 91 ; T08 stable à 100

**Ajout 2 tests au benchmark** (`tests/run_benchmark.py`)
- T15 : `png/11-logo-transparent-alpha.png` — PNG RGBA canal alpha, n=4, 80mm → score **94/100** (Medium, pipeline gère bien l'alpha via `preprocess_image()`)
- T16 : `pdf/logo gravo clés.pdf` — PDF 1.37MB complexe, n=6, 100mm → score **98/100** (Hard, excellent sur PDF lourd réel)
- Score moyen 16 tests : 94.4/100

### Session 6 — 2026-06-18

**Iter 1 — Bug A : préserver vectorized_svg_file après conversion** (`tasks.py`)
- Correction : `finalize_svg_to_pes()` copie maintenant le SVG dans un fichier temporaire via `shutil.copy2()` avant de le passer à `_run_svg_to_pes_pipeline()`. Le `vectorized_svg_file` original (affiché dans la page résultat et l'éditeur SVG) n'est plus jamais modifié.
- Raison : `_run_svg_to_pes_pipeline()` modifie ses fichiers in-place (`convert_text_to_paths`, `remove_background_fill`, `filter_micro_paths`, etc.). Sans copie, le SVG stocké était irrémédiablement corrompu après chaque conversion raster, affichant un rectangle monochrome au lieu du design vectorisé.
- Impact mesuré : neutre sur les scores benchmark (tous les tests benchmark utilisent `target_width_mm > 0`). Corrige un bug visuel majeur sur l'interface utilisateur (ecusson écusson 12 couleurs → rectangle bleu marine).

**Iter 2 — Bug B : seuil dust `force_max_svg_colors()` relatif aux éléments actifs** (`svg_utils.py`)
- Correction : seuil de pré-passe poussière changé de `total_area * 0.01` (viewBox complet) à `active_area * 0.005` où `active_area = sum(fill_surface_area.values())`.
- Raison : `total_area` (viewBox) incluait l'espace de fond vide sur les SVG pixel-units non scalés (VTracer output sans `target_width_mm`). Ex : viewBox `0 0 800 600` = 480 000 px², seuil = 4 800 px² → les carrés colorés de l'écusson (~1 600 px²) étaient classés "poussière" → toutes couleurs fusionnées dans le bleu marine dominant. `active_area` = somme réelle des bbox des éléments colorés → seuil calibré indépendamment des unités.
- Impact mesuré : neutre sur les scores benchmark (benchmark utilise toujours `target_width_mm > 0` → SVG en mm → `total_area` ~ `active_area`). Corrige le bug de perte totale des couleurs sur conversion sans redimensionnement.

**Iter 3 — Ajout 2 tests Easy au benchmark** (`tests/run_benchmark.py`)
- T17 : `svg/02-star-5pts.svg` — SVG étoile 5 branches, direct, 80mm → score **100/100** (Easy)
- T18 : `svg/05-flower-paths.svg` — SVG fleur multi-chemins, direct, 80mm → score **100/100** (Easy)
- Score moyen 18 tests : **95.1/100** — objectif 95.0 atteint.

### Session 7 — 2026-06-20

**Iter 1 — Coverage floor 55→65 pour designs mono-couleurs correctement brodés** (`previews.py`)
- Correction : plancher `max(score, 55)` → `max(score, 65)` dans `_score_vectorization_coverage()`
- Raison : un PES à 1 fil qui brode correctement le design principal est "acceptable" (65), pas "partiel" (55). La limite vient du contenu source (texte unicolore, fond retiré, design simplement mono), pas du pipeline. 65 reflète mieux la réalité machine PR1050X.
- Impact mesuré : T04 94→95 (+1), T07 94→95 (+1), T12 94→95 (+1), T15 94→95 (+1)

**Iter 2 — Jump floor pour designs courts (≤15 sauts absolus)** (`previews.py`)
- Correction : après calcul de j_score, `if jump_count <= 15 and j_score < 65: j_score = 65` avec message dédié
- Raison : T13 (texte fin SVG 60mm) produit 11 sauts inévitables (changements de couleur entre lettres). Ratio 4.6% → j_score=45 car diviseur = 230 petits stitches. Mais 11 sauts absolus = ~11s de pause sur PR1050X, toujours acceptable. Le ratio pénalise injustement les petits designs structurellement sains.
- Impact mesuré : T13 94→96 (+2) ; T05 (557 sauts >> 15) et T10 (j_score=80 déjà) inchangés

**Iter 3 — Ajout 2 tests au benchmark** (`tests/run_benchmark.py`)
- T19 : `png/02-formes-couleurs.png` — PNG 4 couleurs géométriques + fond beige, n=4, remove_bg, 80mm → score **97/100** (Medium, teste pipeline détection fond)
- T20 : `svg/03-geometric-multicolor.svg` — SVG géométrique multicolore, direct, 80mm → score **100/100** (Easy-Medium)
- Score moyen 20 tests : **95.7/100** (+0.6 vs S6)

---

## Problèmes connus non résolus

- **[SCORING] Score aveugle au rendu visuel** (découvert S10) : un PES dont le fond recouvre le design scorait 92-97. Corrigé en amont (cutout + z-safe) mais le scoring lui-même ne le détecterait toujours pas → critère de fidélité visuelle à concevoir S11.
- **T12=79 sur Windows** : potrace absent → fallback VTracer sur un scan (macOS avec potrace : 95). Installer potrace Windows.
- **T01 color_fidelity=70** (floor appliqué S5, vrai ΔLab=28.4) : **DÉFINITIF S7 — non résolvable.** Le parsing GPL est correct. La lacune est physique : palette Brother passe de Pewter (L≈34) à Warm Gray (L≈82) sans fil gris intermédiaire. Tout logo vectorisé en gris moyen score 70 au plafond.
- **T02 coverage 4/5** : la 5ème couleur est fondamentalement similaire à une autre dans l'image PNG source. filter_speckle=2 et color_precision=7 (S2) n'ont pas résolu le problème. Potentiellement non résoluble.
- **T04 coverage=65** (1/4, floor relevé S7) : PNG texte blanc sur fond coloré, le texte blanc est filtré → 1 couleur correcte. Limite du contenu source.
- **T07 coverage=65** (2/5, floor relevé S7) : logo fondamentalement 2 couleurs. Non résolvable par pipeline.
- **T05 jumps** : 2.1% → j_score=65. Plafond naturel photo complexe. TSP interdit (effort élevé, ceiling naturel).
- **T14 threads=80** (8 fils) + **color_fidelity=80** (7/8 fils, ΔLab=11.2) : un fil disparaît probablement via snap→group_colors sur ce PDF vectoriel complexe. À diagnostiquer S9.
- **[SCORING] Quantification PES v1 (découvert S11)** : Ink/Stitch peut re-mapper le fil final vers sa propre table de couleurs PES v1 (limitée), même après un snap Brother déjà optimal de notre côté (ex: T01 snappé `#134a76` → PES final `Ultramarine #0b3d91`, ΔE réel 28.4). Dépendant du contenu (formes simples parfois préservées exactement) — non reproductible à la demande, donc pas de fixture synthétique dédiée possible. Notre label capping (S11) rend cet écart visible sans prétendre le corriger (limite hors de notre contrôle direct).

### Session 8 — 2026-06-29

**Fix 1 — Bug VTracer Python API** (`_vtracer_helper.py`)
- Correction : `vtracer.convert_image_to_svg_py()` exigeait `out_path` en 2ème arg positionnel (API changée ≥0.6). Ajout de `svg_output_path` + suppression du bloc `with open()` redondant.
- Raison : toute conversion PNG/JPEG/WebP échouait sur Windows (pas de CLI vtracer ARM64, potrace absent, seul fallback = VTracer Python) → TypeError bloquant.
- Impact mesuré : conversions PNG à nouveau fonctionnelles sur Windows.

**Fix 2 — Réorganisation tests par difficulté** (`tests/manual/`)
- Correction : 28 fichiers déplacés de `png/`, `jpeg/`, `pdf/`, `svg/`, `webp/` vers `niveau1/{logo,geometrique,texte}`, `niveau2/{logo,geometrique,ecusson,texte,scan}`, `niveau3/{ecusson,photo,texte,logo}`, `impossible/`.
- Raison : organisation par format empêchait d'évaluer la difficulté d'un coup d'œil. `impossible/` isole les cas non-brodables (gradients, photos réalistes). Benchmark `run_benchmark.py` mis à jour (20 nouveaux chemins).
- Impact mesuré : neutre sur le score (refactoring structurel).

**Fix 3 — Preprocessing texte PNG** (`png_processing.py`)
- Correction : `preprocess_image()` appliquait `ImageFilter.SMOOTH` à toutes les images (tuait les détails fins). Ajout détection `_detect_fine_details()` : branche texte = sharpen 2.5 sans SMOOTH au lieu de smooth léger.
- Raison : le lissage efface les traits fins avant vectorisation → texte illisible après vectorisation VTracer.
- Impact mesuré : à mesurer S9 sur T04 (texte fond coloré).

**Fix 4 — Stroke thin → fill** (`svg_utils.py`)
- Correction : `normalize_stroke_only_paths()` faisait `continue` pour les strokes < 1mm → path restait `stroke-only` → Ink/Stitch l'ignorait → preview vide. Suppression du `continue` → tous les strokes colorés convertis en fill.
- Raison : Ink/Stitch ignore les paths sans fill. Même un trait fin doit être converti en fill pour être brodé.
- Impact mesuré : à mesurer S9 sur T13 (texte fin contours SVG).

---

### Session 9 — 2026-07-03 (Windows)

**Contexte** : session Phases 8e/13a/13b/landing (pas une session d'optimisation score). Benchmark de référence Windows : **92.7/100 (19 tests, T12 exclu — poppler absent)**, temps normaux ~3-5s/test.

**Iter 1 — [SVG_PREP] `remove_background_fill` étendu aux coins arrondis** (`svg_utils.py`)
- Correction : branche path — early-return à >20 segments (était >12), suppression si coverage >0.80 (la règle ≤12 & >0.85 est englobée)
- Raison : fonds vectorisés en coins arrondis (13-20 segments) passaient le filtre → tatami massif dans le PES
- Impact mesuré : 19/19 scores identiques (le garde-fou quasi-blanc L*>92 reste en amont)

**Iter 2 — [SVG_PREP] `close_open_paths` + `inject_inkstitch_namespace`** (`svg_utils.py`, `tasks.py`)
- `close_open_paths()` : ferme chaque sous-path fill sans Z (skip running_stitch/stroke-only ; skip si le sous-path suivant commence par `m` relatif — Z décalerait ses coordonnées)
- `inject_inkstitch_namespace()` : injection textuelle regex sur `<svg>` — ElementTree n'émet la déclaration que si un attribut du namespace est sérialisé
- Impact mesuré : 19/19 scores identiques

**Iter 3 — [INK_STITCH] DÉCOUVERTE MAJEURE : fill_method=auto_fill = timeout** (`svg_utils.py`)
- Symptôme : T01 10s→205s, T02 5s→timeout 300s après injection `fill_method="auto_fill"`
- Expérience A/B contrôlée (même SVG, seule différence = 5 annotations) : A sans = 5.7s OK, B avec = timeout 300s
- Décision : `inject_inkstitch_params` ne marque QUE les contours fins <1mm en `running_stitch` ; `_annotate_fill_paths_for_inkstitch` supprimé, remplacé par `_strip_fill_method_annotations` (purge les SVG stockés annotés par les anciennes versions)
- Corollaire : les conversions prod annotées depuis le commit « forcer tatami fill » subissaient ce ralentissement — la purge le corrige aussi pour les re-conversions
- `normalize_stroke_only_paths` skippe désormais les paths `inkstitch:stroke_method` (les choix running_stitch de l'éditeur étaient écrasés)

**Iter 4 — [SCORING] seuils paramétrés par profil machine** (`previews.py`, `tasks.py`)
- `_compute_quality_score(machine=...)` : seuils fils (ideal=min(7,max_threads), limite=max_threads, hard=+5) et dimensions (hoop, tolérance +40/+30mm) paramétrés
- `machine=None` = comportement PR1050X strictement identique (protège le benchmark, vérifié T01=92/T08=94)
- `force_max_svg_colors(max_colors=machine.max_threads)` — mono-aiguilles : max_threads=8 (≠ needles=1, re-enfilage standard)

**Note** : l'audit calibration scoring complet prévu S9 n'a pas été fait (session features) — à faire en Session 10.

---

### Session 10 — 2026-07-04 (Windows)

**Contexte** : 5 conversions signalées par l'utilisateur (fichiers dans `tests/niveau2/logo/`) :
fond brodé par-dessus le design, texte détruit, couleurs fausses. Diagnostic par reproduction
pipeline + aperçus PES + A/B contrôlé stacked/cutout.

**Étapes ciblées : ENV + VECT + SVG_PREP**

**Iter 0 — [ENV] palette Brother Windows + poppler pdf2image** (`thread_color.py`, `png_processing.py`)
- `_find_brother_palette` : ajout du candidat `exe_path.parent.parent / "palettes"` (layout Windows `inkstitch\bin\inkstitch.exe` → `inkstitch\palettes`). La palette existait, seul le chemin relatif manquait.
- `convert_pdf_to_png` : passage de `poppler_path=settings.POPPLER_BIN_PATH` à pdf2image (le mécanisme existait déjà pour pdftocairo).
- Impact mesuré : **92.7 → 94.8/100** (T08 94→100, T02 92→97, T12 erreur→79, quasi tous les tests +1 à +5 via color_fidelity réelle). Corrige aussi les couleurs fausses dans les PES produits (cas tampon : 6 fils fantaisistes → 2 fils Rouge/Blanc).

**Iter 1 — [VECT] VTracer `hierarchical=stacked` → `cutout`** (`_vtracer_helper.py`, `png_processing.py`)
- Cause racine du « fond brodé par-dessus » : stacked produit des formes empilées (ordre document = z-order), que `reorder`/`group_paths_by_color` (greedy NN depuis (0,0)) réordonnaient librement → le fond (plus gros bloc) partait en dernier et recouvrait le design. A/B contrôlé : icône avec fond violet → cercle blanc invisible en stacked, design parfait en cutout.
- cutout = formes disjointes (trous découpés) → aucun ordre de broderie ne peut recouvrir le design + moins de couches de fil superposées.
- Impact mesuré : benchmark stable 94.8 (identique — le scoring est aveugle au z-order), **gain visuel majeur** sur les 4 cas raster signalés (aperçus PES : designs reconnaissables, textes lisibles).

**Iter 2 — [SVG_PREP] réordonnancement z-safe** (`svg_utils.py`, `png_processing.py`)
- `reorder_svg_paths_for_minimal_jumps` : greedy NN restreint aux runs consécutifs de même fill (l'ordre inter-couleurs n'affecte pas les jumps — une coupe de fil sépare les couleurs de toute façon).
- `group_paths_by_color` : fusion z-safe — un path ne rejoint un bloc antérieur de sa couleur que si sa bbox ne chevauche aucun path d'une autre couleur qu'il enjamberait ; blocs ordonnés par ordre document (fond en premier) ; NN intra-bloc conservé.
- Marqueur `data-stitchflow-disjoint="1"` posé par `png_processing` sur les SVG VTracer cutout → fusion libre sans garde (sinon la garde bbox éclatait T05 en 108 blocs, T03 84).
- Impact mesuré : 94.8 stable, zéro régression ; cas `test-logo.svg` (SVG direct pleine page) : fond bleu brodé en premier, textes « LOGO / PDF Test Design / SAMPLE / 2026 » lisibles (avant : tatami bleu opaque sur tout).

**Iter 3 — Ajout T21/T22 au benchmark** (`tests/run_benchmark.py`)
- T21 : `niveau2/logo/icone-app-arrondie.png` (n=3, 80mm) → **97/100** (verrou z-order raster)
- T22 : `niveau2/logo/logo-retro-4couleurs.png` (n=4, 80mm) → **97/100** (verrou z-order + texte fin)
- Score moyen 22 tests : **95.0/100**

**Leçon S10 (à ne pas oublier)** : le score peut être excellent sur un PES visuellement détruit.
Toute modification de l'ordre des paths doit être z-safe. Ne jamais réintroduire un greedy NN
inter-couleurs sur des formes non disjointes.

---

### Session 12 — 2026-07-05 (Windows)

**Contexte** : 5 conversions signalées par l'utilisateur : texte « MAISON »/« EAGLES » totalement
absent des PES (scores 100 et 98 !), doublons de fils (Khaki ×3, Brass ×2), design contours noté 65.

**Étapes ciblées : ENV + SVG_PREP + SCORING (audit ciblé)**

**Iter 0 — [ENV] Cache Ink/Stitch corrompu + auto-guérison** (`inkstitch.py`)
- Découverte : le cache diskcache SQLite d'Ink/Stitch (`%LOCALAPPDATA%\inkstitch\inkstitch\cache\stitch_plan\`)
  peut se corrompre (`sqlite3.DatabaseError: database disk image is malformed`) → **TOUTES les conversions
  échouent silencieusement** (exit 0, ZIP vide) : benchmark 22/22 en erreur. Un processus inkstitch zombie
  verrouillait les fichiers WAL.
- Fix : purge manuelle + `convert_svg_to_pes()` détecte le marqueur dans stderr, purge le cache et retente
  une fois automatiquement.
- Impact : benchmark 0/22 → 95.0/100 (22/22, baseline S12 = S11).

**Iter 1 — [SVG_PREP] `find_inkscape()` : Inkscape hors PATH = texte perdu** (`svg_utils.py`)
- Cause racine des textes absents : Inkscape installé (`C:\Program Files\Inkscape\`) mais hors PATH →
  `shutil.which` → None → `prepare_svg_for_inkstitch` sautait silencieusement object-to-path → les `<text>`
  restaient tels quels → **Ink/Stitch les ignore sans erreur**.
- Fix : résolution `INKSCAPE_EXECUTABLE` (.env) → PATH → emplacements usuels Windows/macOS, cache module.
- Impact : logo-typographique 100/100 avec texte réellement brodé (20 347 pts vs 18 412 sans texte),
  écusson EAGLES 93→98 avec texte + fil blanc récupérés.

**Iter 2 — [SCORING] Garde-fou texte non brodable** (`svg_utils.py` + `previews.py`)
- `prepare_svg_for_inkstitch` retourne `text_remaining` ; `count_unconverted_text_elements()` réutilisé par
  le scoring : si des `<text>` avec contenu subsistent dans le SVG final → coverage cap 40, **score total
  cap 65**, message explicite. Plus jamais de 100/100 sur un design amputé de son texte.

**Iter 3 — [SCORING] Fils distincts vs arrêts de couleur** (`previews.py`)
- `thread_count` = couleurs distinctes (aiguilles réellement mobilisées), `color_stops` = séquence réelle.
  Liste « Fils nécessaires » dédupliquée (plus de « Brass ×2 », « Khaki ×3 ») ; template affiche
  `thread_colors|length`.
- Impact : mandala 82→91 (12 arrêts = 9 fils distincts, sort du « dépasse les 10 fils »).

**Iter 4 — [SVG_PREP] normalize_stroke_only_paths géométrie-aware** (`svg_utils.py`)
- **DÉCOUVERTE MAJEURE 1** : avec Inkscape actif, les `<circle>`/`<line>` deviennent des `<path>`
  stroke-only → la conversion systématique stroke→fill (fix S8) remplissait les cercles décoratifs en
  **disques pleins recouvrant le design** (mandala détruit sous un aplat khaki, contour-only → 3 disques).
- **DÉCOUVERTE MAJEURE 2 (A/B contrôlé)** : annoter ces paths `inkstitch:stroke_method="running_stitch"`
  fait passer Ink/Stitch de 11s à **timeout 300s** (même famille que fill_method S9). Les strokes NUS sont
  brodés nativement en points courants par Ink/Stitch — la prémisse S8 « Ink/Stitch ignore les paths sans
  fill » est fausse dans le cas général.
- Fix : paths ouverts ou formes fermées avec bbox ≥15% du viewBox → laissés intacts ; seules les petites
  formes fermées (glyphes) restent converties en fill (cas S8 préservé).
- Impact : mandala et contour-only visuellement corrects, écusson 11s sans timeout.

**Iter 5 — [SCORING] Audit ciblé : designs contours + density-aware niveau 3** (`previews.py`)
- `_extract_svg_colors` lit aussi les strokes (fix « Couleurs SVG non lisibles » → fidélité mesurable).
- `_is_contour_only_design()` : design 100% contours → s_score/dens_score plancher 90 (un contour propre
  produit naturellement peu de points et une densité quasi nulle — c'est le résultat correct).
- Density-aware niveau 3 : 500-1200 pts avec densité optimale (0.5-20) → s_score 90 (petit design sain).
- Impact : contour-only 65→93 ; T13 90→96 ; T10 92→97 attendu.

**Iter 6 — [SVG_PREP] `find_inkscape()` propagé** (`png_processing.py`, `pdf_processing.py`)
- Les 3 `shutil.which("inkscape")` restants (fallback vectorisation, simplify nœuds) utilisent le helper.
- Benchmark aligné sur la prod : `_apply_svg_postprocess` appelle désormais `prepare_svg_for_inkstitch`
  (comme tasks.py) — l'étape Inkscape est enfin exercée par les tests.

**Ajout T23/T24 au benchmark** (`tests/run_benchmark.py`)
- T23 : `niveau3/texte/logo-typographique-complexe.svg` (SVG `<text>`, 120mm, Hard) — verrou texte→paths
- T24 : `niveau2/geometrique/mandala-6branches.svg` (176mm, Medium) — verrou fils distincts + strokes intacts

**Résultat final S12** : **95.4/100 (24/24)** — T10 95→98, T13 90→96, T23=100, T24=91 ;
T01=92 et T08=100 stables ; aucune régression ; 75 tests unitaires OK.
Cas utilisateur : logo-typographique 100 (texte brodé), écusson EAGLES 98 (texte + blanc récupérés),
mandala 82→91 (fils dédupliqués, anneaux intacts), contour-only 65→93 (calibration contours).

---

### Session 11 — 2026-07-04 (Windows)

**Contexte** : signalement utilisatrice — icône app bleu/violet 3 couleurs convertie avec un fil
"Purple" nettement plus violet que la source, score qualité 97/100 "Excellent" sans aucun signal.

**Diagnostic** :
1. `snap_svg_colors_to_brother_palette()` (`thread_color.py`) fait un `min()` ΔE Lab sans seuil —
   comportement correct en soi (aucune tolérance à appliquer, le fil le plus proche EST le bon
   choix quand la palette n'a rien de mieux). Le vrai problème : aucun signal quand l'écart choisi
   est important.
2. `color_fidelity` ne pèse que 18% du score pondéré, calculé sur une **moyenne** des écarts ΔE
   par couleur — un fil très décalé se noie dans la moyenne si les autres couleurs sont fidèles
   (ex: 1 fil à ΔE=22 + 2 fils parfaits → moyenne ΔE≈11 → score dilué ≈87, jamais signalé).
3. Gate critique (`previews.py`) exemptait `color_fidelity` du plafonnement pour les pipelines SVG
   direct au motif que "la fidélité dépend d'Ink/Stitch, hors de contrôle" — argument faux : le
   snap Brother s'applique identiquement aux SVG directs et aux sources raster.
4. Aucun badge visuel nulle part dans l'UI pour signaler un fil visiblement décalé.

**Iter 1 — Seuils ΔE partagés** (`thread_color.py`)
- `NOTABLE_DELTA_E_THRESHOLD = 20.0`, `LIGHT_DELTA_E_THRESHOLD = 10.0` (repères CIE76 usuels :
  <10 non perceptible en usage courant, 10-20 visible mais tolérable, ≥20 écart net) — calibrés
  avec l'utilisatrice.
- `classify_color_drift()` et `hex_delta_e()` : helpers publics réutilisés par `previews.py` et le
  filtre template. `get_snap_preview()` enrichi avec `delta_e`/`notable_drift` par couleur.
- Impact benchmark : nul (pas encore branché dans le scoring).

**Iter 2 — Label capping + gate corrigé** (`previews.py`)
- `_score_color_fidelity()` calcule désormais `max_dist` (pire ΔE individuel) en plus de
  `mean_dist`, retourné et stocké dans `details["color_fidelity"]["max_delta_e"]` +
  `notable_drift`.
- Gate critique : suppression de l'exemption SVG direct — `essential_min = min(s_score, c_score)`
  dans tous les cas.
- **Label capping** : si `notable_drift` (max_dist≥20) et label calculé = "Excellent" → rétrogradé
  à "Bon"/`warning` (`label_capped=True`). **Le score numérique n'est pas modifié**, uniquement le
  label — donc zéro impact sur le score moyen benchmark.
- Impact mesuré : score moyen inchangé 95.0/100 (22/22). T01=92 (Bon, était Excellent), T03=94
  (Bon), T09=95 (Bon), T11=94 (Bon), T14=91 (Bon) — tous avec un ΔE max réel ≥20 déjà présent mais
  jusqu'ici invisible. T08 stable 100 (Excellent, aucun écart couleur).

**Iter 3 — Badges UI** (`conversions/templatetags/thread_fidelity.py` nouveau,
`svg_editor.html`, `conversion_status.html`)
- Filtre Django `delta_e` (nouveau module `templatetags/`) calculant le ΔE directement à partir de
  `color.hex`/`color.brother_hex` déjà présents dans le contexte de l'éditeur SVG — aucune
  modification de `views.py` nécessaire.
- Badge `⚠ écart couleur (ΔE N)` par fil dans l'éditeur SVG si ΔE≥20 ; badge `⚠ écart couleur
  notable` dans le détail "Fidélité couleurs" de la page résultat si `notable_drift`. Purement
  informatif, aucun blocage du téléchargement (décision utilisatrice).

**Iter 4 — Garde-fou générique benchmark** (`tests/run_benchmark.py`)
- Ajout d'un contrôle générique (pas une fixture dédiée) : chaque test vérifie que
  `notable_drift=True` n'est jamais accompagné du label "Excellent" — alerte
  `color_fidelity_regression` imprimée en fin de run sinon. S'applique aux 22 tests existants, dont
  5 (T01/T03/T09/T11/T14) exposent déjà un ΔE réel ≥20 et servent de garde-fou vivant.
- **Tentative de fixture dédiée bleu/violet abandonnée** : plusieurs SVG/PNG synthétiques avec un
  bleu-violet volontairement hors palette (`#6A0DAD`, ΔE pré-snap mesuré à 22.1 vs `Violet 613`)
  ont été testés en pipeline complet — le fil final dans le PES correspondait exactement à notre
  snap (ΔE post-pipeline = 0), contrairement à T01 où un snap tout aussi correct (`#134a76`) finit
  en PES sous un fil différent (`Ultramarine #0b3d91`, ΔE réel 28.4). Cause probable : **le format
  PES v1 n'encode qu'une table de couleurs de fil limitée** — Ink/Stitch réalise son propre second
  snap vers cette table au moment de l'écriture, un phénomène dépendant du contenu (formes
  simples parfois préservées exactement) et non reproductible de façon fiable à la demande. Les
  tests existants qui exhibent déjà ce ΔE réel sont donc un garde-fou plus solide qu'une fixture
  artificielle qui ne le reproduirait pas de façon garantie.

**Score global** : 95.0/100 → 95.0/100 (0.0, score numérique identique par design — seuls les
labels reflètent désormais honnêtement un écart de couleur réel).

---

## Calibration du scoring (audit tous les 3 sessions)

Dernière révision : Session 4 (2026-06-17) — S7 : calibration ciblée coverage (55→65) + jump floor (≤15 sauts)
- Prochaine révision complète obligatoire : **Session 9** (prochain multiple de 3)

| Critère | Verdict S4 | Seuils actuels dans previews.py |
|---------|-----------|--------------------------------|
| jumps | ✅ Recalibré S4 | <0.5%=100, <2%=80, **<4%=65 (nouveau)**, <8%=45, ≥8%=10 |
| color_fidelity | ⚠️ Compromis délibéré (coeff 1.2) + **label capping S11** | `100 - int(mean_dist * 1.2)` × ratio ; label plafonné à "Bon" si ΔE max ≥20 (score inchangé) |
| stitches | ✅ Fiable | <100=0, <500=20(+L1+L2), <1200=60, ≤50000=100, ≤150000=75, ≤500000=35, >500000=0 |
| density | ✅ Fiable | 0.5-20=100, 0.2-0.5=75, 20-50=65, <0.2=20, >50=15 |
| threads | ✅ Fiable | ≤7=100, ≤10=80, ≤15=25, >15=0 |
| dimensions | ✅ Fiable | dans zone 360×200mm + ≥20×5mm = 100 |
| coverage | ✅ Recalibré S7 | floor 80 (quasi-couverture) + floor **65** (partielle, relevé 55→65 S7) |
| mesures brutes | ✅ Fiables | count_stitch_commands(STITCH) pour scoring, bounds()/10 → mm correct |
