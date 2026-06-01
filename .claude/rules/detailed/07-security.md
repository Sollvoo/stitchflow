---
description: Sécurité — CSRF, secrets, validation fichiers, OWASP Top 10
paths: ["**/views.py", "**/settings.py", "**/forms.py", "**/services/**"]
priority: high
tags: [security, backend]
---

# Sécurité — StitchFlow

## Règles absolues

- **Jamais de secrets dans le code** — utiliser `.env` via `python-decouple`
- **Jamais faire confiance au nom de fichier utilisateur** — renommer avec UUID systématiquement
- **Jamais appeler de commandes externes depuis les vues** — passer par `services/inkstitch.py`
- **Toujours utiliser `subprocess.run`** avec `capture_output=True`, `timeout=120`, jamais `shell=True`

## Upload de fichiers

```python
# Toujours valider :
# 1. Extension (.svg uniquement)
# 2. Taille (10 MB max via SVG_MAX_FILE_SIZE)
# 3. Contenu XML (parser avec xml.etree.ElementTree)
# 4. Renommer avec UUID avant sauvegarde

import uuid
filename = f"{uuid.uuid4()}.svg"
```

## CSRF

- Toujours inclure `{% csrf_token %}` dans les formulaires POST
- Ne jamais exempter une vue sans raison documentée

## subprocess

```python
result = subprocess.run(
    [executable, arg1, arg2],  # Jamais shell=True avec input utilisateur
    capture_output=True,
    timeout=settings.INKSTITCH_TIMEOUT,
)
if result.returncode != 0:
    raise InkstitchError(result.stderr.decode())
```

## Fichiers uploadés

- `MEDIA_ROOT` hors du web root (pas accessible directement)
- Téléchargement via `FileResponse` avec `as_attachment=True`
- Vérifier ownership avant download (quand auth sera ajoutée)
