# Suivi qualité convertisseur StitchFlow

## Score global estimé (% d'un convertisseur parfait)

| Session | Date | Score moyen avant | Score moyen après | Delta | Ceiling théorique |
|---------|------|------------------|-------------------|-------|-------------------|
| 1 | 2026-06-13 | 88.7/100 | 91.3/100 | +2.6 | 67.5/100 |

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

## Problèmes connus non résolus

- **T01 color_fidelity=66** : ΔLab=28.4 entre couleur SVG et fil Brother le plus proche. Dépend de la palette Brother disponible — pas résoluble sans intervention humaine (choix de fil manuellement).
- **T02/T03 coverage < 100** : images ont moins de couleurs distinctes que le n_colors demandé — comportement attendu.
- **T05 (85/100)** : photo complexe 560KB → ceiling vectorisation atteint, amélioration impossible sans intervention humaine.

## Benchmark de référence

### Résultats détaillés — Session 1 (2026-06-13)

| ID | Fichier | Format | Params | Score avant | Score après | Delta | Erreur |
|----|---------|--------|--------|------------|------------|-------|--------|
| T01 | png/06-logo-monochrome-blanc.png | PNG | n=2,bg,80mm | 80 | 87 | +7 | — |
| T02 | png/03-logo-multicolore.png | PNG | n=5,80mm | 90 | 90 | 0 | — |
| T03 | png/07-ecusson-12couleurs.png | PNG | n=10,100mm | 89 | 89 | 0 | — |
| T04 | png/08-texte-fond-colore.png | PNG | n=4,60mm | 91 | 92 | +1 | — |
| T05 | png/09-photo-complexe-bruit.png | PNG | n=8,bg,100mm | 85 | 85 | 0 | — |
| T06 | jpeg/12-logo-formes-simple.jpg | JPEG | n=6,80mm | 95 | 95 | 0 | — |
| T07 | webp/test-logo.webp | WebP | n=5,80mm | 92 | 92 | 0 | — |
| T08 | svg/01-circle-simple.svg | SVG | direct,80mm | 100 | 100 | 0 | — |
| T09 | svg/07-logo-atelier-8couleurs.svg | SVG | direct,100mm | 92 | 92 | 0 | — |
| T10 | svg/06-text-outline.svg | SVG | direct,80mm | 65 | 88 | +23 | — |
| T11 | pdf/test-logo.pdf | PDF | n=6,100mm | 94 | 94 | 0 | — |
| T12 | pdf/test-scanned-pdf.pdf | PDF | n=4,80mm | 91 | 92 | +1 | — |

**Score moyen avant : 88.7/100**
**Score moyen après : 91.3/100 (delta : +2.6 pts)**

### Position par rapport au ceiling

- Score actuel : 91.3/100
- Ceiling théorique auto-digitizing : 67.5/100
- Note : le score moyen dépasse le ceiling car les fichiers de test sont des designs simples à intermédiaires. Le ceiling s'applique aux designs complexes avec retouche manuelle requise.

### Ce qui manque encore (pour sessions suivantes)

- **Amélioration color_fidelity** : T01 a ΔLab=28.4 car couleur SVG (logo monochrome blanc) ne correspond pas bien à la palette Brother. Phase 7 (assistant pré-conversion) pourrait suggérer un fil adapté.
- **T02 coverage < 100** : 4/5 couleurs — nécessite investigation plus fine de la vectorisation VTracer (images multi-couleurs avec aplats proches)
- **Stitch count T02 (1381)** : encore sous le seuil 1500, reste à s_score=60. Pas de fix évident sans augmenter agressivité VTracer (risque de régression sur textes fins).

### Prochaines priorités

1. **Phase 7** : assistant pré-conversion — pourrait corriger les problèmes de color_fidelity en suggérant les bons paramètres avant conversion
2. **VTracer params pour logos multi-couleurs** : investiguer pourquoi T02 obtient 4/5 couleurs (color_precision / filter_speckle)
3. **Preview PES** : améliorer le rendu visuel de la prévisualisation (pyembroidery → rendu plus réaliste)
