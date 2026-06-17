# Différenciateurs StitchFlow — Arguments produit et positionnement (juin 2025)

> Basé sur l'analyse concurrentielle (docs/analyse-concurrentielle.md), VISION.md, et la ROADMAP complète.

---

## 1. Ce que StitchFlow fait que les concurrents ne font pas (ou mal)

### 1.1 Web, zéro installation, zéro formation

**Aucun concurrent direct ne fait ça.**

- Wilcom, Hatch, Embrilliance, SewArt : tous nécessitent une installation desktop
- Ink/Stitch : nécessite Inkscape + extension + compétences vectorielles
- Digitiseurs humains : nécessitent un email, une attente, un allez-retour

StitchFlow s'ouvre dans un navigateur. Upload, paramétrer, télécharger. 30 secondes.

**Pour qui c'est décisif** : les artisanes qui utilisent un Mac (Embrilliance est la seule alternative Desktop Mac, à $369 minimum), les débutantes, les utilisatrices ponctuelles qui ne veulent pas payer $699 pour broder 2 designs/mois.

---

### 1.2 Preview des fils Brother AVANT la conversion

**Aucun concurrent ne fait ça.**

- Tous les logiciels desktop montrent la preview APRÈS avoir configuré et lancé la conversion
- Les digitiseurs humains livrent le fichier sans que l'utilisatrice sache exactement ce qui va sortir
- Ink/Stitch montre une simulation, mais pas les noms de fils ni la palette Brother réelle

StitchFlow montre les fils exacts (avec leur nom Brother, ex : "Rouge cerise 3023") **avant** de lancer Ink/Stitch. L'utilisatrice voit ce que sa machine va broder, peut exclure des couleurs, fusionner des fils proches. C'est la seule interface qui traite l'utilisatrice comme quelqu'un qui connaît sa machine.

**Impact business** : une artisane qui voit ses fils avant de broder revient. Une artisane qui découvre au brodage que les couleurs sont fausses ne revient pas.

---

### 1.3 Score de brodabilité transparent

**Aucun concurrent ne fait ça.**

- Les logiciels desktop exportent le fichier sans dire "ce design va poser des problèmes"
- Les digitiseurs humains peuvent livrer un fichier médiocre sans feedback
- Ink/Stitch n'a pas de système de scoring

StitchFlow affiche un score 0–100 sur 7 critères (fils, points, dimensions, sauts, densité, fidélité couleurs, couverture vectorisation) **et explique chaque critère**. L'utilisatrice comprend pourquoi un design ne conviendra pas, plutôt que de découvrir le problème sur la machine.

**Impact commercial** : honnêteté = confiance. "Ce design est trop complexe, nous vous recommandons un prestataire humain" est une phrase qu'aucun concurrent ne dit et qui fidélise.

---

### 1.4 Pipeline broderie spécialisé (pas une conversion naïve)

SewArt à $75 fait de l'auto-digitizing basique. Ink/Stitch fait de la conversion SVG simple. StitchFlow fait 12+ étapes spécialisées :

1. Suppression intelligente du fond (rembg IA)
2. Détection logo vs photo (variance locale)
3. Vectorisation multi-chemin (VTracer ARM64 + potrace)
4. Réduction couleurs intelligente (FASTOCTREE)
5. Suppression micro-paths (< 0.1mm²)
6. Réordonnancement des paths (nearest-neighbor, réduction sauts)
7. Snap palette Brother (distance CIE Lab)
8. Forçage ≤ 10 couleurs (contrainte machine)
9. Normalisation strokes → fills (texte vectorisé brodable)
10. Suppression fond de page (PDF vectoriels)
11. Score qualité multi-critères
12. Preview PES rendu Pillow

Aucun outil à moins de $699 n'a ce niveau de post-traitement spécialisé pour la broderie.

---

### 1.5 Éditeur SVG broderie léger (Phase 8, opérationnel)

