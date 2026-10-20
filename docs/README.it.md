# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Supporta_%2F_Dona-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **Seleziona la tua lingua / Select your language:**
> [🇬🇧 English](../README.md) · **[🇮🇹 Italiano](README.it.md)** · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**Self-Hosted Release Archiver, Patch Notes Explorer & Bot Telegram 24/7** per progetti **GitHub** e mod di **Nexus Mods**.

Supporta **10 lingue complete** che traducono l'intera interfaccia e include una **Procedura Guidata Interattiva al Primo Avvio (5-Step Setup Wizard)** accessibile in qualsiasi momento dal pulsante **`📖 Guida & Wizard`**.

---

## ✨ Funzionalità Principali

- 🐙 **Archiviazione Completa GitHub**:
  - Scarica automaticamente tutte le release (Stable e Pre-release/Beta), asset binari, codice sorgente (`.zip` / `.tar.gz`), Patch Notes in Markdown (`PATCH_NOTES.md`) e metadati (`release-metadata.json`) con calcolo **SHA256**.
  - **Bypass intelligente Rate-Limit API GitHub**: download diretto dei sorgenti tramite `codeload.github.com` (zero consumo quota API) e fallback automatico sul feed Atom/HTML quando si raggiunge il limite di 60 richieste/ora senza token o per repository che hanno solo branch/commit senza release formali.
- 🎮 **Supporto Nativo Nexus Mods (Anche con Account Gratuito Free)**:
  - Incolla qualsiasi link `https://www.nexusmods.com/<gioco>/mods/<id>`: recupera nome, miniatura, descrizione BBCode convertita in Markdown, storico versioni (`MAIN`, `OPTIONAL`, `OLD_VERSION`) e scarica direttamente gli archivi sul tuo server combinando la `Personal API Key` e il cookie `nexusmods_session`.
- 🧠 **Auto-Tagging & Memoria Categorie**:
  - Incollando un link GitHub o Nexus Mods, il sistema analizza descrizione e topic generando automaticamente **Categoria** (es. `MOD VR`, `Emulatore`, `Giochi`) e **Tag**, con pulsanti rapidi per riutilizzare al volo le categorie già create.
- ⚡ **Modalità "Solo Ultima Release + Future" (`only_latest`) vs "Storico Completo"**:
  - Scegli per ogni repository (sia da Web UI che dal Bot Telegram) se scaricare l'intero storico passato oppure **solo l'ultima versione attuale e le future uscite**.
- ⏸ **Pausa Globale e Pausa per Singola Repository**:
  - Metti in pausa o riprendi la sincronizzazione generale con un clic, oppure metti in pausa solo specifiche repository lasciando attive le altre.
- 🧹 **Elimina Dati & 🗄 Archivi Conservati sul Disco (Senza Repository Attiva)**:
  - **🧹 Elimina Dati**: svuota i file scaricati di una repository per ripartire da zero con nuove opzioni di download.
  - **🗑 Elimina Repository con Scelta Conservazione File**: quando rimuovi una repository dal monitoraggio, puoi scegliere se cancellare i file dal disco o **conservarli**. I file conservati restano esplorabili e scaricabili nella sezione **`🗄 Archivi Conservati sul Disco`** anche senza repository attiva!
- 🤖 **Bot Telegram Personale 24/7 Blindato**:
  - Risponde esclusivamente al tuo **Telegram User ID numerico** (bloccando chiunque altro).
  - Incolla un link GitHub o Nexus Mods direttamente in chat per aggiungerlo al Vault scegliendo categoria e modalità (*Storico* vs *Solo Ultima + Future*).
  - Comandi interattivi `/menu`, `/status`, `/sync`, gestione Pausa Globale/Singola ed eliminazione repository direttamente da Telegram.

---

## 🚀 Installazione Rapida

### Opzione A: Script Automatico Linux / Proxmox LXC (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

Lo script configura l'ambiente Python in `/opt/github-vault`, crea l'archivio in `/srv/github-vault` e attiva i due servizi `systemd`:
- `github-vault.service` (Web UI + API + Motore di sincronizzazione)
- `github-vault-bot.service` (Bot Telegram 24/7)

### Opzione B: Docker & Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 Primo Accesso & Procedura Guidata (Setup Wizard)

1. Apri il browser su **`http://<IP-DEL-SERVER>:8080`**
2. Effettua il primo login con le credenziali predefinite:
   - **Username:** `admin`
   - **Password:** `admin`
3. Al primo accesso si aprirà automaticamente la **Procedura Guidata in 5 Passaggi** (riapribile in ogni momento cliccando su **`📖 Guida & Wizard`** in alto):
   - **Passo 1 — Lingua & Account Admin**: Scegli la lingua tra le 10 disponibili e imposta il tuo username e la tua nuova password amministratore.
   - **Passo 2 — GitHub Personal Access Token**: Guida passo-passo per generare un token `classic` su `github.com/settings/tokens` (porta il limite da 60 a 5.000 richieste/ora).
   - **Passo 3 — Nexus Mods API & Cookie**: Guida passo-passo per copiare la `Personal API Key` e il cookie `nexusmods_session` (tramite `F12` → *Application* → *Cookies*) per abilitare i download diretti automatici.
   - **Passo 4 — Bot Telegram 24/7**: Guida passo-passo per creare il bot con `@BotFather` e ottenere il tuo ID numerico con `@userinfobot`.
   - **Passo 5 — Manuale Comandi & Funzioni**: Riepilogo completo di tutte le funzioni Web e Telegram.

---

## 📁 Struttura del Progetto

```text
release-vault/
├── server.py              # Backend FastAPI, SQLite, Downloader GitHub/Nexus Mods & API
├── telegram_bot.py        # Bot Telegram 24/7 interattivo con controllo accesso User ID
├── README.md              # README principale (Inglese) con selettore 10 lingue
├── docs/                  # README tradotti in tutte le 10 lingue supportate
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
│   └── index.html         # Web UI Single-Page App, Setup Wizard, 10 Lingue, Markdown Viewer
├── install.sh             # Installer automatico per Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Immagine container Docker
├── docker-compose.yml     # Stack Docker Compose pronto all'uso
├── docker-entrypoint.sh   # Entrypoint Docker (avvia Bot Telegram + Server Web)
├── requirements.txt       # Dipendenze Python
└── .env.example           # Variabili d'ambiente opzionali
```

---

## ☕ Supporta il Progetto / Donazioni

Se **Release Vault** ti è utile e vuoi supportarne lo sviluppo:

👉 **[☕ Supporta / Dona su PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
