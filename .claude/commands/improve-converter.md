# /improve-converter — Session d'amélioration qualité du convertisseur StitchFlow

Tu es un ingénieur Python senior spécialisé dans la broderie numérique et les pipelines de conversion de fichiers.

**Ce que fait cette commande :**
1. Recueille les cas ratés signalés par l'utilisateur (optionnel)
2. Lit l'état actuel depuis `docs/converter-memory.md`
3. Lance le benchmark complet pour obtenir le score "avant" réel
4. **Diagnostique intelligemment** chaque échec par étape de pipeline (PNG→SVG vs SVG→PES vs scoring)
5. Analyse les résultats avec `/sequential-thinking` — ROI = impact × tests affectés / effort
6. Applique les fixes en itérations mesurées avec benchmark partiel après chaque fix
7. Met à jour `docs/converter-memory.md` et affiche un rapport final

---

## IMPORTANT — Mode plan obligatoire

**Invoquer immédiatement `/plan` (EnterPlanMode) au début de cette commande.** Ne pas écrire de code tant que le plan n'est pas approuvé par l'utilisateur via ExitPlanMode.

En mode plan :
1. Lis les fichiers sources (Read tool autorisé)
2. Lance le benchmark (Bash tool autorisé en lecture)
3. Produis le diagnostic et le plan complet avec justification ROI par étape de pipeline
4. Pose les questions AskUserQuestion nécessaires
5. Attends l'approbation — puis seulement commence les modifications de code

---

## Phase 0a — Recueil des cas ratés (optionnel, prioritaire si fournis)

**Si l'utilisateur a indiqué des fichiers ou conversions qui ont mal marché**, les noter immédiatement :

```
Fichier signalé : <chemin ou description>
Symptôme décrit : <ce que l'utilisateur a observé>
```

Pour chaque cas signalé → lancer la **Phase 0d - Diagnostic pipeline** dessus AVANT le benchmark général.

---

## Phase 0b — Questions utilisateur

Utiliser `AskUserQuestion` pour orienter la session :

