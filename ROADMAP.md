# StitchFlow — Roadmap

## Phase 1 — MVP SVG → PES ✅ (en cours)

Objectif : permettre à un utilisateur d'uploader un SVG et de télécharger un fichier PES.

- [x] Projet Django initialisé
- [x] App `frontend` (Vite, Tailwind, DaisyUI, HTMX, Alpine)
- [x] App `conversions` (modèle, formulaire, vues, services)
- [x] Modèle `ConversionJob` (UUID, statuts, FileField)
- [x] Upload SVG avec validation
- [x] Tâche Celery asynchrone
- [x] Service `inkstitch.py` (intégration CLI)
- [x] Page de statut avec polling HTMX
- [x] Téléchargement du fichier PES
- [ ] Tests unitaires (services et formulaires)
- [ ] Validation SVG approfondie (détecter SVG vide, sans chemins brodables)
- [ ] Prévisualisation basique du SVG uploadé

---

## Phase 2 — Amélioration de la conversion SVG

Objectif : donner plus de contrôle sur la conversion et améliorer le feedback.

- [ ] Détection et affichage des couleurs présentes dans le SVG
- [ ] Choix de la taille de broderie (en cm ou mm)
- [ ] Choix du nombre maximum de couleurs de fil
- [ ] Estimation du nombre de points avant conversion
- [ ] Affichage du temps de broderie estimé
- [ ] Prévisualisation du plan de broderie (stitch plan SVG via Ink/Stitch)
- [ ] Messages d'erreur compréhensibles pour les cas fréquents (SVG trop complexe, chemins non fermés, etc.)
- [ ] Amélioration de la validation SVG côté serveur

---

## Phase 3 — PNG → SVG

Objectif : accepter des images PNG et les vectoriser automatiquement en SVG.

- [ ] Upload PNG
- [ ] Nettoyage de l'image (contraste, bruit)
- [ ] Suppression du fond (rembg ou autre)
- [ ] Réduction du nombre de couleurs (quantization)
- [ ] Vectorisation PNG → SVG (Potrace, VTracer, ou autre)
- [ ] Validation du SVG généré (qualité suffisante pour broderie)
- [ ] Aperçu comparatif PNG source / SVG généré

---

## Phase 4 — Assistant intelligent

Objectif : analyser automatiquement les designs et suggérer des améliorations.

- [ ] Analyse automatique du design
- [ ] Détection des détails trop petits pour la broderie (< 2 mm typiquement)
- [ ] Détection du texte trop petit
- [ ] Score de qualité broderie (0–100)
- [ ] Suggestions automatiques d'amélioration
- [ ] Détection des zones susceptibles de causer des problèmes (densité trop haute, chevauchements)

---

## Phase 5 — Interface de corrections humaines

Objectif : permettre à l'utilisateur de modifier le design directement dans le navigateur.

- [ ] Éditeur visuel (SVG interactif dans le navigateur)
- [ ] Supprimer des zones / couleurs
- [ ] Changer les couleurs de fil
- [ ] Changer l'ordre de broderie
- [ ] Modifier le type de point (satin, remplissage, courant…)
- [ ] Modifier la densité
- [ ] Prévisualisation animée avant export (simulation de broderie)
- [ ] Historique des modifications (undo/redo)

---

## Phase 6 — Produit complet

Objectif : passer d'un outil à une plateforme.

- [ ] Comptes utilisateurs (inscription, connexion, profil)
- [ ] Historique des conversions par utilisateur
- [ ] Migration vers PostgreSQL
- [ ] Stockage cloud (S3 ou compatible) pour les fichiers media
- [ ] Quotas de conversion par compte
- [ ] Bibliothèque de designs (catalogue partagé)
- [ ] Paiements éventuels (Stripe)
- [ ] API REST pour intégrations tierces
- [ ] Docker / Docker Compose pour déploiement simplifié
- [ ] CI/CD (GitHub Actions)
