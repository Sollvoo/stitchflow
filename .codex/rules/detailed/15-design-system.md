---
description: Design system StitchFlow - theme DaisyUI, tokens Tailwind, direction visuelle
paths: ["src/frontend/assets/styles.css", "src/frontend/assets/theme.css", "src/frontend/tailwind.config.js", "**/templates/**/*.html"]
priority: high
tags: [frontend, tailwind, daisyui, design-system]
---

# Design System - StitchFlow

## Direction visuelle

- StitchFlow suit une direction `atelier moderne` : chaleureux, artisanal, lisible, minimaliste.
- On evoque la broderie par la matiere, les tons fil/textile et les details, pas par des effets kitsch ou des pictogrammes partout.
- L'interface doit rester plus premium que "loisir creatif enfantin".

## Theme technique obligatoire

- Le theme DaisyUI de reference est `stitchflow`.
- Les tokens Tailwind et CSS vivent dans :
  - `src/frontend/tailwind.config.js`
  - `src/frontend/assets/theme.css`
  - `src/frontend/assets/styles.css`
- Ne pas reintroduire des palettes locales dans les templates si un token existe deja.

## Palette

- `primary` = corail brique de fil pour les CTA et actions majeures
- `secondary` = sauge textile pour les accents de support
- `accent` = bleu atelier doux pour les infos, liens secondaires, respirations
- `neutral` = encre chaude pour le texte et la structure
- `base-100/200/300` = fonds creme et beiges chauds, jamais blanc froid

## Regles d'usage

- Utiliser d'abord les composants DaisyUI (`btn`, `card`, `badge`, `alert`, `input`, `navbar`) puis affiner avec des utilitaires Tailwind.
- Preferer les classes de theme (`bg-base-100`, `text-base-content`, `border-base-300`, `btn-primary`) aux couleurs hardcodees.
- Les helpers locaux autorises sont ceux de `styles.css` comme `sf-panel`, `sf-stitch-card`, `sf-kicker`, `sf-focus-ring`.
- Les fonds doivent rester subtils : texture legere, gradients doux, jamais de blobs generiques ni d'effets neon.
- Les arrondis doivent etre souples et coherents. Viser un rendu "piece textile bien finie", pas "dashboard B2B sec".

## Interdits

- Pas de violet SaaS generique comme couleur dominante.
- Pas de noir pur ni de blanc pur comme fond principal.
- Pas de styles inline de couleur, bordure ou ombre si l'equivalent theme existe.
- Pas de multiplication de couleurs d'accent sur une meme surface.
- Pas de composants qui paraissent "jouets" ou trop crafts marketplace.

## Copy et UX

- Le texte doit etre simple, concret, humain, sans jargon technique inutile.
- Les CTA doivent parler resultat utilisateur (`Convertir un fichier`, `Voir mes conversions`) plutot que mecanique interne.
- Responsive obligatoire : mobile d'abord, sans perte de hierarchie ni de lisibilite.
