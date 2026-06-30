# Cas impossibles à broder

Ces fichiers **ne peuvent pas produire une bonne broderie**, même avec un convertisseur parfait. Ils sont conservés ici à titre de référence et pour tester la gestion des erreurs.

## Pourquoi ces fichiers sont "impossibles"

### Dégradés (`09-gradient-erreur-attendue.svg`, `10-degrade-multicouleur.png`)
La broderie ne supporte pas les transitions de couleur progressives. Une machine à broder ne peut créer qu'un changement net entre deux couleurs (un fil à la fois). Les dégradés doivent être approximés manuellement par un brodeur expert — un convertisseur automatique produira toujours un résultat de mauvaise qualité.

**Ce que fait StitchFlow** : pour les SVG avec `<linearGradient>` ou `<radialGradient>`, la conversion lève une `GradientNotSupportedError` explicite. Pour les PNG avec dégradés, la vectorisation produira une mosaïque de patches de couleur sans cohérence visuelle.

### Photos réalistes (`test-photo.jpg`)
Les photos naturelles contiennent des milliers de nuances et des transitions douces impossibles à reproduire en broderie. La quantification à 8–16 couleurs produit une image méconnaissable. La vectorisation génère une carte de régions sans rapport avec le sujet original.

**Ce que fait StitchFlow** : la conversion aboutira à un résultat avec score < 40/100. Ces cas dépassent le ceiling algorithmique de tout convertisseur automatique (~67.5/100).

## À ne pas confondre avec niveau3/photo/

`niveau3/photo/09-photo-complexe-bruit.png` est un cas "ceiling" (plafond algorithmique) — la conversion est possible mais le score restera autour de 60–70/100. Ce n'est pas impossible, c'est simplement difficile.

Les fichiers dans ce dossier, eux, produisent soit une erreur, soit un résultat inutilisable quelle que soit la qualité du convertisseur.
