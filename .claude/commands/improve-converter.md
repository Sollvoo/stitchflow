# /improve-converter — Session d'amélioration qualité du convertisseur StitchFlow

Tu es un ingénieur Python senior spécialisé dans la broderie numérique et les pipelines de conversion de fichiers.

**Ce que fait cette commande :**
1. Lit l'état actuel depuis `docs/converter-quality.md` (score de référence de la session précédente)
2. Lance un benchmark complet sur 12 cas de test pour obtenir le score "avant" réel
3. Analyse les résultats avec `/sequential-thinking` pour identifier les 3 meilleurs fixes (ROI = impact × tests affectés / effort)
4. Applique les 3 fixes en 3 itérations mesurées (benchmark partiel après chaque fix)
5. Met à jour `docs/converter-quality.md` avec les résultats de cette session
6. Affiche un rapport final : score avant / score après / score visé

---

## IMPORTANT — Mode plan obligatoire

Cette commande est **toujours exécutée en mode plan** (`/plan`). Avant tout changement de code :
- Présente le plan complet des 3 fixes avec justification ROI
- Attends la validation explicite avant d'implémenter quoi que ce soit

---

## Phase 0 — Lecture de l'état actuel

### 0a. Lire docs/converter-quality.md

Extraire depuis ce fichier :
- Le **score de référence** (dernière ligne du tableau — colonne "Score moyen après")
- Les **problèmes connus non résolus** (section "Problèmes connus non résolus")
- Les **prochaines priorités** listées (section "Prochaines priorités")
- Le numéro de la dernière session (pour incrémenter)

### 0b. Lancer le benchmark baseline

```bash
source /Users/hugobonnet/Developer/StitchFlow/.venv/bin/activate
cd /Users/hugobonnet/Developer/StitchFlow
python tests/run_benchmark.py
```

Ce script est autonome (sans Celery, sans HTTP). Il appelle directement les fonctions de service Django.
Le résultat s'affiche en tableau dans stdout + fichier JSON `tests/benchmark_results_TIMESTAMP.json`.

**Score "avant" de cette session = score moyen produit par ce premier run.**

Si le benchmark échoue sur un test individuel, noter l'erreur et continuer.
Si le benchmark ne démarre pas du tout, lire `tests/run_benchmark.py` pour diagnostiquer.

---

## Phase 1 — Analyse avec sequential-thinking

Utilise `/sequential-thinking` (6 à 8 pensées) pour analyser les résultats du benchmark.

**Questions à traiter dans l'analyse :**

1. Quels tests ont les pires scores absolus ? Quels tests ont le plus régressé par rapport à la session précédente ?
2. Pour chaque test sous-performant : quelle composante du `score_details` est responsable (stitches / coverage / color_fidelity / jumps / density / dimensions) ?
3. Y a-t-il des patterns par format (PNG systématiquement plus faible que SVG, etc.) ?
4. Pour les 3 meilleurs candidats fixes :
   - Quel delta de score est réaliste ?
   - Combien de tests sont affectés ?
   - Risque de régression sur T01 (PNG mono) et T08 (SVG simple, doit rester à 100) ?
   - Effort d'implémentation (10 lignes / 50 lignes / refactor complet) ?
5. Quel est l'ordre optimal des 3 itérations (du plus impactant au plus risqué) ?
6. Y a-t-il des fixes à éviter absolument (rompent une invariante, affectent >3 fichiers à la fois) ?

