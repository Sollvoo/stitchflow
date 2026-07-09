Cherche les meilleurs skills, plugins MCP et agents Claude Code disponibles pour améliorer ce projet.

## Étapes

1. Utilise `mcp__mcp-registry__search_mcp_registry` avec les mots-clés pertinents pour le projet (ex : design, css, frontend, figma, accessibility, storybook)
2. Utilise `mcp__mcp-registry__suggest_connectors` pour afficher les connecteurs non encore installés
3. Liste les agents Claude Code disponibles (`Explore`, `Plan`, `explore-docs`, `websearch`) et indique lesquels sont utiles pour ce projet
4. Consulte la documentation en ligne si nécessaire via WebSearch/WebFetch
5. Mets à jour `.claude/rules/detailed/15-design-system.md` avec les recommandations et tools trouvés

## Focus pour StitchFlow

Ce projet utilise : Django 6, TailwindCSS v4, DaisyUI v5, HTMX 2, AlpineJS 3, Vite 6.

Recherche prioritaire :
- MCP Figma (sync design tokens)
- MCP Accessibility checker
- MCP Storybook / component documentation
- Tools CSS-in-context (Tailwind IntelliSense, DaisyUI docs)
- Agents spécialisés frontend/UI

## Résultat attendu

Liste des top 5 tools recommandés avec :
- Nom + description courte
- Comment l'installer
- Comment l'utiliser dans ce projet spécifiquement
