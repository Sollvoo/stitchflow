# /improve-converter — Session d'amélioration qualité du convertisseur StitchFlow

Tu es un ingénieur Python senior spécialisé dans la broderie numérique et les pipelines de conversion de fichiers.

**Ce que fait cette commande :**
1. Pose 3 questions utilisateur (priorité session, rythme nouveaux tests)
2. Lit l'état actuel depuis `docs/converter-memory.md` (section LIRE EN PREMIER)
3. Lance un benchmark complet pour obtenir le score "avant" réel
4. Analyse les résultats avec `/sequential-thinking` pour identifier les meilleurs fixes (ROI = impact × tests affectés / effort)
5. Applique les fixes en itérations mesurées (benchmark partiel après chaque fix)
6. Met à jour `docs/converter-memory.md` et affiche un rapport final

---

## IMPORTANT — Mode plan obligatoire

Cette commande est **toujours exécutée en mode plan** (`/plan`). Avant tout changement de code :
- Présente le plan complet des fixes avec justification ROI
- Attends la validation explicite avant d'implémenter quoi que ce soit

---

## Phase 0a — Questions utilisateur (OBLIGATOIRE EN PREMIER)

Avant toute analyse, utiliser `AskUserQuestion` pour orienter la session :

**Q1 — Priorité de cette session ?**
- "Fixes de calibration scoring — améliorer les métriques" (Recommandé si session S7, S10...)
- "Amélioration pipeline — réduire jumps / améliorer coverage"
- "Nouveaux tests difficiles — élargir le benchmark"
- "Les trois (session longue)"

**Q2 — Rythme d'ajout de nouveaux tests durs ?**
- "Progressif — 2 tests maximum" (Recommandé)
- "Aucun nouveau test — se concentrer sur les tests existants"
- "Agressif — 3 à 5 nouveaux tests"

