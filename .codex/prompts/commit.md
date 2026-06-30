Creer un commit git propre pour les changements en cours.

Etapes :
1. `git status` pour voir ce qui est modifie
2. `git diff` pour voir les changements detailles
3. Analyser les changements et rediger un message de commit clair
4. Stager les fichiers pertinents seulement
5. Creer le commit

Format du message :
- Premiere ligne : action courte (50 chars max), style imperatif en francais
- Corps optionnel si besoin d'expliquer le pourquoi

Fichiers a ne jamais committer :
- `.env`
- `db.sqlite3`
- `media/`
- `staticfiles/`
- `src/frontend/static/dist/`
- `src/frontend/node_modules/`

Attention :
- Ne pas embarquer de fichiers generes ou secrets
- Si le worktree est sale, ne pas committer les changements non lies sans accord explicite
