---
description: Code style — Ruff linter, Black formatter, conventions Python
paths: ["**/*.py"]
priority: low
tags: [quality, backend]
---

# Code Style — StitchFlow

## Formatter

**USE**: Black (uncompromising formatter)
- 88 caractères line length

```toml
# pyproject.toml
[tool.black]
line-length = 88
target-version = ['py312']
extend-exclude = '''
/(\.git|\.venv|migrations)/
'''
```

## Linter

**USE**: Ruff (ultra-rapide, Rust)

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I"]
```

```bash
source .venv/bin/activate
ruff check src/          # Linter
black src/               # Formatter
```

## Conventions

- **Imports** : stdlib → third-party → local, séparés par ligne vide
- **Types** : typer les fonctions (paramètres + retour) autant que possible
- **Chemins** : toujours `Path`, jamais strings hardcodées
- **Secrets** : toujours via `python-decouple` / `.env`, jamais dans le code
- **Statuts** : utiliser `ConversionJob.Status.*`, jamais les strings directement
- **Commandes externes** : toujours via `subprocess.run` dans `services/`, jamais dans les vues

## Commentaires

- Zéro commentaire par défaut — les noms parlent d'eux-mêmes
- Un commentaire uniquement quand le **POURQUOI** est non évident (contrainte cachée, workaround)
- Jamais de docstrings multi-paragraphes
