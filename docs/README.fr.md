# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Soutenir_%2F_Don-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **Sélectionnez votre langue / Select your language :**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · [🇪🇸 Español](README.es.md) · **[🇫🇷 Français](README.fr.md)** · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**Archiveur de Releases Auto-Hébergé, Explorateur de Notes de Patch & Bot Telegram 24/7** pour les projets **GitHub** et les mods **Nexus Mods**.

Prend en charge **10 langues complètes** traduisant toute l'interface et inclut un **Assistant de Configuration Interactif en 5 Étapes (Setup Wizard)** accessible à tout moment via le bouton **`📖 Guide & Assistant`**.

---

## ✨ Fonctionnalités Principales

- 🐙 **Archivage Complet GitHub** :
  - Télécharge automatiquement toutes les versions (Stables et Pré-versions/Bêta), les fichiers binaires, le code source (`.zip` / `.tar.gz`), les notes de version en Markdown (`PATCH_NOTES.md`) et les métadonnées (`release-metadata.json`) avec calcul **SHA256**.
  - **Contournement intelligent de la limite API GitHub** : téléchargement direct du code source via `codeload.github.com` (zéro quota API consommé) et basculement automatique sur le flux Atom/HTML lorsque la limite de 60 requêtes/heure sans jeton est atteinte ou pour les dépôts sans releases formelles.
- 🎮 **Support Natif Nexus Mods (Même avec un Compte Gratuit)** :
  - Collez n'importe quel lien `https://www.nexusmods.com/<jeu>/mods/<id>` : récupère le titre, la miniature, la description BBCode convertie en Markdown, l'historique des versions (`MAIN`, `OPTIONAL`, `OLD_VERSION`) et télécharge directement les archives sur votre serveur grâce à la `Personal API Key` et au cookie `nexusmods_session`.
- 🧠 **Auto-Tagging Intelligent & Mémoire des Catégories** :
  - En collant un lien GitHub ou Nexus Mods, le système analyse la description et les sujets pour suggérer automatiquement une **Catégorie** et des **Tags**, avec des boutons rapides pour réutiliser vos catégories existantes.
- ⚡ **Mode « Dernière Version Uniquement + Futures » (`only_latest`) vs « Historique Complet »** :
  - Choisissez pour chaque dépôt (depuis l'interface Web ou le Bot Telegram) de télécharger tout l'historique ou **uniquement la dernière version actuelle et les futures mises à jour**.
- ⏸ **Pause Globale et Pause par Dépôt Individuel** :
  - Mettez en pause ou reprenez la synchronisation globale en un clic, ou mettez en pause uniquement certains dépôts tout en laissant les autres actifs.
- 🧹 **Effacer les Données & 🗄 Archives Conservées sur le Disque (Sans Dépôt Actif)** :
  - **🧹 Effacer les données** : videz les fichiers téléchargés d'un dépôt pour repartir à zéro avec de nouvelles options.
  - **🗑 Supprimer le dépôt avec choix de conservation des fichiers** : lors de la suppression d'un dépôt de la surveillance active, choisissez de supprimer les fichiers du disque ou de **les conserver**. Les archives conservées restent consultables et téléchargeables dans la section **`🗄 Archives Conservées sur le Disque`** !
- 🤖 **Bot Telegram Personnel 24/7 Sécurisé** :
  - Répond exclusivement à votre **User ID numérique Telegram** (bloquant tout autre utilisateur).
  - Envoyez un lien GitHub ou Nexus Mods directement dans le chat pour l'ajouter au Vault en choisissant la catégorie et le mode de téléchargement.
  - Commandes interactives `/menu`, `/status`, `/sync`, pause globale/individuelle et suppression de dépôts directement depuis Telegram.

---

## 🚀 Installation Rapide

### Option A : Script Automatique Linux / Proxmox LXC (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

Le script configure l'environnement Python dans `/opt/github-vault`, crée le stockage dans `/srv/github-vault` et active les deux services `systemd` :
- `github-vault.service` (Interface Web + API + Moteur de synchronisation)
- `github-vault-bot.service` (Bot Telegram 24/7)

### Option B : Docker & Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 Première Connexion & Assistant de Configuration (Setup Wizard)

1. Ouvrez votre navigateur sur **`http://<IP-DU-SERVEUR>:8080`**
2. Connectez-vous avec les identifiants par défaut :
   - **Utilisateur :** `admin`
   - **Mot de passe :** `admin`
3. Lors de la première connexion, l'**Assistant Interactif en 5 Étapes** s'ouvre automatiquement (et reste accessible à tout moment via **`📖 Guide & Assistant`**) :
   - **Étape 1 — Langue & Compte Admin** : Choisissez votre langue parmi les 10 disponibles et définissez votre nom d'utilisateur et mot de passe administrateur.
   - **Étape 2 — Jeton Personnel GitHub** : Guide pas à pas pour générer un jeton `classic` sur `github.com/settings/tokens` (passe la limite de 60 à 5 000 requêtes/heure).
   - **Étape 3 — API & Cookie Nexus Mods** : Guide pas à pas pour copier votre `Personal API Key` et le cookie `nexusmods_session` (`F12` → *Application* → *Cookies*).
   - **Étape 4 — Bot Telegram 24/7** : Guide pas à pas pour créer votre bot avec `@BotFather` et obtenir votre ID numérique avec `@userinfobot`.
   - **Étape 5 — Manuel des Commandes & Fonctions** : Récapitulatif complet de toutes les fonctionnalités Web et Telegram.

---

## 📁 Structure du Projet

```text
release-vault/
├── server.py              # Backend FastAPI, SQLite, Téléchargeur GitHub/Nexus Mods & API
├── telegram_bot.py        # Bot Telegram 24/7 interactif avec contrôle d'accès par User ID
├── README.md              # README principal avec sélecteur 10 langues
├── docs/                  # Fichiers README traduits dans les 10 langues prises en charge
│   ├── README.it.md
│   ├── README.es.md
│   ├── README.fr.md
│   ├── README.de.md
│   ├── README.pt.md
│   ├── README.ru.md
│   ├── README.zh.md
│   ├── README.ja.md
│   └── README.ko.md
├── static/
│   └── index.html         # Web UI Single-Page App, Setup Wizard, 10 Langues, Lecteur Markdown
├── install.sh             # Installateur automatique pour Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Image conteneur Docker
├── docker-compose.yml     # Stack Docker Compose prête à l'emploi
├── docker-entrypoint.sh   # Entrypoint Docker (démarre le Bot Telegram + Serveur Web)
├── requirements.txt       # Dépendances Python
└── .env.example           # Variables d'environnement optionnelles
```

---

## ☕ Soutenir le Projet / Faire un Don

Si **Release Vault** vous est utile et que vous souhaitez soutenir son développement :

👉 **[☕ Soutenir / Faire un don sur PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
