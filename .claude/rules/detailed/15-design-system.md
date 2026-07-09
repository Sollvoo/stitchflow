# Design System — StitchFlow

S'applique à : `**/templates/**/*.html`, `**/assets/*.css`

## Tokens disponibles (theme.css)

| Token CSS | Valeur | Usage |
|---|---|---|
| `--color-primary-*` | Corail #c45142 (50→900) | Actions, boutons, accents |
| `--color-secondary-*` | Sauge #617055 | Éléments secondaires |
| `--color-neutral-50` | Crème #fcf7f1 | Fond page, navbar, cards |
| `--font-display` | Iowan Old Style / Palatino / Georgia | Titres h1/h2/h3 |
| `--font-body` | System UI | Corps de texte |
| `--shadow-thread` | Ombre douce pour panels | sf-panel |
| `--shadow-stitch` | Ombre plus légère | sf-stitch-card |

## Composants custom — `@layer components` dans styles.css

### `.sf-panel`
Card principale — fond crème, border-radius 24px, ombre douce.
```html
<div class="sf-panel p-6">…</div>
<!-- avec couleur de bordure overridée : -->
<div class="sf-panel border-success/30">…</div>
```

### `.sf-stitch-card`
Card secondaire — même style que sf-panel mais ombre plus légère. Pour grilles, items de liste.
```html
<div class="sf-stitch-card p-4 hover:shadow-lg transition-shadow">…</div>
```

### `.sf-kicker`
Badge pill — texte petit en majuscules, couleur primaire, fond translucide.
```html
<!-- Toujours utiliser avec un wrapper flex pour centrer -->
<div class="flex justify-center">
  <span class="sf-kicker">Étape 1</span>
</div>
<!-- Variante couleur custom (secondary) : -->
<span class="sf-kicker" style="color: var(--color-secondary-600); border-color: color-mix(in oklab, var(--color-secondary-600) 15%, transparent); background-color: color-mix(in oklab, var(--color-secondary-100) 65%, transparent);">Étape 2</span>
```
**Attention** : `sf-kicker` est `display: inline-flex`. Ne jamais utiliser `mx-auto` directement dessus — entourer d'un `flex justify-center`.

### `.sf-thread-dots`
Fond texturé en points radiaux. Toujours combiné avec `sf-panel` sur les sections hero.
```html
<div class="sf-panel sf-thread-dots px-8 py-14 text-center">…</div>
```

### `.sf-focus-ring`
Focus visible accessible sur inputs custom.

## Règles typo

- `h1`, `h2`, `h3` → automatiquement en font-display via `@layer base`
- Ajouter `font-display font-bold` sur les titres principaux pour le poids
- Ne jamais utiliser `font-extrabold` seul — toujours avec `font-display`

## Fonds et backgrounds

**IMPORTANT** : `bg-base-100` peut ne pas être opaque selon le contexte DaisyUI v5/oklch.
Pour les éléments sticky ou teleportés (navbar, modals, dropdowns) :
```html
<!-- Utiliser l'inline style explicite -->
style="background-color: #fcf7f1"
```
Jamais utiliser `bg-base-100` seul sur la navbar ou un dropdown téléporté.

## DaisyUI v5 — composants utilisés

- `btn btn-primary`, `btn-ghost`, `btn-outline`, `btn-lg`, `btn-sm`, `btn-xs`, `btn-square`
- `badge`, `badge-success`, `badge-warning`, `badge-error`
- `alert`, `alert-info`, `alert-error`, `alert-warning`
- `loading loading-spinner`
- `tooltip tooltip-bottom` + `data-tip="…"` (pour boutons icon-only)
- `collapse collapse-arrow` (pour sections repliables)
- `select select-bordered`, `input input-bordered`, `checkbox checkbox-primary`
- `range range-primary range-xs`
- **NE PAS utiliser** : `stats stats-horizontal` (whitespace excessif) → remplacer par `grid grid-cols-3 divide-x`
- **NE PAS utiliser** : `navbar-start`/`navbar-end` (problème de rendu DaisyUI v5) → utiliser `flex items-center justify-between`

## Tooltips sur boutons icon-only

Pattern DaisyUI v5 pour bouton icône avec tooltip au survol :
```html
<div class="tooltip tooltip-bottom" data-tip="Description de l'action">
  <button class="btn btn-ghost btn-xs btn-square">
    <svg>…</svg>
  </button>
</div>
```

## Skills / Agents recommandés pour le design

### Agents Claude Code intégrés

| Agent | Utilisation design |
|---|---|
| `explore-docs` | Documentation Tailwind v4, DaisyUI v5, AlpineJS 3 avec Context7 |
| `websearch` | Recherche composants, patterns UI, exemples DaisyUI/Alpine |
| `Plan` | Planifier refonte de composants ou pages |
| `Explore` | Localiser rapidement un composant dans les templates |

### Skills custom disponibles

| Skill | Fichier | Description |
|---|---|---|
| `/find-skill` | `.claude/commands/find-skill.md` | Recherche MCP servers et skills utiles pour ce projet |
| `/commit` | `.claude/commands/commit.md` | Commit git propre |

### MCP servers utiles à connecter

- **Context7** (via agent `explore-docs`) — documentation précise avec exemples de code pour Tailwind v4, DaisyUI v5, AlpineJS
- **MCP Registry** (`mcp__mcp-registry__search_mcp_registry`) — recherche de nouveaux connecteurs MCP

### Pour les prochaines intégrations design

Si disponibles via `/find-skill` :
- **Figma MCP** — sync design tokens Figma → CSS custom properties
- **Storybook MCP** — documentation des composants sf-* avec exemples visuels
- **Accessibility checker** — vérification WCAG des contrastes et interactions

## Checklist avant commit d'une page HTML

- [ ] Tous les `h1`/`h2`/`h3` ont `font-display font-bold` ou `font-display font-semibold`
- [ ] Les cards principales utilisent `sf-panel`, les secondaires `sf-stitch-card`
- [ ] Les badges de statut utilisent `sf-kicker` (pas `badge badge-*` pour les étapes)
- [ ] Les boutons icône-seul ont `tooltip` + `data-tip`
- [ ] La navbar et les dropdowns téléportés ont `style="background-color: #fcf7f1"` explicite
- [ ] `npm run build` passe sans erreur
- [ ] `python src/manage.py check` passe (0 erreurs)