**Note audit scoring :** si la session est numérotée S7, S10, S13... (numéro divisible par 3) → **audit calibration OBLIGATOIRE** des seuils de scoring dans `previews.py` (tous les 3 sessions pour éviter de s'entraîner sur de fausses métriques).

---

## Phase 0b — Lecture de l'état actuel

### Lire docs/converter-memory.md

Extraire depuis la section **[LIRE EN PREMIER]** :
- Le **score de référence** (Score actuel)
- Les **tests anti-régression** (T01 min, T08 = 100 obligatoire)
- Les **niveaux de difficulté** des tests
- Les **prochaines priorités**
- **Ce qui a été tenté et n'a PAS fonctionné** (ne pas retenter ces approches)
- Le numéro de la dernière session (pour incrémenter)

### Lancer le benchmark baseline

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
Critères pondérés (previews.py) — seuils exacts au 2026-06-17 :
  - threads 18%       — ≤7=100, ≤10=80, ≤15=25, >15=0
  - stitches 18%      — <100=0, <500=20(+corrections L1/L2 density-aware), <1200=60, ≤50000=100, ≤150000=75, ≤500000=35, >500000=0
  - dimensions 14%    — dans zone 360×200mm et ≥20×5mm = 100, légèrement hors zone = 55, hors zone = 0
  - jumps 10%         — <0.5%=100, <2%=80, <4%=65, <8%=45, ≥8%=10
  - density 10%       — 0.5-20 pts/mm²=100, 0.2-0.5=75, 20-50=65, <0.2=20, >50=15
  - color_fidelity 18%— 100-int(ΔLab×1.2) × (0.4+0.6×ratio_fils)
  - coverage 12%      — ratio couleurs obtenues/demandées, floor 80 quasi-couverture, floor 55 partielle

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
9. Logger l'itération dans docs/converter-memory.md (en cours de session)
```

### Règles de sécurité absolues

- **Audit calibration (tous les 3 sessions)** : si la session est S7, S10, S13... → relire tous les seuils de scoring dans `previews.py` et valider contre réalité broderie PR1050X avant de faire des fixes (sinon on s'entraîne sur de fausses métriques)
- **Ne JAMAIS modifier** `models.py`, `views.py`, `settings.py`, `urls.py`, `celery.py`
- **Ne JAMAIS changer** les signatures des fonctions publiques exportées (celles importées dans `tasks.py`)
- **Ne JAMAIS utiliser** `shell=True` dans subprocess
- **Toujours utiliser** `Path` pour les chemins, jamais des strings hardcodées
- **Toujours typer** les nouveaux paramètres de fonctions
- **Rollback immédiat** si T01 ou T08 régressent de > 5 points après un fix
- **Maximum 2 fichiers modifiés par itération**
- Les seuls fichiers de service modifiables : `previews.py`, `png_processing.py`, `svg_utils.py`, `thread_color.py`, `pdf_processing.py`, `inkstitch.py`, `validation.py`

### Candidats connus (à re-évaluer à chaque session)

Ces candidats viennent des sessions précédentes. Ils peuvent être déjà résolus — toujours vérifier dans le code avant de les proposer. **Ne pas retenter** les approches marquées ❌ dans `docs/converter-memory.md` section "Ce qui a été tenté et n'a PAS fonctionné".

| Candidat | Fichier | Fonction | Tests concernés | Risque |
|----------|---------|----------|-----------------|--------|
| snap couleurs Lab : améliorer sélection fil Brother | `thread_color.py` | `snap_svg_colors_to_brother_palette()` | T01 (color_fidelity=66) | Faible |
| VTracer corner_threshold adaptatif selon n_colors | `png_processing.py` | `_vectorize_vtracer_cli()` | T02/T03/T06 | Faible |
| filter_micro_paths proportionnel à la taille design | `svg_utils.py` | `filter_micro_paths()` | T03/T04 | Moyen |
| reorder_svg_paths TSP-greedy amélioré | `svg_utils.py` | `reorder_svg_paths_for_minimal_jumps()` | T05 (jumps 2.1%) | Élevé |

---

## Mapping des 14 tests de référence

Ces tests sont codés en dur dans `tests/run_benchmark.py`. Ne pas les modifier sans raison — ils définissent la baseline inter-sessions.

| ID | Fichier (tests/manual/) | Format | Paramètres | Niveau | Cas testé |
|----|------------------------|--------|------------|--------|-----------|
| T01 | png/06-logo-monochrome-blanc.png | PNG | n=2, remove_bg, width=80mm | Medium | Logo mono blanc fond transparent |
| T02 | png/03-logo-multicolore.png | PNG | n=5, width=80mm | Easy-Medium | Logo multi-couleurs plats |
| T03 | png/07-ecusson-12couleurs.png | PNG | n=10, width=100mm | Hard | Écusson 12 couleurs complexe |
| T04 | png/08-texte-fond-colore.png | PNG | n=4, width=60mm | Medium | Texte sur fond coloré |
| T05 | png/09-photo-complexe-bruit.png | PNG | n=8, remove_bg, width=100mm | Hard/Ceiling | Photo avec bruit (ceiling naturel) |
| T06 | jpeg/12-logo-formes-simple.jpg | JPEG | n=6, width=80mm | Easy-Medium | Logo géométrique JPEG |
| T07 | webp/test-logo.webp | WebP | n=5, width=80mm | Easy-Medium | Logo WebP |
| T08 | svg/01-circle-simple.svg | SVG | direct, width=80mm | Easy | SVG trivial **(anti-régression, doit = 100)** |
| T09 | svg/07-logo-atelier-8couleurs.svg | SVG | direct, width=100mm | Medium | SVG multi-couleurs |
| T10 | svg/06-text-outline.svg | SVG | direct, width=80mm | Medium | Texte en contours fins SVG |
| T11 | pdf/test-logo.pdf | PDF | n=6, width=100mm | Medium | PDF vectoriel simple |
| T12 | pdf/test-scanned-pdf.pdf | PDF | n=4, width=80mm | Medium | PDF scanné (raster) |
| T13 | svg/08-texte-fin-contours.svg | SVG | direct, width=60mm | Hard | Texte très fin contours (lisibilité machine) |
| T14 | pdf/test-vectoriel-complexe.pdf | PDF | n=6, width=120mm | Hard | PDF vectoriel complexe grand format |

**Tests anti-régression prioritaires :** T01 (min=86) et T08 (doit=100) — un fix qui les dégrade de >5 pts doit être rollbacké immédiatement.
**T05 = ceiling naturel** : photo complexe avec bruit, plafond algorithmique — ne pas s'acharner.

---

## Phase 5 — Mise à jour de docs/converter-memory.md

Après les cycles d'amélioration, mettre à jour `docs/converter-memory.md` :

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

### 5f. Mettre à jour la section [LIRE EN PREMIER] de docs/converter-memory.md

- Mettre à jour **Score actuel** et la date de dernière session
- Mettre à jour **Prochaines priorités** (3 meilleurs candidats pour la prochaine session, en ordre de ROI)
- Ajouter à **Ce qui a été tenté et n'a PAS fonctionné** si une nouvelle approche a échoué cette session

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
