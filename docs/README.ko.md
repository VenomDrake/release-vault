# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_후원_%2F_기부-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **언어를 선택하세요:**
> [🇮🇹 Italiano](../README.md) · [🇬🇧 English](README.en.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · [🇧🇷 Português](README.pt.md) · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · **[🇰🇷 한국어](README.ko.md)**

**GitHub** 프로젝트 및 **Nexus Mods** 모드를 위한 **셀프 호스팅 릴리스 아카이버, 패치 노트 탐색기 & 24/7 텔레그램 봇**.

전체 인터페이스를 완벽하게 번역하는 **10개 언어**를 지원하며, 상단 **`📖 가이드 및 마법사`** 버튼을 통해 언제든 다시 열 수 있는 **대화형 5단계 초기 설정 마법사(Setup Wizard)**가 포함되어 있습니다.

---

## ✨ 주요 기능

- 🐙 **완벽한 GitHub 아카이빙**:
  - 모든 릴리스(정식 버전 및 프리릴리스/베타), 바이너리 에셋, 소스 코드(`.zip` / `.tar.gz`), Markdown 패치 노트(`PATCH_NOTES.md`), 그리고 **SHA256** 해시 검증이 포함된 메타데이터(`release-metadata.json`)를 자동으로 다운로드합니다.
  - **스마트한 GitHub API 속도 제한 우회**: `codeload.github.com`을 통해 소스 코드를 직접 다운로드(API 할당량 소모 없음)하며, 토큰 없이 시간당 60회 제한에 도달하거나 정식 릴리스가 없는 저장소의 경우 자동으로 Atom/HTML 피드로 대체합니다.
- 🎮 **Nexus Mods 네이티브 지원 (무료 계정에서도 작동)**:
  - `https://www.nexusmods.com/<게임>/mods/<id>` 링크를 붙여넣으면 모드 이름, 썸네일, Markdown으로 변환된 BBCode 설명, 버전 기록(`MAIN`, `OPTIONAL`, `OLD_VERSION`)을 가져오고, `Personal API Key`와 `nexusmods_session` 쿠키를 결합하여 서버로 직접 아카이브를 다운로드합니다.
- 🧠 **스마트 자동 태그 및 카테고리 기억**:
  - GitHub 또는 Nexus Mods 링크를 붙여넣으면 설명과 토픽을 분석하여 **카테고리**와 **태그**를 자동 생성하며, 기존 카테고리를 즉시 재사용할 수 있는 빠른 선택 버튼을 제공합니다.
- ⚡ **"최신 릴리스만 + 향후 업데이트" (`only_latest`) vs "전체 기록" 모드**:
  - 웹 UI와 텔레그램 봇 모두에서 저장소별로 과거의 모든 버전을 다운로드할지, 아니면 **현재 최신 버전과 앞으로 출시될 업데이트만** 다운로드할지 선택할 수 있습니다.
- ⏸ **전체 일시중지 및 개별 저장소 일시중지**:
  - 클릭 한 번으로 전체 동기화를 일시중지/재개하거나, 다른 저장소는 유지한 채 특정 저장소만 일시중지할 수 있습니다.
- 🧹 **데이터 초기화 & 🗄 디스크에 보관된 아카이브 (활성 저장소 없이도 접근 가능)**:
  - **🧹 데이터 초기화**: 새로운 다운로드 옵션으로 다시 시작할 수 있도록 저장소의 다운로드된 파일을 비웁니다.
  - **🗑 파일 보관 선택이 가능한 저장소 삭제**: 모니터링 목록에서 저장소를 제거할 때 디스크에서 파일을 삭제할지 **보관할지** 선택할 수 있습니다. 보관된 파일은 **`🗄 디스크에 보관된 아카이브`** 섹션에서 언제든 탐색하고 다운로드할 수 있습니다!
- 🤖 **보안이 강화된 개인 전용 24/7 텔레그램 봇**:
  - 오직 본인의 숫자 **Telegram User ID**에만 응답하며 다른 모든 사용자의 접근을 차단합니다.
  - 채팅창에 GitHub 또는 Nexus Mods 링크를 바로 전송하여 카테고리와 다운로드 모드(*전체 기록* vs *최신만 + 향후*)를 선택해 Vault에 추가할 수 있습니다.
  - `/menu`, `/status`, `/sync` 대화형 명령어, 전체/개별 일시중지 전환 및 저장소 삭제를 텔레그램에서 직접 제어할 수 있습니다.

---

## 🚀 빠른 설치 가이드

### 옵션 A: Linux / Proxmox LXC 자동 설치 스크립트 (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

스크립트가 `/opt/github-vault`에 Python 가상 환경을 구성하고 `/srv/github-vault`에 아카이브 저장소를 생성하며 두 개의 `systemd` 서비스를 활성화합니다:
- `github-vault.service` (웹 UI + API + 백그라운드 동기화 엔진)
- `github-vault-bot.service` (24/7 텔레그램 봇)

### 옵션 B: Docker 및 Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 첫 로그인 및 초기 설정 마법사 (Setup Wizard)

1. 브라우저에서 **`http://<서버-IP>:8080`**에 접속합니다
2. 기본 계정 정보로 첫 로그인을 진행합니다:
   - **사용자 이름:** `admin`
   - **비밀번호:** `admin`
3. 첫 로그인 시 **5단계 초기 설정 마법사**가 자동으로 열립니다 (상단 **`📖 가이드 및 마법사`** 버튼으로 언제든 다시 열기 가능):
   - **1단계 — 언어 및 관리자 계정**: 10개 지원 언어 중 원하는 언어를 선택하고 새 관리자 아이디와 비밀번호를 설정합니다.
   - **2단계 — GitHub 개인용 액세스 토큰 (PAT)**: `github.com/settings/tokens`에서 `classic` 토큰을 발급받는 단계별 가이드를 제공합니다 (API 한도를 시간당 60회에서 5,000회로 상향).
   - **3단계 — Nexus Mods API 및 쿠키**: 자동 직접 다운로드를 위해 `Personal API Key`와 `nexusmods_session` 쿠키(`F12` → *Application* → *Cookies*)를 복사하는 방법을 안내합니다.
   - **4단계 — 24/7 텔레그램 봇**: `@BotFather`로 봇을 생성하고 `@userinfobot`으로 숫자 User ID를 확인하는 방법을 안내합니다.
   - **5단계 — 명령어 및 기능 매뉴얼**: 웹 UI와 텔레그램 봇의 모든 기능을 요약해 안내합니다.

---

## 📁 프로젝트 구조

```text
release-vault/
├── server.py              # FastAPI 백엔드, SQLite, GitHub/Nexus Mods 다운로더 및 API
├── telegram_bot.py        # User ID 접근 제어가 적용된 24/7 대화형 텔레그램 봇
├── README.md              # 10개 언어 선택기가 포함된 메인 README
├── docs/                  # 지원되는 10개 언어로 번역된 README 문서
│   ├── README.en.md
│   ├── README.es.md
│   ├── README.fr.md
│   ├── README.de.md
│   ├── README.pt.md
│   ├── README.ru.md
│   ├── README.zh.md
│   ├── README.ja.md
│   └── README.ko.md
├── static/
│   └── index.html         # 싱글 페이지 웹 UI, 설정 마법사, 10개 언어 지원, Markdown 뷰어
├── install.sh             # Debian/Ubuntu/Proxmox LXC용 자동 설치 스크립트 (systemd)
├── Dockerfile             # Docker 컨테이너 이미지
├── docker-compose.yml     # 바로 사용 가능한 Docker Compose 스택
├── docker-entrypoint.sh   # Docker 엔트리포인트 (텔레그램 봇 + 웹 서버 실행)
├── requirements.txt       # Python 의존성 패키지
└── .env.example           # 선택적 환경 변수 예제
```

---

## ☕ 프로젝트 후원 / 기부

**Release Vault**가 유용하셨다면 개발 지원을 위해 후원해 주실 수 있습니다:

👉 **[☕ PayPal로 후원 / 기부하기 (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
