# StitchFlow — Stratégie marketing & lancement (juin 2025)

> Document vivant. À mettre à jour après chaque signal marché (retour beta, premier paiement, premier refus).

---

## 1. Contexte et objectifs

### Situation actuelle

- Phases 1–9 terminées ✅ (pipeline complet + auth + comptes)
- Phase 10 (dashboard/historique) en cours → **prérequis pour la beta**
- Pas encore de lancement, pas de paiement intégré, pas de landing page

### Objectif principal à 12 mois

**Valider le product-market fit** : obtenir au moins 5 utilisatrices régulières (hors fondateur) qui convertissent ≥ 2 designs/mois avec StitchFlow.

Indicateur secondaire concret : **1 paiement réel** (même €3) d'une personne que le fondateur ne connaît pas personnellement.

> Ce n'est pas un objectif de revenus — c'est un objectif de validation. Si 0 artisane paye d'ici 6 mois, il faut comprendre pourquoi avant d'aller plus loin.

---

## 2. La conversation à avoir avant tout le reste

### ⚠️ Risque critique : l'utilisatrice beta ne sait pas encore que c'est un projet commercial

Avant de lancer une landing page, un plan tarifaire ou quoi que ce soit de public, **cette conversation doit avoir lieu** :

**Questions à lui poser :**
1. "Est-ce que tu utiliserais StitchFlow régulièrement si c'était disponible ?"
2. "Est-ce que €3/conversion te semble juste pour remplacer tes conversions simples à €10 ?"
3. "Est-ce que tu connais d'autres brodeuses qui ont le même problème ?"
4. "Qu'est-ce qui te ferait hésiter à l'utiliser ?"

**Ce qu'on veut confirmer :**
- Elle voit la valeur (gain temps + argent sur designs simples)
- Elle accepterait de payer pour ça
- Elle pourrait en parler dans son réseau

**Ce qu'on risque sans cette conversation :**
- Elle découvre le SaaS en production sans avoir été prévenue → perte de confiance
- On construit une stratégie sur une hypothèse non testée

---

## 3. Modèle freemium

### Structure tarifaire recommandée

| Plan | Prix | Quota | Cible |
|------|------|-------|-------|
| **Free** | €0 | 3 conversions/mois | Discovery, test sans engagement |
| **Starter** | €9/mois | 15 conversions/mois | Artisane occasionnelle (2-3×/semaine) |
| **Pro** | €19/mois | 50 conversions/mois | Artisane régulière (business principale) |
| **Pay-as-you-go** | €3/conversion | Sans limite ni abonnement | Usage ponctuel, pic de commandes |

### Pourquoi ces prix

