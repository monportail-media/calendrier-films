# 🎬 Calendrier Films & Séries — Quebec + International

Application web PWA (installable sur iPhone/Android) avec mise à jour automatique hebdomadaire.

---

## Structure du projet

```
calendrier-projet/
├── .github/
│   └── workflows/
│       └── update.yml        ← CRON automatique (chaque lundi 6h)
├── scripts/
│   └── update.py             ← Script de mise à jour des données
├── public/
│   ├── index.html            ← L'application calendrier (PWA)
│   ├── manifest.json         ← Rend l'app installable sur iPhone
│   ├── sw.js                 ← Service Worker (mode hors ligne)
│   ├── data.json             ← Données générées automatiquement
│   └── data-qc.json          ← Données QC à compléter manuellement
└── README.md
```

---

## ⚙️ Setup initial (une seule fois — environ 20 minutes)

### Étape 1 — Créer un compte GitHub
1. Aller sur **https://github.com**
2. Cliquer **Sign up**
3. Choisir un nom d'utilisateur (ex: `monnom`)
4. Confirmer l'email

### Étape 2 — Créer le dépôt
1. Sur GitHub, cliquer le **+** en haut à droite → **New repository**
2. Nom du dépôt : `calendrier-films` (ou ce que tu veux)
3. Cocher **Public**
4. Cocher **Add a README file**
5. Cliquer **Create repository**

### Étape 3 — Uploader les fichiers
1. Dans ton dépôt GitHub, cliquer **Add file** → **Upload files**
2. Glisser-déposer TOUS les fichiers de ce projet
3. Cliquer **Commit changes**

### Étape 4 — Clé API TMDb (gratuite)
1. Aller sur **https://www.themoviedb.org/signup**
2. Créer un compte (juste un email)
3. Aller dans **Paramètres → API → Créer une clé API**
4. Choisir **Developer** → remplir le formulaire (usage personnel)
5. Copier ta **clé API (v3)**

### Étape 5 — Ajouter la clé API dans GitHub Secrets
1. Dans ton dépôt GitHub → **Settings** → **Secrets and variables** → **Actions**
2. Cliquer **New repository secret**
3. Nom : `TMDB_API_KEY`
4. Valeur : colle ta clé API TMDb
5. Cliquer **Add secret**

### Étape 6 — Activer GitHub Pages
1. Dans ton dépôt → **Settings** → **Pages**
2. Source : **Deploy from a branch**
3. Branch : **main** / dossier : **/ (root)** — mais comme nos fichiers sont dans `/public`, choisir **main** et **/public**
4. Cliquer **Save**
5. Attendre 2 minutes → ton adresse sera : `https://tonnom.github.io/calendrier-films`

### Étape 7 — Lancer la première mise à jour
1. Dans ton dépôt → onglet **Actions**
2. Cliquer **Update Calendar Data**
3. Cliquer **Run workflow** → **Run workflow**
4. Attendre ~2 minutes
5. Les données sont maintenant dans `public/data.json`

---

## 📱 Installer l'app sur iPhone

1. Ouvrir Safari sur ton iPhone
2. Aller sur `https://tonnom.github.io/calendrier-films`
3. Appuyer sur le bouton **Partager** (carré avec flèche)
4. Défiler et appuyer **Sur l'écran d'accueil**
5. Appuyer **Ajouter**
6. L'icône apparaît sur ton écran d'accueil comme une vraie app !

---

## 🍁 Ajouter des séries québécoises manuellement

Ouvrir `public/data-qc.json` dans GitHub et ajouter une entrée :

```json
{
  "id": "qc-001",
  "title": "Nom de la série",
  "saison": "Saison 1",
  "date": "2026-09-15",
  "status": "a-venir",
  "type": "serie",
  "platform": "Club Illico",
  "platformUrl": "https://www.illico.com",
  "lang": ["FR"],
  "tags": ["QC"],
  "categories": ["Drame"],
  "cast": ["Acteur 1", "Acteur 2"],
  "desc": "Description de la série.",
  "note": null,
  "trailers": [
    {
      "lang": "VF",
      "label": "Bande-annonce officielle",
      "url": "https://www.youtube.com/watch?v=XXXXXXXXXXX"
    }
  ],
  "poster": null,
  "backdrop": null,
  "isManual": true
}
```

Cliquer **Commit changes** — c'est tout !

---

## 🔄 Mise à jour automatique

Le CRON tourne **chaque lundi à 6h00** automatiquement.
Il récupère depuis :
- **TVmaze** — nouvelles séries canadiennes (sans clé API)
- **TMDb** — films + séries, affiches, descriptions, notes (clé API gratuite)
- **Radio-Canada RSS** — annonces de nouvelles séries QC

Tu n'as rien à faire. Ton calendrier se met à jour tout seul.

---

## 💰 Coût total : 0$

| Service | Coût |
|---------|------|
| GitHub | Gratuit |
| GitHub Pages | Gratuit |
| GitHub Actions | Gratuit (2000 min/mois, on utilise ~8 min) |
| TMDb API | Gratuit |
| TVmaze API | Gratuit |
| Domaine `.github.io` | Gratuit |
