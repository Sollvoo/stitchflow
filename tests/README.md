# Tests — Fichiers de test StitchFlow

Dossier contenant les fichiers utilisés pour tester manuellement le pipeline SVG → PES.

## Structure

```
tests/
├── svg/        ← Fichiers SVG de test pour la conversion
├── pdf/        ← PDFs de référence (designs source)
├── png/        ← Images PNG de référence (Phase 3)
└── results/    ← Fichiers .PES obtenus après conversion
```

## Fichiers SVG disponibles

| Fichier | Description | Ce qu'il teste |
|---------|-------------|----------------|
| `01-circle-simple.svg` | Cercle plein bleu | Fill simple, 1 couleur |
| `02-star-5pts.svg` | Étoile 5 branches | Chemins avec points complexes |
| `03-geometric-multicolor.svg` | Rectangles multicouleurs | Plusieurs fils (4 couleurs) |
| `04-contour-only.svg` | Cercles concentriques vides | Running stitch (contours seuls) |
| `05-flower-paths.svg` | Fleur avec ellipses | Transforms, chemins bezier |
| `06-text-outline.svg` | Texte "BRODERIE" | Lettrage, texte en chemins |

## Usage

Uploader un fichier SVG sur http://localhost:8001/conversions/ pour tester la conversion.