- **€3/conversion** : 3× moins cher que le prestataire actuel (€10), défendable face aux digitiseurs Etsy ($3–5 mais avec délai 1–24h). Voir `docs/differenciateurs.md §4`.
- **€9/mois** : seuil psychologique bas ("moins d'une pizza"), ROI dès 3 conversions vs PAYG
- **€19/mois** : ROI immédiat pour 7+ conversions/mois. Pour l'utilisatrice à €100/mois chez son prestataire → €19 StitchFlow + prestataire pour les designs complexes
- **Pas de plan illimité** : évite les abuseurs et les coûts infra incontrôlés (Celery + Ink/Stitch scale linéairement avec l'usage)

### Mécanisme d'upgrade

Le plan Free pousse naturellement vers l'upgrade par épuisement du quota mensuel. Pas de fonctionnalités dégradées (confusing), pas de watermark (nuit à la réputation) — juste "vous avez utilisé vos 3 conversions ce mois-ci".

### Essai sans inscription (accès IP)

Avant de créer un compte : **2 conversions anonymes** identifiées par IP (rate-limitées par Redis). Objectif : laisser les utilisatrices tester sans friction avant de demander une inscription. À implémenter en Phase 12 avec un cookie de session anonyme + fallback IP.

> ⚠️ L'IP seule est une passoire (VPN, 4G/5G, changement de box). L'utiliser uniquement comme signal "bonne foi", pas comme vrai garde-fou.

---

## 4. Canal d'acquisition

### Phase 0 — Bouche-à-oreille fermé (mois 1–3)

**Canal unique : l'utilisatrice beta actuelle et son réseau.**

1. Valider avec elle (cf. section 2)
2. Elle utilise StitchFlow pour ses commandes réelles
3. Si ça marche, lui demander de mentionner StitchFlow à 2–3 artisanes de son réseau
4. Onboarder ces artisanes manuellement (pas d'inscription publique)

Pourquoi c'est suffisant pour l'instant : on a besoin de 3–5 signaux qualitatifs avant d'investir dans l'acquisition. Les retours terrain d'une utilisatrice qui brode vraiment valent plus que 50 signups d'une landing page.

### Phase 1 — Landing page avec liste d'attente (mois 1, avant l'ouverture)

**Objectif** : capturer les emails d'artisanes intéressées AVANT que l'outil soit ouvert. Crée de l'anticipation et filtre les utilisateurs motivés.

**Contenu minimal de la landing page :**
- Titre : "Convertissez vos designs SVG en broderie PES en 30 secondes — pour €3"
- Sous-titre : "Avant : €10 et 24h d'attente. Après : €3 et 30 secondes."
- Preview animé ou screenshot de l'interface (la preview des fils est le différenciateur visuel)
- Formulaire email simple : "Je veux tester en avant-première"
- Pas de nom de fondateur obligatoire — le produit parle seul

**Stack suggérée** : une page Django existante `/landing/` suffit. Pas besoin d'outil tiers.

### Phase 2 — Communautés passives (mois 3+, si la beta valide)

Une fois que le produit est validé par 3+ utilisatrices, envisager une présence passive (pas d'outreach actif) :

- **Reddit** : r/embroidery (240K membres), r/BERNINA, r/BrotherEmbroidery — poster un "Show HN"-style "I built a web tool that converts SVG to PES for €3 in 30s" avec résultats réels
- **Groupes Facebook broderie FR** : "Broderie machine" (les plus gros groupes francophones) — même approche
- **Etsy forums** : les vendeurs Etsy qui achètent des fichiers PES sont les clients idéaux

> ⚠️ Ces communautés sont très sensibles au spam. Règle : ne poster que si le produit fonctionne vraiment, avec des exemples réels, en répondant aux questions honnêtement (y compris les limites).

### Ce qu'on ne fait PAS (pour l'instant)

| Canal | Raison d'exclusion |
|-------|-------------------|
| Instagram/TikTok | Demande du contenu régulier — coût élevé pour un fondateur discret |
| LinkedIn personal branding | Hors cible (les artisanes ne sont pas sur LinkedIn professionnel) |
| SEO / blog | Délai 6–12 mois minimum avant premier résultat |
| Publicité payante | Trop tôt — on ne sait pas encore quel message convertit |

---

## 5. Messages clés (cf. `docs/differenciateurs.md §5`)

### Message principal

> **"De €10 à €3 : convertissez vos designs simples en broderie en 30 secondes."**

### Message différenciateur produit

> **"Voyez vos fils Brother avant de broder. Toujours."**

Aucun concurrent (humain ou logiciel) ne montre les fils exacts avant la conversion. C'est le différenciateur visuel le plus fort pour une démo ou une landing page.

### Message honnêteté / confiance

> **"Les designs complexes méritent un humain. Les designs simples méritent 30 secondes et €3."**

---

## 6. Séquence de lancement recommandée

```
Semaine 1   Avoir la conversation avec l'utilisatrice beta
            → Confirmer : valeur perçue, prix acceptable, réseau potentiel

Semaine 2   Publier la landing page avec liste d'attente
            → Collecter emails, pas d'inscription compte

Semaine 3-4 Finaliser Phase 10 (historique conversions)
            → Prérequis beta : elle doit retrouver ses fichiers

Mois 2      Ouvrir la beta à l'utilisatrice + 2-3 personnes de son réseau
            → Accès manuel (invitations), pas d'inscription publique

Mois 3      Décision : est-ce que le produit tient la route pour ces 3-5 personnes ?
            → Si oui : implémenter Phase 12 (paiement Stripe)
            → Si non : identifier le problème avant d'aller plus loin

Mois 4-6    Ouvrir l'inscription publique + plan payant
            → Landing page → signup → plan Free → upgrade vers payant
```

---

## 7. Métriques à suivre

| Métrique | Cible à 3 mois | Cible à 6 mois |
|----------|----------------|----------------|
| Utilisatrices actives (≥1 conv./mois) | 3–5 | 10–20 |
| Taux de rétention (mois 2 si mois 1) | — | ≥50% |
| Conversions réalisées | 20–50 | 100+ |
| Premier paiement réel | — | ✅ avant mois 6 |
| Score qualité moyen (pipeline) | ≥75/100 | ≥80/100 |

---

## 8. Faiblesses à assumer publiquement

Ne pas sur-promettre. Sur la landing page et dans les onboardings :

- "StitchFlow fonctionne bien pour les logos, designs géométriques et texte simple. Pas pour les photos réalistes ou les designs > 10 couleurs."
- "Brother uniquement pour l'instant (PES v1)."
- "Résultat automatique — pas un digitiseur professionnel. Score de qualité fourni à chaque conversion."

Cette honnêteté est elle-même un différenciateur (voir `docs/differenciateurs.md §3`).

---

## Références

- `docs/analyse-concurrentielle.md` — données marché avec prix sourcés
- `docs/differenciateurs.md` — arguments, faiblesses, messages marketing
- `docs/VISION.md` — positionnement et modèle économique
- `docs/ROADMAP.md` — phases de développement (Phase 12 = monétisation)
