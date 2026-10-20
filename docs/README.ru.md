# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Поддержать-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **Выберите ваш язык / Select your language:**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · **[🇷🇺 Русский](README.ru.md)** · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**Автономный архиватор релизов (Self-Hosted), просмотрщик патчноутов и Telegram-бот 24/7** для репозиториев **GitHub** и модов **Nexus Mods**.

Поддерживает **10 полных языков** (переводится весь интерфейс) и включает **Интерактивный мастер первичной настройки из 5 шагов (Setup Wizard)**, доступный в любой момент по кнопке **`📖 Гид и Мастер`**.

---

## ✨ Основные возможности

- 🐙 **Полное архивирование GitHub**:
  - Автоматически скачивает все релизы (Stable и Pre-release/Beta), бинарные файлы, исходный код (`.zip` / `.tar.gz`), патчноуты в формате Markdown (`PATCH_NOTES.md`) и метаданные (`release-metadata.json`) с проверкой контрольных сумм **SHA256**.
  - **Умный обход лимитов GitHub API**: прямая загрузка исходного кода через `codeload.github.com` (нулевой расход квоты API) и автоматическое переключение на Atom/HTML-ленту при достижении лимита в 60 запросов/час без токена или для репозиториев без официальных релизов.
- 🎮 **Нативная поддержка Nexus Mods (Работает даже с бесплатным аккаунтом)**:
  - Вставьте любую ссылку `https://www.nexusmods.com/<игра>/mods/<id>`: система получит название, обложку, описание BBCode (конвертированное в Markdown), историю версий (`MAIN`, `OPTIONAL`, `OLD_VERSION`) и скачает архивы напрямую на ваш сервер с помощью `Personal API Key` и cookie `nexusmods_session`.
- 🧠 **Умные авто-теги и память категорий**:
  - При вставке ссылки GitHub или Nexus Mods система анализирует описание и темы, автоматически предлагая **Категорию** и **Теги**, а также кнопки быстрого выбора уже существующих категорий.
- ⚡ **Режим «Только последний релиз + будущие» (`only_latest`) или « Полная история»**:
  - Выбирайте для каждого репозитория (в веб-интерфейсе или через Telegram-бота), скачивать ли всю прошлую историю версий или **только текущую последнюю версию и будущие обновления**.
- ⏸ **Глобальная пауза и пауза для отдельного репозитория**:
  - Приостанавливайте и возобновляйте общую синхронизацию в один клик или ставьте на паузу только выбранные репозитории.
- 🧹 **Очистка данных и 🗄 Сохранённые архивы на диске (без активного репозитория)**:
  - **🧹 Очистить данные**: удалите скачанные файлы репозитория, чтобы начать заново с новыми настройками загрузки.
  - **🗑 Удаление репозитория с сохранением файлов**: при удалении репозитория из мониторинга вы можете удалить файлы с диска или **сохранить их**. Сохранённые архивы остаются доступными для просмотра и скачивания в разделе **`🗄 Сохранённые архивы на диске`**!
- 🤖 **Защищённый личный Telegram-бот 24/7**:
  - Отвечает исключительно вашему числовому **Telegram User ID** (блокируя всех остальных).
  - Отправьте ссылку GitHub или Nexus Mods прямо в чат, чтобы добавить её в Vault с выбором категории и режима загрузки.
  - Интерактивные команды `/menu`, `/status`, `/sync`, управление глобальной/индивидуальной паузой и удаление репозиториев прямо из Telegram.

---

## 🚀 Быстрая установка

### Вариант A: Автоматический скрипт Linux / Proxmox LXC (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

Скрипт настраивает окружение Python в `/opt/github-vault`, создаёт хранилище в `/srv/github-vault` и запускает две службы `systemd`:
- `github-vault.service` (Веб-интерфейс + API + Движок синхронизации)
- `github-vault-bot.service` (Telegram-бот 24/7)

### Вариант B: Docker и Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 Первый вход и Мастер настройки (Setup Wizard)

1. Откройте в браузере **`http://<IP-СЕРВЕРА>:8080`**
2. Войдите в систему со стандартными учётными данными:
   - **Логин:** `admin`
   - **Пароль:** `admin`
3. При первом входе автоматически откроется **Пошаговый мастер настройки из 5 шагов** (доступен в любое время по кнопке **`📖 Гид и Мастер`**):
   - **Шаг 1 — Язык и аккаунт администратора**: Выберите один из 10 языков и задайте собственный логин и пароль администратора.
   - **Шаг 2 — Токен GitHub (PAT)**: Пошаговая инструкция по созданию `classic`-токена на `github.com/settings/tokens` (увеличивает лимит с 60 до 5 000 запросов в час).
   - **Шаг 3 — API и Cookie Nexus Mods**: Инструкция по копированию `Personal API Key` и cookie `nexusmods_session` (`F12` → *Application* → *Cookies*).
   - **Шаг 4 — Telegram-бот 24/7**: Инструкция по созданию бота через `@BotFather` и получению числового ID через `@userinfobot`.
   - **Шаг 5 — Руководство по командам и функциям**: Полное описание всех возможностей веб-интерфейса и Telegram-бота.

---

## 📁 Структура проекта

```text
release-vault/
├── server.py              # Бэкенд FastAPI, SQLite, загрузчик GitHub/Nexus Mods и API
├── telegram_bot.py        # Интерактивный Telegram-бот 24/7 с контролем доступа по User ID
├── README.md              # Главный README с переключателем на 10 языков
├── docs/                  # Переведённые файлы README на всех 10 поддерживаемых языках
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
│   └── index.html         # Одностраничный веб-интерфейс (SPA), Мастер настройки, 10 языков, просмотрщик Markdown
├── install.sh             # Автоматический установщик для Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Образ контейнера Docker
├── docker-compose.yml     # Готовый стек Docker Compose
├── docker-entrypoint.sh   # Точка входа Docker (запускает Telegram-бота + Веб-сервер)
├── requirements.txt       # Зависимости Python
└── .env.example           # Дополнительные переменные окружения
```

---

## ☕ Поддержать проект / Донат

Если **Release Vault** оказался вам полезен и вы хотите поддержать разработку проекта:

👉 **[☕ Поддержать / Донат через PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
