# Tests — StitchFlow

## Structure

```
tests/
├── run_integration.py      ← Tests E2E automatisés (Phase 6d)
├── generate_fixtures.py    ← Génère les fixtures de tests/fixtures/
│
├── fixtures/               ← Fichiers de référence pour run_integration.py
│   ├── logos/              SVG et PNG de logos
│   ├── ecusson/            Écussons et patches
│   ├── texte/              Texte et typographie
│   ├── geometrique/        Formes géométriques
│   └── pdf/                PDFs vectoriels et scannés
│
├── manual/                 ← Fichiers pour tests manuels ad-hoc (upload UI)
│   ├── svg/                SVGs de test (Phase 1-2)
│   ├── png/                PNGs de test (Phase 3)
│   ├── jpeg/               JPEGs de test
│   ├── pdf/                PDFs de test
│   └── webp/               WebPs de test
│
└── results/                ← Fichiers .PES générés (gitignored — local seulement)
```

---

## Tests automatisés — `run_integration.py`

Lance une vraie conversion pour chaque fixture via HTTP + Celery et compare les scores.

**Prérequis :**
```bash
# 1. Django sur port 8001
source .venv/bin/activate && python src/manage.py runserver 8001

# 2. Worker Celery
source .venv/bin/activate && PYTHONPATH=src celery -A stitchflow worker -l info

# 3. Générer les fixtures si absentes
python tests/generate_fixtures.py
```

**Lancer les tests :**
```bash
python tests/run_integration.py
# Avec options :
python tests/run_integration.py --output /tmp/results.json --timeout 300
```

---

## Fixtures — `fixtures/`

Générées par `generate_fixtures.py` (reproductible, zéro droits d'auteur).
Voir `fixtures/README.md` pour le détail de chaque fixture et les scores attendus.

---

## Tests manuels — `manual/`

Fichiers à uploader directement sur http://localhost:8001/conversions/ pour tester des cas spécifiques.

| Dossier | Fichiers | Usage |
|---|---|---|
| `svg/` | 9 SVGs (cercle, étoile, texte...) | Tester la conversion SVG directe |
| `png/` | 11 PNGs (texte, formes, écusson...) | Tester le pipeline PNG → vectorisation → PES |
| `jpeg/` | 2 JPEGs | Tester le support JPEG |
| `pdf/` | 4 PDFs (vectoriel + scanné) | Tester les deux pipelines PDF |
| `webp/` | 1 WebP | Tester le support WebP |

**SVGs notables :**

| Fichier | Ce qu'il teste |
|---|---|
| `svg/01-circle-simple.svg` | Cas de base — fill simple 1 couleur |
| `svg/03-geometric-multicolor.svg` | Multi-couleurs (4 fils) |
| `svg/07-logo-atelier-8couleurs.svg` | 8 couleurs — dépasse les 7 idéaux |
| `svg/09-gradient-erreur-attendue.svg` | Doit échouer avec message gradient |
| `png/07-ecusson-12couleurs.png` | 12 couleurs → force_max_svg_colors doit réduire à ≤10 |
| `png/09-photo-complexe-bruit.png` | Photo → doit router vers VTracer (variance élevée) |

---

## Résultats — `results/`

Dossier local gitignored. Les `.pes` téléchargés depuis l'UI peuvent être stockés ici pour référence.
