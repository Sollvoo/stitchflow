# Codex Mirror

Ce dossier reflète les ressources locales déjà maintenues pour Claude Code dans `.claude/`.

Objectif :
- donner à Codex un point d'entrée explicite ;
- garder des règles et prompts locaux au projet ;
- éviter de dépendre uniquement d'instructions globales.

Convention de mapping :
- `.claude/rules/**` -> `.codex/rules/**`
- `.claude/commands/*.md` -> `.codex/prompts/*.md`

Quand une ressource existe des deux côtés, la version `.codex/` fait foi pour Codex.
