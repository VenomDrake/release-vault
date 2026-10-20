# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Unterstützen_%2F_Spenden-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **Wähle deine Sprache / Select your language:**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · **[🇩🇪 Deutsch](README.de.md)** · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**Selbstgehostetes Release-Archiv, Patch-Notes-Explorer & 24/7 Telegram-Bot** für **GitHub**-Projekte und **Nexus Mods**.

Unterstützt **10 vollständige Sprachen**, die die gesamte Benutzeroberfläche übersetzen, und enthält einen **Interaktiven 5-Schritte-Einrichtungsassistenten (Setup Wizard)**, der jederzeit über **`📖 Anleitung & Assistent`** aufgerufen werden kann.

---

## ✨ Hauptfunktionen

- 🐙 **Vollständige GitHub-Archivierung**:
  - Lädt automatisch alle Releases (Stable und Pre-Release/Beta), Binärdateien, Quellcode (`.zip` / `.tar.gz`), Markdown-Patchnotes (`PATCH_NOTES.md`) und Metadaten (`release-metadata.json`) inklusive **SHA256**-Prüfsumme herunter.
  - **Intelligenter GitHub-API-Rate-Limit-Bypass**: Direkter Quellcode-Download über `codeload.github.com` (null API-Quota-Verbrauch) und automatischer Atom/HTML-Feed-Fallback bei Erreichen des Limits von 60 Anfragen/Stunde ohne Token oder bei Repositories ohne formelle Releases.
- 🎮 **Native Nexus Mods Unterstützung (Auch mit kostenlosem Free-Account)**:
  - Füge einen beliebigen Link `https://www.nexusmods.com/<spiel>/mods/<id>` ein: Ruft Titel, Vorschaubild, in Markdown konvertierte BBCode-Beschreibung sowie den Versionsverlauf (`MAIN`, `OPTIONAL`, `OLD_VERSION`) ab und lädt Archive über den `Personal API Key` und das `nexusmods_session`-Cookie direkt auf deinen Server herunter.
- 🧠 **Intelligentes Auto-Tagging & Kategorienspeicher**:
  - Beim Einfügen eines GitHub- oder Nexus-Mods-Links analysiert das System Beschreibung und Themen, um automatisch **Kategorie** und **Tags** vorzuschlagen – inklusive Schnellauswahl-Buttons für bereits vorhandene Kategorien.
- ⚡ **Modus „Nur neueste Version + Zukünftige“ (`only_latest`) vs. „Kompletter Verlauf“**:
  - Wähle pro Repository (sowohl in der Web-UI als auch im Telegram-Bot), ob der gesamte bisherige Verlauf oder **nur die aktuell neueste Version sowie zukünftige Updates** heruntergeladen werden sollen.
- ⏸ **Globale Pause & Pause pro einzelnem Repository**:
  - Pausiere oder starte die globale Synchronisierung mit einem Klick, oder pausiere gezielt einzelne Repositories, während alle anderen weiterlaufen.
- 🧹 **Daten löschen & 🗄 Auf Festplatte behaltene Archive (Ohne aktives Repository)**:
  - **🧹 Daten löschen**: Leere die heruntergeladenen Dateien eines Repositorys, um mit neuen Download-Optionen sauber neu zu starten.
  - **🗑 Repository löschen mit Dateierhalt-Option**: Beim Entfernen eines Repositorys aus der Überwachung kannst du wählen, ob die Dateien von der Festplatte gelöscht oder **behalten** werden sollen. Behaltene Archive bleiben im Bereich **`🗄 Auf Festplatte behaltene Archive`** jederzeit durchsuchbar und herunterladbar!
