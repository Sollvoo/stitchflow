---
description: Code style - Ruff linter, Black formatter, conventions Python
paths: ["**/*.py"]
priority: low
tags: [quality, backend]
---

# Code Style - StitchFlow

## Formatter

**USE**: Black
- 88 caracteres line length

```toml
[tool.black]
line-length = 88
target-version = ['py312']
extend-exclude = '''
/(\.git|\.venv|migrations)/
'''
```

## Linter

**USE**: Ruff

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I"]
```

```bash
source .venv/bin/activate
ruff check src/
black src/
```

## Conventions

- **Imports** : stdlib -> third-party -> local, separes par ligne vide
- **Types** : typer les fonctions autant que possible
- **Chemins** : toujours `Path`, jamais de strings hardcodees
- **Secrets** : toujours via `python-decouple` / `.env`, jamais dans le code
- **Statuts** : utiliser `ConversionJob.Status.*`, jamais les strings directement
- **Commandes externes** : toujours via `subprocess.run` dans `services/`, jamais dans les vues

## Commentaires

- Zero commentaire par defaut - les noms doivent suffire
- Ajouter un commentaire uniquement quand le **pourquoi** n'est pas evident
- Eviter les docstrings longues si une fonction peut rester lisible avec de bons noms
