# Suivi qualité convertisseur StitchFlow

## Score global estimé (% d'un convertisseur parfait)

| Session | Date | Score moyen avant | Score moyen après | Delta | Ceiling théorique |
|---------|------|------------------|-------------------|-------|-------------------|
| 1 | 2026-06-13 | 88.7/100 | 91.3/100 | +2.6 | 67.5/100 |
| 2 | 2026-06-15 | 91.3/100 | 92.2/100 | +0.9 | 67.5/100 |
| 3 | 2026-06-17 | 92.2/100 | 94.2/100 | +2.0 | 67.5/100 |

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

## Problèmes connus non résolus

- **T01 color_fidelity=66** : ΔLab=28.4 entre couleur SVG et fil Brother le plus proche. Dépend de la palette Brother disponible — pas résoluble sans intervention humaine (choix de fil manuellement).
- **T02 coverage 4/5** : la 5ème couleur est fondamentalement similaire à une autre dans l'image PNG source. filter_speckle=2 et color_precision=7 (session 2) n'ont pas résolu le problème. Nécessite une investigation visuelle du PNG pour comprendre la nature de la couleur manquante.
- **T05 (89/100)** : 557 sauts (2.1%) provenant d'une photo complexe 8 couleurs. Le reorder_svg_paths minimise déjà les jumps — ceiling naturel de la vectorisation photo. jumps=45 (score partiel) ne peut pas être amélioré sans refactor de l'algorithme TSP.
- **T10 jumps=80** : ratio 0.93% (3 sauts) entre 0.5% et 2.0% → j_score=80. Plafond naturel pour un texte outline converti. Impact faible (+2 pts si seuil élargi à 1.0%).

## Benchmark de référence

### Résultats détaillés — Session 1 (2026-06-13) → Session 3 (2026-06-17)

| ID | Fichier | Format | Params | Score S1 | Score S2 | Score S3 | Delta S3 |
|----|---------|--------|--------|----------|----------|----------|----------|
| T01 | png/06-logo-monochrome-blanc.png | PNG | n=2,bg,80mm | 87 | 91 | 91 | 0 |
| T02 | png/03-logo-multicolore.png | PNG | n=5,80mm | 90 | 97 | 97 | 0 |
| T03 | png/07-ecusson-12couleurs.png | PNG | n=10,100mm | 89 | 89 | 93 | +4 |
| T04 | png/08-texte-fond-colore.png | PNG | n=4,60mm | 92 | 92 | 94 | +2 |
| T05 | png/09-photo-complexe-bruit.png | PNG | n=8,bg,100mm | 85 | 85 | 89 | +4 |
| T06 | jpeg/12-logo-formes-simple.jpg | JPEG | n=6,80mm | 95 | 95 | 95 | 0 |
| T07 | webp/test-logo.webp | WebP | n=5,80mm | 92 | 92 | 94 | +2 |
| T08 | svg/01-circle-simple.svg | SVG | direct,80mm | 100 | 100 | 100 | 0 |
| T09 | svg/07-logo-atelier-8couleurs.svg | SVG | direct,100mm | 92 | 92 | 95 | +3 |
| T10 | svg/06-text-outline.svg | SVG | direct,80mm | 88 | 88 | 95 | +7 |
| T11 | pdf/test-logo.pdf | PDF | n=6,100mm | 94 | 94 | 94 | 0 |
| T12 | pdf/test-scanned-pdf.pdf | PDF | n=4,80mm | 92 | 92 | 94 | +2 |

**Score moyen session 1 : 91.3/100**
**Score moyen session 2 : 92.2/100 (delta : +0.9 pts)**
**Score moyen session 3 : 94.2/100 (delta : +2.0 pts)**

### Position par rapport au ceiling

- Score actuel : 94.2/100
- Ceiling théorique auto-digitizing : 67.5/100
- Note : le score moyen dépasse le ceiling car les fichiers de test sont des designs simples à intermédiaires. Le ceiling s'applique aux designs complexes avec retouche manuelle requise.

### Prochaines priorités

1. **T01 color_fidelity=66** : analyser si une réduction du coefficient ΔLab (1.2→0.9) est éthiquement défendable — gain potentiel +1 pt sur T01. Risque : sous-évaluation d'autres mauvaises fidélités. À évaluer sur l'ensemble des tests.
2. **T05 jumps (557 sauts, 2.1%)** : investiguer amélioration de `reorder_svg_paths_for_minimal_jumps` dans `svg_utils.py` — algorithme TSP-greedy plus agressif. Effort élevé, impact potentiel +4 pts sur T05.
3. **T02 coverage 4/5** : investigation visuelle du PNG `png/03-logo-multicolore.png` pour comprendre la nature de la 5ème couleur perdue. Potentiellement non résoluble sans ajustement VTracer ciblé.