- 🤖 **Abgesicherter persönlicher 24/7 Telegram-Bot**:
  - Reagiert ausschließlich auf deine numerische **Telegram User ID** (blockiert alle anderen Nutzer).
  - Sende einfach einen GitHub- oder Nexus-Mods-Link in den Chat, um ihn inklusive Kategorie- und Modusauswahl zum Vault hinzuzufügen.
  - Interaktive Befehle `/menu`, `/status`, `/sync`, Globale/Einzelne Pause und Repository-Löschung direkt über Telegram.

---

## 🚀 Schnellinstallation

### Option A: Automatisches Linux / Proxmox LXC Skript (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

Das Skript richtet die Python-Umgebung in `/opt/github-vault` ein, erstellt das Archivverzeichnis in `/srv/github-vault` und aktiviert zwei `systemd`-Dienste:
- `github-vault.service` (Web-UI + API + Synchronisierungs-Engine)
- `github-vault-bot.service` (24/7 Telegram-Bot)

### Option B: Docker & Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 Erster Login & Einrichtungsassistent (Setup Wizard)

1. Öffne deinen Browser unter **`http://<SERVER-IP>:8080`**
2. Melde dich beim ersten Start mit den Standard-Zugangsdaten an:
   - **Benutzername:** `admin`
   - **Passwort:** `admin`
3. Beim ersten Login öffnet sich automatisch der **5-Schritte-Einrichtungsassistent** (jederzeit wieder aufrufbar über **`📖 Anleitung & Assistent`**):
   - **Schritt 1 — Sprache & Admin-Konto**: Wähle deine Sprache aus 10 Optionen und lege deinen eigenen Admin-Benutzernamen und dein Passwort fest.
   - **Schritt 2 — GitHub Personal Access Token**: Schritt-für-Schritt-Anleitung zum Erstellen eines `classic`-Tokens auf `github.com/settings/tokens` (erhöht das Limit von 60 auf 5.000 Anfragen/Stunde).
   - **Schritt 3 — Nexus Mods API & Cookie**: Schritt-für-Schritt-Anleitung zum Kopieren von `Personal API Key` und `nexusmods_session`-Cookie (`F12` → *Application* → *Cookies*).
   - **Schritt 4 — 24/7 Telegram-Bot**: Schritt-für-Schritt-Anleitung zum Erstellen deines Bots über `@BotFather` und Abrufen deiner numerischen ID über `@userinfobot`.
   - **Schritt 5 — Befehls- & Funktionshandbuch**: Vollständige Übersicht aller Web- und Telegram-Funktionen.

---

## 📁 Projektstruktur

```text
release-vault/
├── server.py              # FastAPI Backend, SQLite, GitHub/Nexus Mods Downloader & API
├── telegram_bot.py        # Interaktiver 24/7 Telegram-Bot mit User-ID-Zugriffskontrolle
├── README.md              # Haupt-README mit 10-Sprachen-Auswahl
├── docs/                  # Übersetzte README-Dateien in allen 10 unterstützten Sprachen
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
│   └── index.html         # Single-Page Web-UI, Setup Wizard, 10 Sprachen, Markdown-Viewer
├── install.sh             # Automatischer Installer für Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Docker-Container-Image
├── docker-compose.yml     # Einsatzbereiter Docker Compose Stack
├── docker-entrypoint.sh   # Docker-Entrypoint (startet Telegram-Bot + Webserver)
├── requirements.txt       # Python-Abhängigkeiten
└── .env.example           # Optionale Umgebungsvariablen
```

---

## 👥 Mitwirkende & Credits

- 👑 **[VenomDrake](https://github.com/VenomDrake)** — Schöpfer, Haupt-Maintainer, Lead Developer, Architektur & Full-Stack-Engineering
- 🤖 **[Antigravity (Google DeepMind)](https://deepmind.google)** — KI-Co-Entwickler, Architektur & Full-Stack-Engineering
---

## ☕ Projekt unterstützen / Spenden

Wenn dir **Release Vault** gefällt und du die Weiterentwicklung unterstützen möchtest:

👉 **[☕ Unterstützen / Spenden über PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