**SewArt** et les logiciels desktop permettent des ajustements, mais nécessitent une formation.

StitchFlow offre un éditeur web léger entre la vectorisation et la conversion :
- Voir le SVG intermédiaire avant Ink/Stitch
- Supprimer ou fusionner des couleurs d'un clic
- Voir les fils Brother correspondants
- Valider et convertir en un clic

Pas besoin de savoir ce qu'est un SVG. L'interface guide.

---

## 2. Arguments commerciaux pour l'utilisatrice beta

### Argument 1 — L'argent sauvé

> "Vous payez €10 par fichier pour des designs simples. StitchFlow coûte €2–3. Sur 10 conversions par mois, vous économisez €70–80/mois."

Avec un CA de ~€2 000/mois, chaque €10 de conversion est visible. StitchFlow réduit ce coût de 70–80% sur les designs simples.

**Ce qu'il faut valider** : combien de conversions/mois fait l'utilisatrice, et quelle proportion sont "simples" vs complexes ?

### Argument 2 — Le délai supprimé

> "Vous attendez 24h pour recevoir un fichier. Avec StitchFlow, vous brodez dans la minute."

Le délai de 24h n'est pas neutre : il bloque les commandes urgentes, impose de planifier, crée une dépendance. StitchFlow supprime ce frein.

### Argument 3 — Vous voyez vos fils avant de broder

> "Pour la première fois, vous savez exactement quels fils charger avant de mettre le tissu dans le cercle."

Sur la Brother PR1050X (10 aiguilles), charger les fils prend du temps. Savoir à l'avance évite les surprises. C'est un argument pratique, pas marketing.

### Argument 4 — Honnêteté sur les limites

> "StitchFlow vous dit immédiatement si votre design est trop complexe pour être automatisé. Vous ne gaspillez pas €3 pour un résultat décevant."

La concurrence (Etsy digitizers offshore) livre le fichier sans avertissement sur la qualité. Le score de brodabilité de StitchFlow est un argument de transparence.

---

## 3. Faiblesses à assumer honnêtement

### 3.1 Qualité inférieure à un humain qualifié sur les designs complexes

**C'est vrai.** Un digitiseur professionnel ($15-20, Wilcom) produit un résultat meilleur sur tout design non-trivial. StitchFlow doit l'assumer et rediriger.

*Comment gérer* : le score de brodabilité + la détection de complexité (Phase 13) doivent dire explicitement "ce design mérite un humain". Ne pas prétendre être meilleur qu'on est.

### 3.2 Brother uniquement pour l'instant

**C'est vrai.** Le snap de palette Brother, les contraintes 10 aiguilles, le PES v1 — tout est calibré pour Brother. Un utilisateur Janome ou Bernina ne trouvera pas son format.

*Comment gérer* : l'assumer dès l'onboarding, ne pas promettre ce qui n'existe pas encore. Phase 13 prévoit le multi-format.

### 3.3 Pas de compte/historique encore (Phase 9 non faite)

**C'est vrai.** Chaque session est indépendante. Impossible de retrouver un ancien fichier converti.

*Comment gérer* : accepté pour la beta. À corriger avant ouverture commerciale (Phase 9).

### 3.4 Pas encore de paiement intégré (Phase 12 non faite)

**C'est vrai.** La beta sera probablement gratuite ou sur invitation. Le SaaS arrive en Phase 12.

### 3.5 Qualité variable selon la complexité du source

L'auto-digitizing ne peut pas tout. Un PNG floue, un logo avec dégradés, une photo réaliste — les résultats seront décevants. Le score qualité atténue cela, mais ne le résout pas.

---

## 4. Positionnement prix optimal (basé sur le marché réel)

### Données du marché

| Référentiel | Prix |
|-------------|------|
| Etsy digitizers offshore (simple) | $3–5 |
| Etsy digitizers (intermédiaire) | $5–15 |
| SewArt (logiciel) | $75 une fois |
| Digitiseurs pro US | $15–20+ |
| Prestataire actuel de l'utilisatrice | €10 |
| Embrilliance SA L2 (logiciel Mac) | $369 une fois |
| Hatch Composer (logiciel) | $699 une fois |

