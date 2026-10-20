# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Apoyar_%2F_Donar-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **Selecciona tu idioma / Select your language:**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · **[🇪🇸 Español](README.es.md)** · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**Archivador Autoalojado de Releases, Explorador de Notas de Parche y Bot de Telegram 24/7** para proyectos de **GitHub** y mods de **Nexus Mods**.

Soporta **10 idiomas completos** que traducen toda la interfaz e incluye un **Asistente Interactivo de Configuración Inicial en 5 Pasos (Setup Wizard)** accesible en cualquier momento desde el botón **`📖 Guía y Asistente`**.

---

## ✨ Características Principales

- 🐙 **Archivado Completo de GitHub**:
  - Descarga automáticamente todas las versiones (Estables y Pre-releases/Beta), binarios, código fuente (`.zip` / `.tar.gz`), notas de parche en Markdown (`PATCH_NOTES.md`) y metadatos (`release-metadata.json`) con verificación **SHA256**.
  - **Bypass inteligente del límite de API de GitHub**: descarga directa del código fuente mediante `codeload.github.com` (cero consumo de cuota API) y respaldo automático mediante feed Atom/HTML cuando se alcanza el límite de 60 peticiones/hora sin token o en repositorios sin releases formales.
- 🎮 **Soporte Nativo para Nexus Mods (Incluso con Cuenta Gratuita)**:
  - Pega cualquier enlace `https://www.nexusmods.com/<juego>/mods/<id>`: obtiene título, miniatura, descripción BBCode convertida a Markdown, historial de versiones (`MAIN`, `OPTIONAL`, `OLD_VERSION`) y descarga directamente los archivos en tu servidor combinando la `Personal API Key` y la cookie `nexusmods_session`.
- 🧠 **Auto-Etiquetado Inteligente y Memoria de Categorías**:
  - Al pegar un enlace de GitHub o Nexus Mods, el sistema analiza la descripción y los temas para generar automáticamente la **Categoría** y las **Etiquetas (Tags)**, con botones rápidos para reutilizar categorías existentes.
- ⚡ **Modo "Solo Última Versión + Futuras" (`only_latest`) vs "Historial Completo"**:
  - Elige por cada repositorio (tanto en la Web como en el Bot de Telegram) si deseas descargar todo el historial pasado o **solo la última versión actual y las actualizaciones futuras**.
- ⏸ **Pausa Global y Pausa por Repositorio Individual**:
  - Pausa o reanuda la sincronización global con un clic, o pausa únicamente repositorios específicos manteniendo activos los demás.
- 🧹 **Borrar Datos y 🗄 Archivos Conservados en Disco (Sin Repositorio Activo)**:
  - **🧹 Borrar Datos**: limpia los archivos descargados de un repositorio para empezar de cero con nuevas opciones de descarga.
  - **🗑 Eliminar Repositorio con Opción de Conservar Archivos**: al eliminar un repositorio del monitoreo activo, puedes elegir si borrar los archivos del disco o **conservarlos**. ¡Los archivos conservados siguen disponibles para explorar y descargar en la sección **`🗄 Archivos Conservados en Disco`**!
- 🤖 **Bot de Telegram Personal 24/7 Blindado**:
  - Responde exclusivamente a tu **User ID numérico de Telegram** (bloqueando a cualquier otro usuario).
  - Envía cualquier enlace de GitHub o Nexus Mods directamente al chat para añadirlo al Vault eligiendo categoría y modo de descarga.
  - Comandos interactivos `/menu`, `/status`, `/sync`, pausa global/individual y eliminación de repositorios desde Telegram.

---

## 🚀 Instalación Rápida

### Opción A: Script Automático Linux / Proxmox LXC (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

El script configura el entorno Python en `/opt/github-vault`, crea el archivo en `/srv/github-vault` y activa los dos servicios `systemd`:
- `github-vault.service` (Interfaz Web + API + Motor de sincronización)
- `github-vault-bot.service` (Bot de Telegram 24/7)

### Opción B: Docker y Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 Primer Acceso y Asistente de Configuración (Setup Wizard)

1. Abre tu navegador en **`http://<IP-DEL-SERVIDOR>:8080`**
2. Inicia sesión por primera vez con las credenciales predeterminadas:
   - **Usuario:** `admin`
   - **Contraseña:** `admin`
3. En el primer acceso se abrirá automáticamente el **Asistente Guiado en 5 Pasos** (disponible en cualquier momento desde **`📖 Guía y Asistente`**):
   - **Paso 1 — Idioma y Cuenta Admin**: Elige entre los 10 idiomas y configura tu propio usuario y contraseña de administrador.
   - **Paso 2 — GitHub Personal Access Token**: Guía paso a paso para generar un token `classic` en `github.com/settings/tokens` (aumenta el límite de 60 a 5.000 peticiones/hora).
   - **Paso 3 — API y Cookie de Nexus Mods**: Guía paso a paso para copiar tu `Personal API Key` y la cookie `nexusmods_session` (`F12` → *Application* → *Cookies*).
   - **Paso 4 — Bot de Telegram 24/7**: Guía paso a paso para crear tu bot con `@BotFather` y obtener tu ID numérico con `@userinfobot`.
   - **Paso 5 — Manual de Comandos y Funciones**: Resumen completo de todas las funciones Web y de Telegram.

---

## 📁 Estructura del Proyecto

```text
release-vault/
├── server.py              # Backend FastAPI, SQLite, Descargador GitHub/Nexus Mods y API
├── telegram_bot.py        # Bot de Telegram 24/7 interactivo con control de acceso por User ID
├── README.md              # README principal con selector de 10 idiomas
├── docs/                  # Archivos README traducidos en los 10 idiomas soportados
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
│   └── index.html         # Web UI Single-Page App, Setup Wizard, 10 Idiomas, Visor Markdown
├── install.sh             # Instalador automático para Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Imagen de contenedor Docker
├── docker-compose.yml     # Stack Docker Compose listo para usar
├── docker-entrypoint.sh   # Entrypoint Docker (inicia Bot de Telegram + Servidor Web)
├── requirements.txt       # Dependencias de Python
└── .env.example           # Variables de entorno opcionales
```

---

## 👥 Colaboradores y Créditos

- 👑 **[VenomDrake](https://github.com/VenomDrake)** — Creador, Mantenedor Principal, Desarrollador Principal, Arquitectura e Ingeniería
- 🤖 **[Antigravity (Google DeepMind)](https://deepmind.google)** — Co-Desarrollador IA, Arquitectura e Ingeniería
---

## ☕ Apoya el Proyecto / Donar

Si **Release Vault** te resulta útil y quieres apoyar su desarrollo:

👉 **[☕ Apoyar / Donar en PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
