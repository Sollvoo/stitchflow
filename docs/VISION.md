# StitchFlow — Vision Produit

## Le problème

Une brodeuse indépendante (entreprise individuelle, ~€2 000/mois de chiffre d'affaires) paye **10 € par fichier** à un prestataire pour convertir ses designs en fichiers de broderie PES. Même pour des designs simples — logos, formes géométriques, texte — elle n'a pas d'alternative : les logiciels de digitalisation professionnels (Wilcom, Embrilliance) coûtent des centaines d'euros et nécessitent une formation. Résultat : chaque conversion simple lui coûte du temps (délai 24h) et de l'argent.

## La solution

StitchFlow automatise les conversions **simples à moyennes** instantanément, pour un coût inférieur à ce que facture un prestataire humain. L'objectif n'est pas de remplacer les digitaliseurs professionnels — les designs complexes (ombrés, très détaillés, artistiques) restent leur terrain. StitchFlow prend en charge la "fast lane" : les conversions répétitives et prévisibles qui ne méritent pas 10 €.

## Utilisateur cible (beta)

- **Profil** : artisane indépendante, machine Brother (modèle à confirmer), fait principalement des designs simples à moyens pour ses clients
- **Douleur principale** : payer 10 €/conversion + délai d'attente pour des fichiers qui devraient pouvoir être automatisés
- **Gain attendu** : économiser sur les conversions simples, payer le prestataire humain uniquement pour les designs complexes qui le justifient

## Positionnement

> "La conversion automatique de broderie pour les designs qui n'ont pas besoin d'un humain."

StitchFlow ne prétend pas être meilleur qu'un digitaliseur expert sur les cas difficiles. Il est **plus rapide, moins cher et suffisant** pour les cas simples.

## Ce que StitchFlow fait bien (scope)

- Logos vectoriels (SVG, PDF vectoriel) avec aplats de couleurs franches
- Designs géométriques simples
- Texte converti en courbes
- PNG/JPEG nets (logos sur fond blanc ou transparent)
- Designs ≤ 10 couleurs, ≤ 360 × 200 mm

## Ce que StitchFlow ne fait pas encore (et doit le dire)

- Designs avec dégradés de couleur → rediriger vers un prestataire
- Photos réalistes → résultat imprévisible, à utiliser en connaissance de cause
- Très petit détails (< 2mm) → perte de fidélité garantie
- Designs > 10 couleurs → hors capacité Brother PR1050X

L'application doit être **honnête sur ses limites**. Mieux vaut afficher "ce design est trop complexe pour être automatisé correctement" que de livrer un résultat décevant.

## Priorité machine cible

Phase initiale : **Brother PES uniquement** (machine de l'utilisatrice beta).  
Évolution : support multi-machines (DST, JEF, VP3) une fois la base stabilisée.

## Modèle économique envisagé

- Prix cible : **€3 par conversion** (recommandé d'après analyse marché juin 2025 — voir `docs/differenciateurs.md` §4)
  - €2 : trop proche du "gratuit" symboliquement, marge trop faible
  - €3 : 3× moins cher que le prestataire actuel (€10), défendable vs Etsy offshore ($3–5 mais délai)
  - €5 : possible si différenciation très forte, mais concurrence plus directe avec digitiseurs $5
- Positionnement : pas gratuit (la gratuité signale la mauvaise qualité dans ce marché), pas cher (accessible aux artisans)
- Plans suggérés :
  - **Pay-as-you-go** : €3/conversion (pas d'engagement, idéal pour valider)
  - **Abonnement mensuel** : €19/mois illimité (ROI immédiat pour 7+ conversions/mois)
  - **Essai** : 3 conversions gratuites pour valider sans risque

## Roadmap macro

1. **Beta fermée** — Valider avec l'utilisatrice que StitchFlow remplace ses conversions simples
2. **Auth + Dashboard** — Comptes, historique, quota
3. **Éditeur SVG broderie** — Contrôle fin sur les couleurs/fils, ordre de broderie
4. **SaaS** — Paiement, plans, multi-machines
5. **Détection de complexité** — Recommander le bon outil selon le design

## Ce qui différencie StitchFlow des concurrents

Analyse concurrentielle complète : `docs/analyse-concurrentielle.md`

| Critère | Prestataire humain ($15–20 pro, $3–5 offshore) | Hatch/SewArt (logiciel) | Ink/Stitch (gratuit) | StitchFlow |
|---|---|---|---|---|
| Vitesse | 1h–24h (jamais instantané) | Immédiat (si formé) | Immédiat (si expert Inkscape) | Immédiat |
| Prix | $3–20/conversion selon qualité | $75–$1 199 (logiciel, une fois) | Gratuit | €3/conversion |
| Qualité | Variable à excellente | Bonne à excellente | Dépend de l'opérateur | Bonne sur designs simples |
| Accessibilité | Email/site externe | Installation requise, Windows | Installation Inkscape + extension | Web, aucune install |
| Preview des fils | Aucune avant livraison | Aucune | Aucune | ✅ Fils Brother avant conversion |
| Score brodabilité | Aucun | Aucun | Aucun | ✅ Score 0–100 transparent |
| Mac compatible | ✅ | Embrilliance uniquement ($369+) | ✅ | ✅ |

**Gap de marché confirmé** : aucun outil web frictionless, sans installation, qui livre un PES brodable instantanément pour moins de $10. StitchFlow occupe ce terrain seul.