### Recommandation : €3 par conversion (ou plan mensuel)

**Pourquoi €3 et pas €2 ou €5 ?**

- **€2** : trop proche du "gratuit" symboliquement, risque de signaler mauvaise qualité. Marge très faible.
- **€3** : point de prix psychologique fort ("3 fois moins cher qu'un humain"), rentable dès 50 conversions/mois pour couvrir infra + marge.
- **€5** : défendable si différenciation très forte (preview fils, score, éditeur SVG), mais risque de se battre avec les digitiseurs à $5 sur Etsy (qui ont l'avantage "humain").

**Plan suggéré pour la beta :**
- **Pay-as-you-go** : €3 / conversion (pas d'engagement, validé rapidement)
- **Abonnement mensuel** : €19/mois illimité (pour les artisanes qui font 10+ conversions/mois — ROI immédiat vs €10/design)
- **Essai** : 3 conversions gratuites (pour valider le produit sans risque)

**Argument pour l'abonnement** : l'utilisatrice beta à €2 000/mois de CA et 10 conversions/mois passe de €100 (prestataire) à €19 (StitchFlow) pour les designs simples. Elle garde le prestataire pour les designs complexes.

---

## 5. Les 3 messages marketing les plus percutants

### Message 1 — L'économie concrète

> **"De €10 à €3 : convertissez vos designs simples en broderie en 30 secondes."**

Accroche directe pour l'artisane qui connaît le prix du marché. Pas de jargon.

---

### Message 2 — La transparence des fils

> **"Voyez vos fils avant de broder. Toujours."**

Différenciateur absolu. Aucun concurrent ne peut répliquer ça sans refonte produit. S'adresse à la douleur pratique (temps de chargement des fils, surprises au brodage).

---

### Message 3 — Le bon outil pour le bon usage

> **"Les designs complexes méritent un humain. Les designs simples méritent 30 secondes et €3."**

Ce message assume les limites et les retourne en force. Il positionne StitchFlow comme honnête et précis dans sa promesse, pas comme un concurrent à tout faire. Il rassure l'artisane : elle ne va pas "trahir" son prestataire — elle optimise son budget.

---

## 6. Matrice de positionnement

```
                    PRIX ÉLEVÉ
                         │
              Wilcom E4  │  ProDigitizing ($20)
              $4 000     │  Fiverr pro
              Hatch      │
              $700-1200  │
                         │
TECHNIQUE ───────────────┼─────────────────── ACCESSIBLE
DIFFICILE                │               FACILEMENT
                         │
              Ink/Stitch │  ★ StitchFlow cible
              gratuit    │  €3 / conversion
              mais       │  web, instantané
              complexe   │
              SewArt     │  Etsy offshore
              $75        │  $3-5 mais délai
                         │
                    PRIX BAS
```

**StitchFlow cible le quadrant "accessible + prix bas"**, là où aucun outil de qualité n'existe actuellement.

---

## 7. Prochaines validations prioritaires

Ces hypothèses sont raisonnables mais non prouvées. À valider avec l'utilisatrice beta :

1. **Volume de conversions/mois** : combien de designs "simples" facture-t-elle à son prestataire ?
2. **Définition de "simple"** : est-ce que sa définition correspond aux cas où StitchFlow performe bien (logos vectoriels, geometrique, texte) ?
3. **Seuil qualité acceptable** : un score 75/100 suffit-il pour qu'elle utilise le fichier sans révisions ?
4. **Willingness to pay €3** : est-ce que €3 est le bon prix ou est-ce qu'elle préférerait €5 pour "ne pas que ça paraisse cheap" ?
5. **Usage du score qualité** : comprend-elle intuitivement les 7 critères ou faut-il simplifier ?
