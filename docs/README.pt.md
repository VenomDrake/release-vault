# 🗄️ Release Vault

[![Donate with PayPal](https://img.shields.io/badge/☕_Apoiar_%2F_Doar-PayPal.Me%2Fvenomdrake-0070ba?style=for-the-badge&logo=paypal&logoColor=white)](https://www.paypal.com/paypalme/venomdrake)
[![License: MIT](https://img.shields.io/badge/License-MIT-emerald?style=for-the-badge)](../LICENSE)

> 🌐 **Selecione o seu idioma / Select your language:**
> [🇬🇧 English](../README.md) · [🇮🇹 Italiano](README.it.md) · [🇪🇸 Español](README.es.md) · [🇫🇷 Français](README.fr.md) · [🇩🇪 Deutsch](README.de.md) · **[🇧🇷 Português](README.pt.md)** · [🇷🇺 Русский](README.ru.md) · [🇨🇳 中文](README.zh.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md)

**Arquivador Auto-Hospedado de Releases, Explorador de Notas de Atualização e Bot do Telegram 24/7** para projetos do **GitHub** e mods do **Nexus Mods**.

Suporta **10 idiomas completos** que traduzem toda a interface e inclui um **Assistente Interativo de Configuração Inicial em 5 Passos (Setup Wizard)** acessível a qualquer momento pelo botão **`📖 Guia e Assistente`**.

---

## ✨ Funcionalidades Principais

- 🐙 **Arquivamento Completo do GitHub**:
  - Baixa automaticamente todas as releases (Estáveis e Pré-lançamentos/Beta), arquivos binários, código-fonte (`.zip` / `.tar.gz`), notas de lançamento em Markdown (`PATCH_NOTES.md`) e metadados (`release-metadata.json`) com verificação **SHA256**.
  - **Bypass inteligente de limite de API do GitHub**: download direto do código-fonte via `codeload.github.com` (zero consumo de cota da API) e fallback automático via feed Atom/HTML ao atingir o limite de 60 requisições/hora sem token ou para repositórios sem releases formais.
- 🎮 **Suporte Nativo ao Nexus Mods (Funciona também com Conta Gratuita)**:
  - Cole qualquer link `https://www.nexusmods.com/<jogo>/mods/<id>`: obtém nome, miniatura, descrição BBCode convertida para Markdown, histórico de versões (`MAIN`, `OPTIONAL`, `OLD_VERSION`) e baixa diretamente os arquivos no seu servidor combinando a `Personal API Key` e o cookie `nexusmods_session`.
- 🧠 **Auto-Tagging Inteligente e Memória de Categorias**:
  - Ao colar um link do GitHub ou Nexus Mods, o sistema analisa a descrição e os tópicos para sugerir automaticamente a **Categoria** e as **Tags**, com botões rápidos para reutilizar categorias existentes.
- ⚡ **Modo "Apenas Última Release + Futuras" (`only_latest`) vs "Histórico Completo"**:
  - Escolha para cada repositório (tanto na Web UI quanto no Bot do Telegram) se deseja baixar todo o histórico passado ou **apenas a versão mais recente atual e as atualizações futuras**.
- ⏸ **Pausa Global e Pausa por Repositório Individual**:
  - Pause ou retome a sincronização global com um clique, ou pause apenas repositórios específicos mantendo os demais ativos.
- 🧹 **Limpar Dados e 🗄 Arquivos Preservados no Disco (Sem Repositório Ativo)**:
  - **🧹 Limpar Dados**: apague os arquivos baixados de um repositório para recomeçar do zero com novas opções de download.
  - **🗑 Excluir Repositório com Opção de Preservar Arquivos**: ao remover um repositório do monitoramento ativo, escolha entre excluir os arquivos do disco ou **preservá-los**. Os arquivos preservados continuam navegáveis e disponíveis para download na seção **`🗄 Arquivos Preservados no Disco`**!
- 🤖 **Bot do Telegram Pessoal 24/7 Blindado**:
  - Responde exclusivamente ao seu **User ID numérico do Telegram** (bloqueando qualquer outra pessoa).
  - Envie qualquer link do GitHub ou Nexus Mods diretamente no chat para adicioná-lo ao Vault escolhendo categoria e modo de download.
  - Comandos interativos `/menu`, `/status`, `/sync`, pausa global/individual e exclusão de repositórios diretamente pelo Telegram.

---

## 🚀 Instalação Rápida

### Opzione A: Script Automático Linux / Proxmox LXC (Debian / Ubuntu)

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
chmod +x install.sh
sudo ./install.sh
```

O script configura o ambiente Python em `/opt/github-vault`, cria o diretório de arquivos em `/srv/github-vault` e ativa os dois serviços `systemd`:
- `github-vault.service` (Interface Web + API + Motor de sincronização)
- `github-vault-bot.service` (Bot do Telegram 24/7)

### Opção B: Docker e Docker Compose

```bash
git clone https://github.com/VenomDrake/release-vault.git release-vault
cd release-vault
docker compose up -d --build
```

---

## 🔑 Primeiro Acesso e Assistente de Configuração (Setup Wizard)

1. Abra o navegador em **`http://<IP-DO-SERVIDOR>:8080`**
2. Faça o primeiro login com as credenciais padrão:
   - **Usuário:** `admin`
   - **Senha:** `admin`
3. No primeiro acesso será aberto automaticamente o **Assistente Guiado em 5 Passos** (que pode ser reaberto a qualquer momento clicando em **`📖 Guia e Assistente`**):
   - **Passo 1 — Idioma e Conta Admin**: Escolha entre os 10 idiomas e defina seu usuário e senha de administrador.
   - **Passo 2 — GitHub Personal Access Token**: Guia passo a passo para gerar um token `classic` em `github.com/settings/tokens` (aumenta o limite de 60 para 5.000 requisições/hora).
   - **Passo 3 — API e Cookie do Nexus Mods**: Guia passo a passo para copiar sua `Personal API Key` e o cookie `nexusmods_session` (`F12` → *Application* → *Cookies*).
   - **Passo 4 — Bot do Telegram 24/7**: Guia passo a passo para criar seu bot com `@BotFather` e obter seu ID numérico com `@userinfobot`.
   - **Passo 5 — Manual de Comandos e Funções**: Resumo completo de todas as funções Web e do Telegram.

---

## 📁 Estrutura do Projeto

```text
release-vault/
├── server.py              # Backend FastAPI, SQLite, Downloader GitHub/Nexus Mods e API
├── telegram_bot.py        # Bot do Telegram 24/7 interativo com controle de acesso por User ID
├── README.md              # README principal com seletor de 10 idiomas
├── docs/                  # Arquivos README traduzidos nos 10 idiomas suportados
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
│   └── index.html         # Web UI Single-Page App, Setup Wizard, 10 Idiomas, Visualizador Markdown
├── install.sh             # Instalador automático para Debian/Ubuntu/Proxmox LXC (systemd)
├── Dockerfile             # Imagem de container Docker
├── docker-compose.yml     # Stack Docker Compose pronta para uso
├── docker-entrypoint.sh   # Entrypoint Docker (inicia Bot do Telegram + Servidor Web)
├── requirements.txt       # Dependências do Python
└── .env.example           # Variáveis de ambiente opcionais
```

---

## ☕ Apoie o Projeto / Doar

Se o **Release Vault** é útil para você e deseja apoiar o seu desenvolvimento:

👉 **[☕ Apoiar / Doar pelo PayPal (paypal.me/venomdrake)](https://www.paypal.com/paypalme/venomdrake)**
