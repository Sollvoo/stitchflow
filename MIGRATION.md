# StitchFlow Desktop — Checklist de migration

Ce fichier trace ce qu'il reste à faire pour passer de la base initiale à une app desktop complète et distribuable.

---

## ✅ Fait (base initiale)

- [x] Structure projet Electron + Django créée
- [x] `electron/main.js` — process manager (spawn Django, BrowserWindow, splash screen)
- [x] `electron/preload.js` — bridge Electron minimal
- [x] `src/stitchflow/settings_desktop.py` — overrides desktop (MEDIA_ROOT, DB, no Celery)
- [x] `src/conversions/tasks.py` — décorateurs Celery retirés (fonctions Python pures)
- [x] `src/conversions/views.py` — `.delay()` remplacé par `threading.Thread`
- [x] `src/stitchflow/celery.py` — supprimé
- [x] `src/stitchflow/__init__.py` — import Celery retiré
- [x] `requirements.txt` — Celery/Redis retirés
- [x] `netlify/index.html` — landing page de téléchargement
- [x] Repo GitHub créé (maintenant supprimé — code fusionné dans StitchFlow)
- [x] Monorepo : fusionné dans https://github.com/Sollvoo/stitchflow (juillet 2026)

---

## 🔧 À faire — MVP fonctionnel

### Setup Python
- [x] venv à `.venv/` à la racine StitchFlow — prêt
- [x] `python src/manage.py check --settings=stitchflow.settings_desktop` → 0 erreur
- [x] `python src/manage.py migrate --settings=stitchflow.settings_desktop` → OK

### Setup Electron
- [x] `npm install` depuis la racine StitchFlow → node_modules créé
- [x] `npm start` démarre sans erreur (testé sur Windows)
- [ ] Vérifier sur Mac que Django démarre et l'app charge correctement

### Build Vite
- [ ] Installer les dépendances frontend : `cd src/frontend && npm install`
- [ ] Builder les assets : `cd src/frontend && npm run build`
- [ ] Vérifier que `src/frontend/static/dist/.vite/manifest.json` existe

### Migrations
- [x] Migrations appliquées avec settings_desktop — OK
- [ ] Vérifier que la DB SQLite se crée dans `~/Library/Application Support/StitchFlow/` (Mac)

### Test pipeline complet
- [ ] Uploader un SVG → vérifier la conversion et le téléchargement PES
- [ ] Uploader un PNG → vérifier la vectorisation + éditeur SVG + PES
- [ ] Vérifier que le polling HTMX fonctionne (barre de progression)

---

## 🎨 UX desktop

- [ ] **Dialog de bienvenue** — au premier lancement, vérifier Ink/Stitch installé
  - Si absent : afficher un message avec les instructions d'installation
  - Bouton "Vérifier à nouveau" pour relancer la détection
- [ ] **Icône d'application** personnalisée (`.icns` pour Mac, `.ico` pour Windows)
  - Créer `assets/icon.png` (1024×1024), convertir en `.icns`/`.ico`
- [ ] **Menu bar natif** Mac — Fichier, Édition, Affichage, Aide
- [ ] **Tray icon** optionnel — icône dans la barre de menu Mac
- [ ] **Splash screen** amélioré — avec icône de l'app

---

## 📦 Build & distribution

### Mac ARM64 (priorité)
- [ ] Tester `npm run build:mac-arm` → génère `dist/StitchFlow-arm64.dmg`
- [ ] Vérifier l'installation depuis le .dmg sur Mac Apple Silicon
- [ ] Vérifier que `Clic droit → Ouvrir` contourne le Gatekeeper (pas de signature)
- [ ] *(Optionnel)* Signer le .dmg avec Apple Developer account — élimine le warning Gatekeeper

### Mac Intel
- [ ] Tester `npm run build:mac-intel` → génère `dist/StitchFlow-x64.dmg`
- [ ] Universal binary (ARM64 + Intel) : `npm run build:mac` (plus lourd mais universel)

### Windows
- [ ] Tester `npm run build:win` (depuis Mac via Wine ou GitHub Actions)
- [ ] Configurer GitHub Actions pour build Windows automatique

### GitHub Actions CI (automatisation)
- [ ] Créer `.github/workflows/build.yml`
  - Trigger sur push de tag `v*.*.*`
  - Build Mac ARM64 sur `macos-latest`
  - Build Windows x64 sur `windows-latest`
  - Upload automatique les `.dmg`/`.exe` en Release Assets

---

## 🌐 Distribution Netlify

- [ ] Déployer `netlify/index.html` sur Netlify
  - Aller sur https://app.netlify.com → "New site from Git" → brancher le repo GitHub
  - Build command : vide, Publish directory : `netlify`
  - L'URL sera du type `stitchflow-desktop.netlify.app`
- [ ] Mettre à jour le lien dans `netlify/index.html` avec la vraie URL de release GitHub
- [ ] Tester le téléchargement depuis la page Netlify

---

## 🔌 Ink/Stitch — script d'installation assisté

- [ ] Créer `scripts/install_inkstitch.sh` (macOS) :
  ```bash
  #!/bin/bash
  # Vérifie Homebrew, installe Inkscape, télécharge Ink/Stitch v3.x
  ```
- [ ] Intégrer la vérification dans `electron/main.js` :
  - Au démarrage, vérifier `INKSTITCH_EXECUTABLE`
  - Si introuvable → charger `electron/inkstitch_missing.html` à la place du splash
- [ ] Créer `electron/inkstitch_missing.html` — page avec instructions d'installation
- [ ] Bouton "Relancer la détection" sans redémarrer l'app

---

## 🧹 Nettoyage & maintenance

- [ ] **Nettoyage automatique** des fichiers media anciens (jobs > 30 jours)
  - Ajouter une commande de gestion Django : `python manage.py cleanup_old_jobs`
  - Appeler depuis Electron au démarrage (si dernier nettoyage > 7 jours)
- [ ] **Gestion des erreurs** — améliorer les messages d'erreur dans l'UI Django
- [ ] **Logs** — vérifier que les logs s'écrivent correctement dans userData
- [ ] **Mise à jour** — pas de mécanisme auto prévu pour MVP, à faire manuellement

---

## 🔐 Sécurité & distribution

- [ ] Vérifier que `SECRET_KEY` dans `settings_desktop.py` est suffisamment aléatoire pour la prod
  - Pour une app locale single-user, une clé fixe est acceptable mais non idéale
- [ ] **Apple Gatekeeper** : sans signature → "clic droit → Ouvrir" requis
  - Documenter clairement dans README.md et page Netlify
- [ ] **Antivirus Windows** : l'exe PyInstaller/Electron peut déclencher des faux positifs
  - À documenter dans le README

---

## 📝 Notes techniques

### Pourquoi threading.Thread et non Celery ?
Celery nécessite un broker externe (Redis) = processus supplémentaire à gérer.
En mode desktop single-user, `threading.Thread(daemon=True)` fait exactement la même chose :
- La conversion tourne en arrière-plan
- Le polling HTMX fonctionne (la progression est sauvegardée en SQLite)
- Aucun processus externe requis

### Où sont stockées les données ?
- SQLite : `~/Library/Application Support/StitchFlow/db.sqlite3`
- Media (uploads, résultats) : `~/Library/Application Support/StitchFlow/media/`
- Logs : `~/Library/Application Support/StitchFlow/stitchflow.log`

### Port Django
Electron cherche un port libre depuis 8765. Le port effectif est passé à Django via la commande `runserver 127.0.0.1:PORT`.
