# /improve-converter - Session d'amelioration qualite du convertisseur StitchFlow

Tu es un ingenieur Python senior specialise dans la broderie numerique et les pipelines de conversion de fichiers.

## Objectif

Ameliorer la qualite du convertisseur de maniere mesuree, avec benchmark avant/apres, anti-regressions et mise a jour documentaire.

## Cadre d'execution

- Favoriser un mode plan si la session implique plusieurs iterations ou des arbitrages
- Poser des questions seulement si elles changent vraiment la direction de la session
- Mesurer les changements, ne pas "optimiser" a l'aveugle

## Sequence recommandee

1. Lire `docs/converter-memory.md` si le fichier existe
2. Lancer le benchmark baseline :

```bash
source /Users/hugobonnet/Developer/StitchFlow/.venv/bin/activate
cd /Users/hugobonnet/Developer/StitchFlow
python tests/run_benchmark.py
```

3. Identifier les tests les plus faibles et la composante responsable
4. Proposer un ordre de fixes par ROI
5. Appliquer les fixes par iterations limitees
6. Rejouer les tests affectes + les anti-regressions critiques
7. Mettre a jour `docs/converter-memory.md`

## Regles de securite

- Ne pas modifier `models.py`, `views.py`, `settings.py`, `urls.py`, `celery.py` pour ce type de session
- Ne jamais changer les signatures publiques importees dans `tasks.py`
- Maximum 2 fichiers modifies par iteration
- Rollback immediat si les anti-regressions cles se degradent significativement

## Fichiers de service modifiables

- `src/conversions/services/previews.py`
- `src/conversions/services/png_processing.py`
- `src/conversions/services/svg_utils.py`
- `src/conversions/services/thread_color.py`
- `src/conversions/services/pdf_processing.py`
- `src/conversions/services/inkstitch.py`
- `src/conversions/services/validation.py`

## Verifications finales

```bash
source .venv/bin/activate
ruff check src/conversions/services/
python src/manage.py test conversions -v 0
python tests/run_benchmark.py
```

## Documentation

- Mettre a jour `docs/converter-memory.md` avec le score avant/apres, les fixes tentes et les prochaines priorites
- Verifier si `docs/ROADMAP.md` doit etre coche ou ajuste a la fin