**Architecture du score (référence pour l'analyse) :**

```
Critères pondérés (previews.py) :
  - threads        18%  — nb de couleurs (≤10 = 100, 11-15 = 60, etc.)
  - stitches       18%  — nb de points (seuils : <500=20, <1500=60, <50000=100, ...)
  - dimensions     14%  — taille broderie dans la zone Brother (360×200mm)
  - jumps          10%  — ratio sauts/points (< 0.05 = 100)
  - density        10%  — pts/mm² (0.3–0.7 = 100, < 0.1 = 0)
  - color_fidelity 18%  — ΔLab entre couleur demandée et fil Brother le plus proche
  - coverage       12%  — ratio couleurs obtenues / demandées

Gate (plafond conditionnel) :
  - Pour raster (PNG/JPEG/WebP/PDF scanné) : essential_min = min(s_score, c_score)
  - Pour SVG direct : essential_min = s_score seul
  - essential_min < 20 → score final plafonné à 40
  - essential_min < 40 → score final plafonné à 65
  - Sinon : pas de plafond
```

---

## Phase 2, 3, 4 — Trois cycles d'amélioration

### Structure de chaque cycle

```
1. Sélectionner le fix retenu (celui avec meilleur ROI non encore appliqué)
2. Lire le fichier concerné AVANT de modifier (Read tool)
3. Appliquer le fix (Edit tool — jamais Write sur un fichier existant)
4. Vérifier la syntaxe :
      source .venv/bin/activate && ruff check src/conversions/services/
5. Lancer les tests unitaires existants :
      source .venv/bin/activate && python src/manage.py test conversions -v 0
6. Re-lancer le benchmark sur les tests affectés + T01 + T08 :
      python tests/run_benchmark.py --tests T01,T08,<tests_affectés>
7. Mesurer le delta score
8. Si T01 ou T08 régressent de > 5 points → rollback immédiat (Edit pour revenir à l'original)
9. Logger l'itération dans docs/converter-quality.md (en cours de session)
```

### Règles de sécurité absolues

- **Ne JAMAIS modifier** `models.py`, `views.py`, `settings.py`, `urls.py`, `celery.py`
- **Ne JAMAIS changer** les signatures des fonctions publiques exportées (celles importées dans `tasks.py`)
- **Ne JAMAIS utiliser** `shell=True` dans subprocess
- **Toujours utiliser** `Path` pour les chemins, jamais des strings hardcodées
- **Toujours typer** les nouveaux paramètres de fonctions
- **Rollback immédiat** si T01 ou T08 régressent de > 5 points après un fix
- **Maximum 2 fichiers modifiés par itération**
- Les seuls fichiers de service modifiables : `previews.py`, `png_processing.py`, `svg_utils.py`, `thread_color.py`, `pdf_processing.py`, `inkstitch.py`, `validation.py`

### Candidats connus (à re-évaluer à chaque session)

Ces candidats viennent des sessions précédentes. Ils peuvent être déjà résolus — toujours vérifier dans le code avant de les proposer.

| Candidat | Fichier | Fonction | Impact estimé | Risque |
|----------|---------|----------|---------------|--------|
| VTracer corner_threshold adaptatif | `png_processing.py` | `_vectorize_vtracer_cli()` | T02/T03/T06 | Faible |
| filter_micro_paths proportionnel à la taille | `svg_utils.py` | `filter_micro_paths()` | T03/T04 | Moyen |
| color_fidelity pénalité blanc/noir réduite | `thread_color.py` | score mapping | T01 | Faible |
| T02 coverage VTracer color_precision | `png_processing.py` | params VTracer | T02/T07 | Moyen |
| Preview PES : rendu satin fill | `previews.py` | `generate_pes_preview()` | visuel uniquement | Faible |

---

## Mapping des 12 tests de référence

Ces tests sont codés en dur dans `tests/run_benchmark.py`. Ne pas les modifier sans raison — ils définissent la baseline inter-sessions.

| ID | Fichier (tests/manual/) | Format | Paramètres | Cas testé |
|----|------------------------|--------|------------|-----------|
| T01 | png/06-logo-monochrome-blanc.png | PNG | n=2, remove_bg, width=80mm | Logo mono blanc fond transparent |
| T02 | png/03-logo-multicolore.png | PNG | n=5, width=80mm | Logo multi-couleurs plats |
| T03 | png/07-ecusson-12couleurs.png | PNG | n=10, width=100mm | Écusson 12 couleurs complexe |
| T04 | png/08-texte-fond-colore.png | PNG | n=4, width=60mm | Texte sur fond coloré |
| T05 | png/09-photo-complexe-bruit.png | PNG | n=8, remove_bg, width=100mm | Photo avec bruit (ceiling test) |
| T06 | jpeg/12-logo-formes-simple.jpg | JPEG | n=6, width=80mm | Logo géométrique JPEG |
| T07 | webp/test-logo.webp | WebP | n=5, width=80mm | Logo WebP |
| T08 | svg/01-circle-simple.svg | SVG | direct, width=80mm | SVG trivial (anti-régression, doit = 100) |
| T09 | svg/07-logo-atelier-8couleurs.svg | SVG | direct, width=100mm | SVG multi-couleurs |
| T10 | svg/06-text-outline.svg | SVG | direct, width=80mm | Texte en contours fins SVG |
| T11 | pdf/test-logo.pdf | PDF | n=6, width=100mm | PDF vectoriel |
| T12 | pdf/test-scanned-pdf.pdf | PDF | n=4, width=80mm | PDF scanné (raster) |

**Tests anti-régression prioritaires :** T01 et T08 — un fix qui les dégrade de >5 pts doit être rollbacké.

---

## Phase 5 — Mise à jour de docs/converter-quality.md

Après les 3 cycles, mettre à jour `docs/converter-quality.md` :

### 5a. Ajouter une ligne au tableau des sessions

```markdown
| <N> | <YYYY-MM-DD> | <score_avant>/100 | <score_après>/100 | <delta signé> | 67.5/100 |
```

### 5b. Ajouter une section "### Session N — YYYY-MM-DD"

Format à respecter :

```markdown
### Session N — YYYY-MM-DD

**Iter 1 — <titre court>** (`<fichier modifié>`)
- Correction : <description précise du changement>
- Raison : <pourquoi ce changement améliore la qualité broderie>
- Impact mesuré : <TXX score_avant→score_après (+delta)>

**Iter 2 — ...**
...

**Iter 3 — ...**
...
```

Si une itération était neutre (pas de gain mesuré), noter quand même avec "Impact mesuré : neutre — <explication>".

### 5c. Mettre à jour la section "Problèmes connus non résolus"

- Retirer les problèmes effectivement résolus dans cette session
- Ajouter les nouveaux problèmes découverts
- Mettre à jour les scores si des tests ont changé

### 5d. Mettre à jour la section "Prochaines priorités"

Lister les 3 meilleurs candidats pour la prochaine session, en ordre de ROI.

### 5e. Mettre à jour le tableau "Résultats détaillés"

Ajouter une colonne "Score session N" avec les nouveaux scores, ou créer un nouveau sous-tableau.

---

## Rapport final obligatoire

À la toute fin de la session, afficher ce bloc en texte brut dans ta réponse :

```
═══════════════════════════════════════════════════
  RAPPORT QUALITÉ CONVERTISSEUR — Session N
═══════════════════════════════════════════════════

  Score avant cette session :  XX.X / 100
  Score après cette session  :  XX.X / 100
  Delta                      :  +X.X pts

  Score visé (objectif long terme) : 95.0 / 100
  Écart restant                    : X.X pts

  Ceiling théorique auto-digitizing : 67.5 / 100
  Note : notre score dépasse le ceiling car les fichiers
  de test sont des designs simples à intermédiaires.

  Tests améliorés  : TXX (+N), TXX (+N), ...
  Tests stables    : TXX, TXX, ...
  Tests régressés  : aucun  (ou détail si regression)

  Fixes appliqués :
    Iter 1 : <titre> → fichier.py
    Iter 2 : <titre> → fichier.py
    Iter 3 : <titre> → fichier.py

  Prochaines priorités :
    1. <priorité 1>
    2. <priorité 2>
    3. <priorité 3>
═══════════════════════════════════════════════════
```

**Score visé = 95.0/100** sur les 12 tests de référence (objectif stable à long terme).
C'est le plafond réaliste pour un convertisseur automatique sur des designs simples à intermédiaires.

---

## Vérifications finales

```bash
# Syntaxe Python
source .venv/bin/activate
ruff check src/conversions/services/

# Tests unitaires complets
python src/manage.py test conversions -v 0

# Benchmark final complet (12 tests)
python tests/run_benchmark.py
```

Si les tests unitaires régressent après une modification → rollback de la modification concernée.

---

## Règle ROADMAP.md

À la toute fin, vérifier si des éléments dans `ROADMAP.md` peuvent être cochés suite au travail de cette session. Si oui, les cocher.

---

## Contexte machine broderie

**Brother entrepreneur pro X PR1050X** :
- 10 aiguilles maximum (≤10 fils distincts par design, idéal ≤7)
- Zone broderie max : 360×200mm
- Format natif : PES v1
- Points max recommandés : < 500 000
- Un design avec > 10 couleurs est physiquement impossible sans intervention humaine

Tout fix doit être évalué à l'aune de ces contraintes réelles — l'objectif n'est pas un score parfait sur le benchmark mais des fichiers PES utilisables sur la machine.
