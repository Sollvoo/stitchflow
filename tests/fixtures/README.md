# Fixtures de test StitchFlow — Bibliothèque par catégorie broderie

Générées par `tests/generate_fixtures.py` (reproductible, zéro droits d'auteur).

## Régénérer

```bash
source .venv/bin/activate
python tests/generate_fixtures.py
```

---

## logos/ — Logos vectoriels et raster

| Fichier | Format | Couleurs | Cas testé | Score attendu |
|---|---|---|---|---|
| `logo-simple-3couleurs.svg` | SVG | 3 | Logo bouclier simple, idéal broderie | ≥ 85 |
| `logo-complexe-7couleurs-texte.svg` | SVG | 7 | Logo + texte multi-couleurs, cas réaliste | ≥ 75 |
| `logo-fond-blanc.png` | PNG | 4 | Fond blanc dominant (>70%) → doit suggérer removeBg | ≥ 70 |
| `logo-fond-transparent.png` | PNG/RGBA | 4 | Fond alpha → doit détecter transparence, removeBg | ≥ 65 |

**Points de vigilance :**
- `logo-fond-blanc.png` : l'auto-analyse doit cocher "Supprimer le fond" automatiquement
- `logo-fond-transparent.png` : idem via canal alpha (pixels < 30 d'opacité)

---

## ecusson/ — Écussons et patches

| Fichier | Format | Couleurs | Cas testé | Score attendu |
|---|---|---|---|---|
| `ecusson-club-6couleurs.png` | PNG | 6 | Écusson hexagonal — cas d'usage principal | ≥ 70, 6-7 fils |
| `patch-sportif-texte-graphique.png` | PNG | 8 | Patch ovale texte + étoiles — multi-éléments | ≥ 65, 7-9 fils |
| `badge-contours-fins.svg` | SVG | 5 | Badge avec rayons et contours 1-2px | 55-75, challenge densité |

**Points de vigilance :**
- `ecusson-club-6couleurs.png` : l'auto-analyse ne doit PAS suggérer 12 couleurs (il y en a 6)
- `badge-contours-fins.svg` : les contours très fins peuvent disparaître en broderie → score densité faible
- `patch-sportif-texte-graphique.png` : test du threshold 0.5% pour les petites étoiles

---

## texte/ — Texte et typographie

| Fichier | Format | Couleurs | Cas testé | Score attendu |
|---|---|---|---|---|
| `monogramme-initiales.svg` | SVG | 3 | Monogramme héraldique or + marine | ≥ 80 |
| `texte-multicolore-8couleurs.svg` | SVG | 8 | Chaque lettre dans une couleur | 65-80, 8 fils |
| `texte-contours-fins.svg` | SVG | 4 | Texte stroke-only sans remplissage | 50-70, challenge |

**Points de vigilance :**
- `texte-contours-fins.svg` : satin stitch requis pour le stroke-only — peut générer peu de points
- `texte-multicolore-8couleurs.svg` : 8 fils dépasse les 7 idéaux → score fils minoré

---

## geometrique/ — Géométrique et abstrait

| Fichier | Format | Couleurs | Cas testé | Score attendu |
|---|---|---|---|---|
| `motif-repetitif-losanges.svg` | SVG | 4 | Grille 5×5 losanges — motif ethnique | ≥ 70 |
| `cercles-concentriques-5couleurs.png` | PNG | 5 | Anneaux concentriques — test quantification | ≥ 65 |
| `abstrait-6couleurs.svg` | SVG | 6 | Formes qui se chevauchent — fidélité couleurs | 60-80 |

**Points de vigilance :**
- `cercles-concentriques-5couleurs.png` : l'auto-analyse doit détecter 5 couleurs (pas 12 cappé)
- `motif-repetitif-losanges.svg` : beaucoup de points → vérifier densité et temps estimé

---

## pdf/ — Documents PDF

| Fichier | Type PDF | Pipeline | Score attendu |
|---|---|---|---|
| `logo-vectoriel.pdf` | Vectoriel (paths SVG) | pdftocairo → SVG direct | ≥ 75 |
| `texte-vectoriel.pdf` | Vectoriel (texte SVG) | pdftocairo → SVG direct | ≥ 70 |
| `simule-scanne.pdf` | Raster (PNG embarquée) | pdf2image → PNG → vectorisation | ≥ 50 |

**Points de vigilance :**
- `logo-vectoriel.pdf` + `texte-vectoriel.pdf` : doivent passer par `is_vector_pdf_svg()` = True
- `simule-scanne.pdf` : doit fallback sur le pipeline raster (n_colors suggéré, removeBg non déclenché)