**Q1 — Priorité de cette session ?**
- "Corriger des cas ratés signalés" (Recommandé si l'utilisateur a décrit des échecs)
- "Amélioration pipeline — réduire jumps / améliorer coverage"
- "Audit calibration scoring (obligatoire session S9, S12...)"
- "Nouveaux tests difficiles — élargir le benchmark"

**Q2 — Rythme d'ajout de nouveaux tests ?**
- "Progressif — 2 tests maximum" (Recommandé)
- "Aucun nouveau test — se concentrer sur les tests existants"
- "Agressif — 3 à 5 nouveaux tests"

**Note audit scoring :** si la session est S9, S12, S15... (numéro divisible par 3) → **audit calibration OBLIGATOIRE** des seuils dans `previews.py`.

---

## Phase 0c — Lecture de l'état actuel

Extraire depuis `docs/converter-memory.md` section **[LIRE EN PREMIER]** :
- Score de référence actuel
- Tests anti-régression (T01 min, T08 = 100 obligatoire)
- Prochaines priorités identifiées
- **Ce qui a été tenté et n'a PAS fonctionné** (ne jamais retenter)
- Numéro de la dernière session → incrémenter pour cette session

---

## Phase 0d — Diagnostic pipeline par étape (CRITIQUE)

Pour **chaque fichier signalé comme raté** ET pour les tests qui ont un score < 93 dans le benchmark :

### Étape D1 — Identifier la phase d'échec

Lancer le diagnostic en deux temps :

```python
# 1. Tester PNG→SVG seul (sans Ink/Stitch)
# Dans run_benchmark.py ou directement :
from conversions.services import png_processing, pdf_processing
svg_path = png_processing.vectorize_png_to_svg(image_path, n_colors=N, ...)
# Inspecter le SVG généré : nombre de paths, couleurs, taille

# 2. Tester SVG→PES seul (avec un SVG connu-bon)
from conversions.services import inkstitch
result = inkstitch.convert_svg_to_pes(svg_path, target_width_mm=80)
# Inspecter le PES : nb fils, nb points, dimensions
```

### Étape D2 — Classer l'échec

Pour chaque test sous-performant, classifier dans l'une de ces catégories :

| Code | Étape | Symptômes typiques |
|------|-------|-------------------|
| `VECT` | PNG→SVG vectorisation | Mauvais nombre de couleurs, artefacts, zones manquantes |
| `SVG_PREP` | Préparation SVG pour Ink/Stitch | Tatami massif, namespace manquant, paths ignorés |
| `INK_STITCH` | Conversion Ink/Stitch | PES vide, timeout, dimensions incorrectes |
| `SCORING` | Calcul score uniquement | Score ne reflète pas la qualité réelle |

### Étape D3 — Inspecter le SVG intermédiaire

Pour les échecs `SVG_PREP` ou `INK_STITCH`, inspecter le SVG qui entre dans Ink/Stitch :

**Checklist SVG obligatoire :**
- [ ] `xmlns:inkstitch` déclaré dans la balise `<svg>` ?
- [ ] Tous les paths ont un attribut `fill` (pas seulement `stroke`) ?
- [ ] Tous les paths se terminent par `Z` (fermés) ?
- [ ] Y a-t-il un path de fond couvrant >80% du viewBox ? (tatami potentiel)
- [ ] Les attributs `inkstitch:row_spacing_mm` sont-ils présents et bien syntaxés ?
- [ ] Le viewBox est-il en mm (non en pixels) ?

**Commande rapide d'inspection :**
```bash
# Lire l'en-tête SVG pour vérifier le namespace
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('path/to/intermediate.svg')
root = tree.getroot()
print('Namespace:', root.attrib)
print('Paths:', len(root.findall('.//{http://www.w3.org/2000/svg}path')))
print('Has inkstitch:', 'inkstitch' in str(root.attrib))
"
```

### Étape D4 — Résumé diagnostic

Avant d'entrer en analyse, produire ce tableau :

```
DIAGNOSTIC PRÉ-SESSION
═══════════════════════════════════════════════════
Fichiers signalés par l'utilisateur :
  [FICHIER] → étape d'échec : [CODE] — [description courte]

Tests benchmark sous-performants (< 93) :
  TXX (score=YY) → étape d'échec : [CODE] — [critère le plus faible]
═══════════════════════════════════════════════════
```

---

## Phase 1 — Benchmark baseline

```bash
# Windows (PowerShell)
& "C:\Users\hugob\Desktop\Developer\StichFlow\.venv\Scripts\python.exe" tests/run_benchmark.py

# macOS/Linux
source .venv/bin/activate && python tests/run_benchmark.py
```

Le script est autonome (sans Celery, sans HTTP). Il appelle directement les fonctions de service Django.

**Le score "avant" de cette session = score moyen de ce premier run.**

Si un test individuel échoue → noter l'erreur, identifier l'étape via Phase 0d, continuer.

---

## Phase 2 — Analyse avec /sequential-thinking

Utiliser `/sequential-thinking` (6–8 pensées) pour analyser les résultats.

**Questions à traiter dans l'analyse :**

1. Quels tests ont les pires scores ? Quel est leur CODE de diagnostic (VECT / SVG_PREP / INK_STITCH / SCORING) ?
2. Y a-t-il des patterns : tous les PNG ratent sur SVG_PREP ? Tous les PDFs sur VECT ?
3. Pour les cas signalés par l'utilisateur : confirmer/infirmer le diagnostic par étape
4. Pour les 3 meilleurs candidats fixes :
   - Quel delta de score est réaliste ?
   - Combien de tests sont affectés (et sur quelle étape) ?
   - Risque de régression T01 (PNG mono, min=86) et T08 (SVG trivial, doit=100) ?
   - Effort : 10 lignes / 50 lignes / refactor complet ?
5. Quel est l'ordre optimal des fixes (plus impactant → plus risqué) ?
6. Y a-t-il des fixes à éviter (rompent une invariante, modifient >2 fichiers) ?

**Architecture du score (référence) :**

```
Critères pondérés (previews.py) :
  threads      18% — ≤7=100, ≤10=80, ≤15=25, >15=0
  stitches     18% — <100=0, <500=20(+density-aware), <1200=60, ≤50000=100, ≤150000=75, ≤500000=35, >500000=0
  dimensions   14% — dans zone machine (profil utilisateur ou 360×200mm) = 100
  jumps        10% — <0.5%=100, <2%=80, <4%=65, <8%=45, ≥8%=10 + floor 65 si ≤15 sauts absolus
  density      10% — 0.5–20 pts/mm²=100, 0.2–0.5=75, 20–50=65, <0.2=20, >50=15
  color_fidelity 18% — 100−int(ΔLab×1.2) × (0.4+0.6×ratio_fils), floor 70 si ratio≥0.8 et ΔLab≤35
  coverage     12% — ratio couleurs obtenues/demandées, floor 80 quasi-couverture, floor 65 partielle

Gate (plafond conditionnel) :
  Pour raster (PNG/JPEG/WebP/PDF scanné) : essential_min = min(s_score, c_score)
  Pour SVG direct : essential_min = s_score seul
  essential_min < 20 → plafonné à 40 ; essential_min < 40 → plafonné à 65
```

---

## Phase 3, 4, 5 — Trois cycles d'amélioration

### Structure de chaque cycle

```
1. Sélectionner le fix retenu (meilleur ROI non encore appliqué)
2. Identifier l'étape de pipeline ciblée (VECT / SVG_PREP / INK_STITCH / SCORING)
3. Lire le fichier concerné AVANT de modifier (Read tool)
4. Appliquer le fix (Edit tool — jamais Write sur fichier existant)
5. Vérifier la syntaxe :
      # Windows
      .venv\Scripts\python.exe -m ruff check src/conversions/services/
      # macOS
      source .venv/bin/activate && ruff check src/conversions/services/
6. Lancer les tests unitaires :
      # Windows
      .venv\Scripts\python.exe src/manage.py test conversions -v 0
      # macOS
      source .venv/bin/activate && python src/manage.py test conversions -v 0
7. Re-lancer le benchmark sur les tests affectés + T01 + T08 :
      python tests/run_benchmark.py --tests T01,T08,<tests_affectés>
8. Mesurer le delta score
9. Si T01 ou T08 régressent de > 5 points → rollback immédiat
10. Logger l'itération dans docs/converter-memory.md (en cours de session)
```

### Règles de sécurité absolues

- **Jamais modifier** `models.py`, `views.py`, `settings.py`, `urls.py`, `celery.py`, `tasks.py`
- **Jamais changer** les signatures des fonctions publiques exportées
- **Jamais** `shell=True` dans subprocess
- **Toujours** `Path` pour les chemins, jamais strings hardcodées
- **Toujours typer** les nouveaux paramètres
- **Rollback immédiat** si T01 ou T08 régressent de > 5 points
- **Maximum 2 fichiers modifiés par itération**
- Fichiers modifiables : `previews.py`, `png_processing.py`, `svg_utils.py`, `thread_color.py`, `pdf_processing.py`, `inkstitch.py`, `validation.py`

### Candidats fixes par étape de pipeline

#### Étape VECT (PNG→SVG vectorisation)
| Candidat | Fichier | Fonction | Tests | Risque |
|----------|---------|----------|-------|--------|
| corner_threshold VTracer adaptatif n_colors | `png_processing.py` | `_vectorize_vtracer_cli()` | T02/T03/T06 | Faible |
| filter_micro_paths proportionnel taille design | `svg_utils.py` | `filter_micro_paths()` | T03/T04 | Moyen |
| Seuil clustering Lab adaptatif | `png_processing.py` | `_consolidate_svg_colors()` | T03/T11 | Faible |

#### Étape SVG_PREP (préparation SVG pour Ink/Stitch)
| Candidat | Fichier | Fonction | Tests | Risque |
|----------|---------|----------|-------|--------|
| Injection namespace xmlns:inkstitch | `svg_utils.py` | `inject_inkstitch_namespace()` (à créer) | Tous PNG/PDF | Faible |
| Fix remove_background_fill rectangles arrondis | `svg_utils.py` | `remove_background_fill()` | T02/T03/T06 | Moyen |
| Fermeture paths non fermés | `svg_utils.py` | `_close_open_paths()` (à créer) | T09/T10 | Faible |
| Injection params Ink/Stitch selon taille zone | `svg_utils.py` | `inject_inkstitch_params()` (à créer) | Tous raster | Moyen |

#### Étape SCORING (calibration)
| Candidat | Fichier | Fonction | Tests | Risque |
|----------|---------|----------|-------|--------|
| T03 : force_max_svg_colors(8) si n_colors≥10 | `svg_utils.py` / `tasks.py` | `force_max_svg_colors()` | T03 | Moyen |
| T11/T14 : debug couleurs perdues PDF vectoriel | `pdf_processing.py` | pipeline PDF | T11/T14 | Moyen |

**Ne jamais retenter :**
- Coefficient color_fidelity 1.5 (durcirait scores sans améliorer qualité réelle)
- Algorithme TSP pour jumps T05 (ceiling naturel photo)
- Fix thread_color.py pour T01 ΔLab=28.4 (lacune physique palette Brother)

---

## Phase 6 — Ajout de nouveaux tests (si décidé en Phase 0b)

Si l'utilisateur a signalé des fichiers ratés → proposer de les ajouter au benchmark :

```python
# Template d'ajout dans run_benchmark.py
TestCase(
    id="T21",
    file="tests/manual/niveau2/logo/mon-logo-rate.png",
    format="PNG",
    params={"n_colors": 4, "target_width_mm": 80},
    niveau="Medium",
    description="Logo signalé raté par l'utilisateur — fond arrondi tatami",
    min_score=75,  # Objectif minimal réaliste
),
```

**Règles d'ajout :**
- Toujours inclure un `min_score` réaliste (pas 95 pour un cas Hard)
- Copier le fichier dans `tests/manual/niveau{1,2,3}/` selon la difficulté estimée
- Maximum 2 nouveaux tests par session (éviter de diluer le score moyen)
- Lancer le benchmark complet après ajout pour mesurer l'impact sur le score moyen

---

## Phase 7 — Mise à jour de docs/converter-memory.md

### 7a. Tableau des sessions
```markdown
| <N> | <YYYY-MM-DD> | <score_avant>/100 | <score_après>/100 | <delta signé> | <nb tests> |
```

### 7b. Section "### Session N — YYYY-MM-DD"
```markdown
### Session N — YYYY-MM-DD

**Étape ciblée : [VECT / SVG_PREP / INK_STITCH / SCORING]**

**Iter 1 — <titre court>** (`<fichier modifié>`)
- Correction : <description précise>
- Raison : <pourquoi ça améliore la qualité broderie>
- Étape pipeline : [VECT / SVG_PREP / INK_STITCH / SCORING]
- Impact mesuré : <TXX score_avant→score_après (+delta)>
```

### 7c. Mettre à jour "Problèmes connus non résolus"
- Retirer les problèmes résolus
- Ajouter les nouveaux découverts avec leur étape pipeline
- Mettre à jour les scores

### 7d. Mettre à jour [LIRE EN PREMIER]
- Score actuel + date
- Prochaines priorités (3 candidats, avec étape pipeline)
- Ce qui n'a pas fonctionné (si nouvelle tentative échouée)

---

## Rapport final obligatoire

```
═══════════════════════════════════════════════════
  RAPPORT QUALITÉ CONVERTISSEUR — Session N
═══════════════════════════════════════════════════

  Score avant cette session :  XX.X / 100
  Score après cette session  :  XX.X / 100
  Delta                      :  +X.X pts

  Score visé (objectif long terme) : 95.0 / 100
  Objectif atteint : OUI / NON (écart : X.X pts)

  Étapes pipeline travaillées cette session :
    VECT      : X fix(es)
    SVG_PREP  : X fix(es)
    SCORING   : X fix(es)

  Tests améliorés  : TXX (+N), TXX (+N), ...
  Tests stables    : TXX, TXX, ...
  Tests régressés  : aucun (ou détail si régression)

  Fixes appliqués :
    Iter 1 [ÉTAPE] : <titre> → fichier.py
    Iter 2 [ÉTAPE] : <titre> → fichier.py
    Iter 3 [ÉTAPE] : <titre> → fichier.py

  Prochaines priorités :
    1. [ÉTAPE] <priorité 1>
    2. [ÉTAPE] <priorité 2>
    3. [ÉTAPE] <priorité 3>
═══════════════════════════════════════════════════
```

---

## Vérifications finales

```bash
# Windows
.venv\Scripts\python.exe -m ruff check src/conversions/services/
.venv\Scripts\python.exe src/manage.py test conversions -v 0
.venv\Scripts\python.exe tests/run_benchmark.py

# macOS
source .venv/bin/activate
ruff check src/conversions/services/
python src/manage.py test conversions -v 0
python tests/run_benchmark.py
```

Si les tests unitaires régressent → rollback du fix concerné.

---

## Contexte machine broderie (référence)

**Brother entrepreneur pro X PR1050X** (machine beta) :
- 10 aiguilles max (≤10 fils, idéal ≤7)
- Zone broderie : 360×200mm
- Format natif : PES v1
- Points max : < 500 000

**Contraintes adaptées au profil machine** (Phase 13a) :
- Si l'utilisateur a configuré sa machine → utiliser ses contraintes
- Sinon → Brother PR1050X par défaut

---

## Règle ROADMAP.md

À la fin, vérifier si des éléments de `docs/ROADMAP.md` peuvent être cochés. Si oui, les cocher.
