# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Support_%2F_Donate-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](LICENSE)

> 🌐 **Select your language / Seleziona la tua lingua:**
> **[🇬🇧 English](README.md)** · [🇮🇹 Italiano](docs/README.it.md) · [🇪🇸 Español](docs/README.es.md) · [🇫🇷 Français](docs/README.fr.md) · [🇩🇪 Deutsch](docs/README.de.md) · [🇧🇷 Português](docs/README.pt.md) · [🇷🇺 Русский](docs/README.ru.md) · [🇨🇳 中文](docs/README.zh.md) · [🇯🇵 日本語](docs/README.ja.md) · [🇰🇷 한국어](docs/README.ko.md)

**Self-Hosted Release Archiver, Patch Notes Explorer & 24/7 Telegram Bot** for **GitHub** repositories and **Nexus Mods** projects.

Supports **10 full languages** translating the entire UI and includes an **Interactive 5-Step First-Run Setup Wizard** accessible at any time via the **`📖 Guide & Wizard`** button.

---

## ✨ Key Features

- 🐙 **Complete GitHub Archiving**:
  - Automatically downloads all releases (Stable and Pre-release/Beta), binary assets, source code (`.zip` / `.tar.gz`), Markdown Patch Notes (`PATCH_NOTES.md`), and metadata (`release-metadata.json`) with **SHA256** checksum verification.
  - **Smart GitHub API Rate-Limit Bypass**: direct source archive downloads via `codeload.github.com` (zero API quota usage) and automatic Atom/HTML feed fallback when hitting the 60 req/hr unauthenticated limit or for repositories that only have branches/commits without formal releases.
- 🎮 **Native Nexus Mods Support (Works with Free Accounts too)**:
  - Paste any `https://www.nexusmods.com/<game>/mods/<id>` URL: automatically fetches mod title, thumbnail, BBCode description converted to Markdown, version history (`MAIN`, `OPTIONAL`, `OLD_VERSION`), and downloads archives directly to your server using your `Personal API Key` and `nexusmods_session` cookie.
- 🧠 **Smart Auto-Tagging & Category Memory**:
  - When pasting a GitHub or Nexus Mods link, the system inspects descriptions and topics to automatically suggest a **Category** (e.g. `VR Mod`, `Emulator`, `Games`) and **Tags**, with quick-select pills to reuse your existing categories.
- ⚡ **"Latest Release Only + Future" (`only_latest`) vs "Full History" Mode**:
  - Choose per repository (both in the Web UI and Telegram Bot) whether to archive all past releases or **only the current latest release plus future updates**.
- ⏸ **Global Pause & Per-Repository Pause**:
  - Pause or resume global synchronization with one click, or pause individual repositories while keeping others active.
- 🧹 **Wipe Data & 🗄 Preserved Disk Archives (Detached Repositories)**:
  - **🧹 Wipe Data**: delete downloaded files of a repository to start fresh with new download options.
  - **🗑 Delete Repository with File Preservation Choice**: when removing a repository from active monitoring, choose whether to delete files from disk or **preserve them**. Preserved archives remain browsable and downloadable in the **`🗄 Preserved Disk Archives`** section even without an active repository!
- 🤖 **Hardened Personal 24/7 Telegram Bot**:
  - Responds exclusively to your numeric **Telegram User ID** (blocking everyone else).
  - Send any GitHub or Nexus Mods URL directly in chat to add it to the Vault, choosing category and download mode (*Full History* vs *Latest + Future*).
  - Interactive `/menu`, `/status`, `/sync`, Global/Single Pause toggles, and repository deletion right from Telegram.

---

## 🚀 Quick Start Installation

### Option A: Automated Linux / Proxmox LXC Script (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

The installer configures the Python virtual environment in `/opt/github-vault`, creates the storage directory in `/srv/github-vault`, and enables two `systemd` services:
- `github-vault.service` (Web UI + API + Background Sync Engine)
- `github-vault-bot.service` (24/7 Telegram Bot)

### Option B: Docker & Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 First Login & Interactive Setup Wizard

1. Open your browser at **`http://<SERVER-IP>:8080`**
2. Log in for the first time using the default credentials:
   - **Username:** `admin`
   - **Password:** `admin`
3. On first login, the **5-Step Interactive Setup Wizard** opens automatically (and can be reopened anytime via the **`📖 Guide & Wizard`** button in the header):
   - **Step 1 — Language & Admin Account**: Pick your preferred language out of 10 and set your custom admin username and password.
   - **Step 2 — GitHub Personal Access Token**: Step-by-step guide to generate a `classic` token on `github.com/settings/tokens` (increases API limit from 60 to 5,000 requests/hour).
   - **Step 3 — Nexus Mods API & Cookie**: Step-by-step guide to grab your `Personal API Key` and `nexusmods_session` cookie (`F12` → *Application* → *Cookies*) for automated direct downloads.
   - **Step 4 — 24/7 Telegram Bot**: Step-by-step guide to create your bot via `@BotFather` and get your numeric User ID via `@userinfobot`.
   - **Step 5 — Commands & Features Manual**: Complete overview of all Web UI and Telegram commands.

---

## 📁 Project Structure

```text
release-vault/
├── server.py              # FastAPI Backend, SQLite, GitHub/Nexus Mods Downloader & API
├── telegram_bot.py        # Interactive 24/7 Telegram Bot with User ID access control
├── README.md              # Main README (English) with 10-language selector
├── docs/                  # Translated README files in all 10 supported languages
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
│   └── index.html         # Single-Page Web UI, Setup Wizard, 10 Languages, Markdown Viewer
├── install.sh             # Automated installer for Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Docker container image
├── docker-compose.yml     # Ready-to-use Docker Compose stack
├── docker-entrypoint.sh   # Docker entrypoint (starts Telegram Bot + Web Server)
├── requirements.txt       # Python dependencies
└── .env.example           # Optional environment variables
```

---

## 👥 Contributors & Credits

- 👑 **[VenomDrake](https://github.com/VenomDrake)** — Creator, Lead Maintainer & Project Owner
- 🤖 **[Antigravity (Google DeepMind)](https://deepmind.google)** — AI Co-Developer, Architecture & Engineering

---

## ☕ Support the Project / Donate

If you find **Release Vault** useful and want to support its development:

👉 **[☕ Support / Donate via PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
