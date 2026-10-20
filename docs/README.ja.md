# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_サポート_%2F_寄付-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **言語を選択してください / Select your language:**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · **[🇯🇵 日本語](README.ja.md)** · [🇰🇷 한국어](README.ko.md)

**GitHub** リポジトリおよび **Nexus Mods** 用の **セルフホスト型リリースアーカイバ、パッチノートエクスプローラー＆24時間稼働 Telegram ボット**。

UI全体を翻訳する **全10言語** に対応し、ヘッダーの **`📖 ガイド＆ウィザード`** ボタンからいつでも開ける **対話型5ステップ初期セットアップウィザード (Setup Wizard)** を搭載しています。

---

## ✨ 主な機能

- 🐙 **完全な GitHub アーカイブ機能**:
  - すべてのリリース（安定版 Stable および Pre-release/Beta）、バイナリアセット、ソースコード（`.zip` / `.tar.gz`）、Markdown パッチノート（`PATCH_NOTES.md`）、および **SHA256** ハッシュ付きメタデータ（`release-metadata.json`）を自動ダウンロードします。
  - **スマートな GitHub API レート制限バイパス**: `codeload.github.com` 経由でソースコードを直接ダウンロード（API クォータ消費ゼロ）し、トークンなしでの60回/時の制限到達時や正式なリリースがないリポジトリでは自動的に Atom/HTML フィードへフォールバックします。
- 🎮 **Nexus Mods ネイティブ対応（無料アカウントでも利用可能）**:
  - `https://www.nexusmods.com/<ゲーム名>/mods/<ID>` のリンクを貼り付けるだけで、Mod名、サムネイル、Markdown変換されたBBCode説明文、バージョン履歴（`MAIN`、`OPTIONAL`、`OLD_VERSION`）を取得し、`Personal API Key` と `nexusmods_session` Cookie を組み合わせてサーバーへ直接アーカイブをダウンロードします。
- 🧠 **自動タグ付け＆カテゴリ記憶**:
  - GitHub や Nexus Mods のリンクを貼り付けると、説明文やトピックを解析して **カテゴリ** と **タグ** を自動生成します。作成済みカテゴリをワンクリックで再利用できるクイックボタンも備えています。
- ⚡ **「最新リリースのみ＋今後の更新」(`only_latest`) vs 「全履歴」モード**:
  - リポジトリごとに（Web UI と Telegram ボットの両方で）、過去の全履歴をダウンロードするか、**現在の最新バージョンと今後の新規リリースのみ** をダウンロードするかを選択できます。
- ⏸ **全体一時停止＆リポジトリ別一時停止**:
  - ワンクリックで全体の同期を一時停止・再開できるほか、特定のリポジトリだけを一時停止して他のリポジトリを稼働させ続けることも可能です。
- 🧹 **データ消去＆ 🗄 ディスク上の保存済みアーカイブ（監視解除後もアクセス可能）**:
  - **🧹 データ消去**: リポジトリのダウンロード済みファイルを消去し、新しいダウンロード設定で最初からやり直せます。
  - **🗑 ファイル保持を選べるリポジトリ削除**: 監視リストからリポジトリを削除する際、ディスク上のファイルを削除するか **保持するか** を選択できます。保持したファイルは **`🗄 ディスク上の保存済みアーカイブ`** セクションからいつでも閲覧・ダウンロード可能です！
- 🤖 **セキュアな個人専用 24/7 Telegram ボット**:
  - あなたの数値 **Telegram User ID** のみに応答し、他のすべてのアクセスを遮断します。
  - チャットに GitHub や Nexus Mods のリンクを送信するだけで、カテゴリやモード（*全履歴* vs *最新のみ＋今後*）を選択して Vault に追加できます。
  - `/menu`、`/status`、`/sync`、全体/個別の一時停止切り替え、リポジトリ削除を Telegram から直接操作できます。

---

## 🚀 クイックインストール

### オプション A: Linux / Proxmox LXC 自動インストールスクリプト (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

このスクリプトは `/opt/github-vault` に Python 環境を構築し、`/srv/github-vault` にアーカイブディレクトリを作成して、2つの `systemd` サービスを有効化します:
- `github-vault.service` (Web UI + API + バックグラウンド同期エンジン)
- `github-vault-bot.service` (24/7 Telegram ボット)

### オプション B: Docker & Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 初回ログイン＆セットアップウィザード (Setup Wizard)

1. ブラウザで **`http://<サーバーIP>:8080`** を開きます
2. デフォルトの認証情報で初回ログインを行います:
   - **ユーザー名:** `admin`
   - **パスワード:** `admin`
3. 初回ログイン時に **5ステップのセットアップウィザード** が自動的に開きます（上部の **`📖 ガイド＆ウィザード`** からいつでも再表示可能）:
   - **ステップ 1 — 言語＆管理者アカウント**: 10言語から好きな言語を選択し、管理者ユーザー名と新しいパスワードを設定します。
   - **ステップ 2 — GitHub Personal Access Token**: `github.com/settings/tokens` で `classic` トークンを発行する手順を案内します（制限が60回/時から5,000回/時に増加）。
   - **ステップ 3 — Nexus Mods API ＆ Cookie**: 自動直接ダウンロードを有効にするため、`Personal API Key` と `nexusmods_session` Cookie（`F12` → *Application* → *Cookies*）の取得手順を案内します。
   - **ステップ 4 — 24/7 Telegram ボット**: `@BotFather` でのボット作成と `@userinfobot` での数値 User ID 取得手順を案内します。
   - **ステップ 5 — コマンド＆機能マニュアル**: Web UI と Telegram ボットの全機能ガイドです。

---

## 📁 プロジェクト構成

```text
release-vault/
├── server.py              # FastAPI バックエンド、SQLite、GitHub/Nexus Mods ダウンローダー＆API
├── telegram_bot.py        # User ID アクセス制限付き 24/7 対話型 Telegram ボット
├── README.md              # 10言語セレクター付きメイン README
├── docs/                  # 全10言語に翻訳された README ファイル群
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
│   └── index.html         # シングルページ Web UI、セットアップウィザード、10言語対応、Markdown ビューア
├── install.sh             # Debian/Ubuntu/Proxmox LXC 用自動インストーラー (systemd)
├── Dockerfile             # Docker コンテナイメージ
├── docker-compose.yml     # すぐに使える Docker Compose スタック
├── docker-entrypoint.sh   # Docker エントリポイント (Telegram ボット + Web サーバーを起動)
├── requirements.txt       # Python 依存パッケージ
└── .env.example           # オプションの環境変数サンプル
```

---

## ☕ プロジェクトの支援 / 寄付

**Release Vault** を気に入っていただけた場合、開発をサポートしていただけると嬉しいです:

👉 **[☕ PayPal でサポート / 寄付する (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
