# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_支持_%2F_捐赠-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **选择您的语言 / Select your language：**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · **[🇨🇳 中文](README.zh.md)** · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**自托管版本归档器、更新日志浏览器与 24/7 Telegram 机器人**，支持 **GitHub** 项目与 **Nexus Mods** 模组。

支持 **10 种完整语言**（全界面完整翻译），并内置 **5 步交互式首次运行设置向导 (Setup Wizard)**，可随时通过顶部 **`📖 指南与向导`** 按钮打开。

---

## ✨ 核心功能

- 🐙 **完整的 GitHub 版本归档**：
  - 自动下载所有发布版本（正式版 Stable 与预发布版 Pre-release/Beta）、二进制文件、源代码包（`.zip` / `.tar.gz`）、Markdown 更新日志（`PATCH_NOTES.md`）以及带有 **SHA256** 校验的元数据（`release-metadata.json`）。
  - **智能绕过 GitHub API 速率限制**：通过 `codeload.github.com` 直接下载源代码（零 API 配额消耗），并在达到未认证 60 次/小时限制或仓库仅有分支/提交而无正式 Release 时自动回退至 Atom/HTML 订阅源。
- 🎮 **原生支持 Nexus Mods（免费账户同样可用）**：
  - 粘贴任意 `https://www.nexusmods.com/<游戏>/mods/<id>` 链接：自动获取模组名称、缩略图、转换为 Markdown 的 BBCode 描述、版本历史（`MAIN`、`OPTIONAL`、`OLD_VERSION`），并结合 `Personal API Key` 与 `nexusmods_session` Cookie 直接将压缩包下载至您的服务器。
- 🧠 **智能自动标签与分类记忆**：
  - 粘贴 GitHub 或 Nexus Mods 链接时，系统会自动分析描述与主题并生成 **分类** 与 **标签**，并提供快捷按钮一键复用已有分类。
- ⚡ **“仅最新版本 + 未来更新” (`only_latest`) vs “完整历史记录”模式**：
  - 可在网页端或 Telegram 机器人中为每个仓库单独选择：归档全部历史版本，或 **仅下载当前最新版本及后续发布的新版本**。
- ⏸ **全局暂停与单仓库独立暂停**：
  - 一键暂停或恢复全局同步，或仅暂停指定仓库而保持其他仓库正常运行。
- 🧹 **清空数据与 🗄 磁盘保留归档（无活跃仓库也可访问）**：
  - **🧹 清空数据**：清空某个仓库已下载的文件，以便使用新的下载选项重新开始。
  - **🗑 删除仓库并自由选择是否保留文件**：从监控列表中移除仓库时，可选择删除磁盘文件或 **保留文件**。保留下来的归档依然可以在 **`🗄 磁盘保留归档`** 区域中随时浏览和下载！
- 🤖 **安全加固的私人 24/7 Telegram 机器人**：
  - 仅响应您本人的数字 **Telegram User ID**（自动拦截任何其他用户）。
  - 在聊天中直接发送 GitHub 或 Nexus Mods 链接即可添加至 Vault，并选择分类和下载模式（*完整历史* vs *仅最新 + 未来*）。
  - 支持 `/menu`、`/status`、`/sync` 交互菜单、全局/单仓库暂停切换以及直接在 Telegram 中删除仓库。

---

## 🚀 快速安装指南

### 方式 A：Linux / Proxmox LXC 自动安装脚本（Debian / Ubuntu）

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

脚本会在 `/opt/github-vault` 配置 Python 虚拟环境，在 `/srv/github-vault` 创建归档目录，并启用两个 `systemd` 服务：
- `github-vault.service`（网页界面 + API + 后台同步引擎）
- `github-vault-bot.service`（24/7 Telegram 机器人）

### 方式 B：Docker 与 Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 首次登录与交互式设置向导 (Setup Wizard)

1. 在浏览器中打开 **`http://<服务器IP>:8080`**
2. 使用默认凭据进行首次登录：
   - **用户名：** `admin`
   - **密码：** `admin`
3. 首次登录时会自动弹出 **5 步交互式设置向导**（也可随时点击顶部 **`📖 指南与向导`** 重新打开）：
   - **第 1 步 — 语言与管理员账户**：在 10 种语言中选择您的偏好语言，并设置自定义管理员用户名和密码。
   - **第 2 步 — GitHub 个人访问令牌 (PAT)**：图文指引在 `github.com/settings/tokens` 生成 `classic` 令牌（将 API 速率限制从 60 次/小时提升至 5,000 次/小时）。
   - **第 3 步 — Nexus Mods API 与 Cookie**：分步指导获取 `Personal API Key` 和 `nexusmods_session` Cookie（按 `F12` → *Application* → *Cookies*），实现全自动直接下载。
   - **第 4 步 — 24/7 Telegram 机器人**：分步指导通过 `@BotFather` 创建机器人并通过 `@userinfobot` 获取您的数字 User ID。
   - **第 5 步 — 命令与功能手册**：网页端与 Telegram 机器人的完整功能说明。

---

## 📁 项目结构

```text
release-vault/
├── server.py              # FastAPI 后端、SQLite 数据库、GitHub/Nexus Mods 下载引擎与 API
├── telegram_bot.py        # 具有 User ID 访问控制的 24/7 交互式 Telegram 机器人
├── README.md              # 包含 10 语言切换栏的主 README 文档
├── docs/                  # 全部 10 种支持语言的完整 README 翻译文档
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
│   └── index.html         # 单页 Web 应用 (SPA)、设置向导、10 语言支持、Markdown 阅读器
├── install.sh             # 适用于 Debian/Ubuntu/Proxmox LXC 的自动安装脚本 (systemd)
├── Dockerfile             # Docker 容器镜像构建文件
├── docker-compose.yml     # 开箱即用的 Docker Compose 编排文件
├── docker-entrypoint.sh   # Docker 启动入口脚本（同时启动 Telegram 机器人与 Web 服务）
├── requirements.txt       # Python 依赖包列表
└── .env.example           # 可选环境变量示例
```

---

## ☕ 支持项目 / 捐赠

如果 **Release Vault** 对您有帮助，欢迎支持本项目的持续开发：

👉 **[☕ 通过 PayPal 支持 / 捐赠 (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
