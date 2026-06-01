Crée un commit git propre pour les changements en cours.

Étapes :
1. `git status` pour voir ce qui est modifié
2. `git diff` pour voir les changements détaillés
3. Analyser les changements et rédiger un message de commit clair
4. Stager les fichiers pertinents (jamais `.env`, `db.sqlite3`, `media/`, `staticfiles/`, `node_modules/`)
5. Créer le commit

Format du message :
- Première ligne : action courte (50 chars max), style impératif en français
- Corps optionnel si besoin d'expliquer le pourquoi

Fichiers à ne jamais committer :
- `.env` (secrets)
- `db.sqlite3` (données locales)
- `media/` (fichiers uploadés)
- `staticfiles/` (généré par collectstatic)
- `src/frontend/static/dist/` (généré par Vite build)
- `src/frontend/node_modules/`
