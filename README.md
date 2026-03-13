<div align="center">

# 🔍 SRE AI Log Analyzer

**From raw logs to RCA report in seconds. Powered by free LLMs.**

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%7C%20Gemini%20%7C%20Claude%20%7C%20Ollama-blueviolet?style=flat-square)](#-supported-llm-providers)
[![No Paid API](https://img.shields.io/badge/No%20Paid%20API-Required-success?style=flat-square)](#-supported-llm-providers)

Scan an entire directory of application logs, filter the noise, and generate a **beautiful interactive HTML Root Cause Analysis report** — in seconds.

Works with **Groq**, **Google Gemini**, **Anthropic Claude**, or a fully **local Ollama** model.

</div>

---

## ✨ Features

- 📁 **Bulk directory scan** — point it at a folder with 100s of `.log` or `.txt` files and analyze them all in one run
- 🧠 **AI-powered RCA** — structured JSON output per incident: summary, root cause, impact, fix steps, and prevention tips
- 🌐 **Interactive HTML report** — color-coded severity cards, collapsible sections, live search & filter, no server needed
- 📊 **Dashboard summary** — total files, critical count, high count, and clean count at a glance
- 🔴 **Auto-expand critical issues** — the most urgent incidents open automatically on load
- 🔎 **Search & filter** — instantly find any log file, error keyword, or severity level
- 🔄 **Multi-provider support** — switch LLMs with a single `.env` change, no code edits needed
- 🟢 **Clean file detection** — files with no issues are clearly marked and separated

---

## 📸 Report Preview

```
┌──────────────────────────────────────────────────────────────────┐
│  🔍 SRE Incident RCA Report                                      │
│  provider: GROQ · generated: 2024-03-11 10:35:00  · 📁 logs/   │
│                                                                  │
│   12 Total    3 Critical    2 High    7 Issues    5 Clean        │
├──────────────────────────────────────────────────────────────────┤
│  [ All ]  [ Issues ]  [ Clean ]  [ 🔴 Critical ]  🔎 Search...  │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ▼ 📄 db-errors.log         18 lines · 6 flagged   🔴 CRITICAL  │
│  ┌────────────────────┬────────────────────────────────────────┐ │
│  │ 📋 Incident Summary│ Connection pool exhausted across       │ │
│  │                    │ /api/orders and /api/users endpoints   │ │
│  ├────────────────────┼────────────────────────────────────────┤ │
│  │ 🔍 Root Cause      │ max_connections=100 undersized for     │ │
│  │                    │ current traffic; pod OOMKilled at 512Mi│ │
│  ├────────────────────┼────────────────────────────────────────┤ │
│  │ 💥 Impact          │ ~2 min downtime · failover triggered   │ │
│  ├────────────────────┴────────────────────────────────────────┤ │
│  │ 🛠 Recommended Fix                                           │ │
│  │   1. Increase max_connections in pool configuration         │ │
│  │   2. Raise container memory limit above 512Mi               │ │
│  │   3. Alert at 70% pool utilization, not just exhaustion     │ │
│  ├──────────────────────────────────────────────────────────── ┤ │
│  │ 🛡 Prevention   Load test · Auto-scale · Monitor pool %     │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ▶ 📄 nginx.log                                      🟠 HIGH    │
│  ▶ 📄 kubernetes.log                                 🟠 HIGH    │
│  ▶ 📄 notification-service.log                       ✅ Clean   │
└──────────────────────────────────────────────────────────────────┘
```
<img width="1909" height="929" alt="image" src="https://github.com/user-attachments/assets/7fb419af-1542-4ace-b786-70c2ee26b059" />

---

## ⚙️ How It Works

```
logs/
 ├── app-server.log
 ├── database.log
 ├── nginx.log
 └── ... 100s more
       │
       ├─ reads all lines
       ├─ filters  ERROR · WARNING · CRITICAL · FATAL · EXCEPTION
       │
       ▼
Free LLM  (Groq / Gemini / Claude / Ollama)
       │
       ▼
Structured RCA per file
 ├── Severity     →  CRITICAL | HIGH | MEDIUM | LOW
 ├── Summary      →  What happened
 ├── Root Cause   →  Why it happened
 ├── Impact       →  Who was affected and for how long
 ├── Fix Steps    →  Step-by-step remediation actions
 └── Prevention   →  How to stop it from happening again
       │
       ▼
rca_report.html   ←  open in any browser, no server needed
```

---

## 🤖 Supported LLM Providers

| Provider | Free Tier | Speed | API Key Required |
|---|---|---|---|
| [Groq](https://console.groq.com) (Llama 3) | 500K tokens/day | ⚡ Very Fast | Yes |
| [Google Gemini](https://aistudio.google.com) | 1,500 req/day | 🚀 Fast | Yes |
| [Anthropic Claude](https://console.anthropic.com) | Free tier available | 🚀 Fast | Yes |
| [Ollama](https://ollama.com) (local) | Unlimited | Depends on hardware | ❌ Not needed |

---

## 🚀 Quickstart

**1. Clone the repo**

```bash
git clone https://github.com/nishantmandil/sre-log-analyzer.git
cd sre-log-analyzer
```

**2. Create a virtual environment**

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac / Linux
source venv/bin/activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

**4. Configure your provider**

```bash
cp .env.example .env
```

Open `.env` and fill in your details:

```env
LLM_PROVIDER=groq              # groq | claude | gemini | ollama
GROQ_API_KEY=your_key_here
LOGS_DIR=logs                  # path to your logs folder (relative or absolute)
```

**5. Add your logs and run**

```bash
mkdir logs
cp /path/to/your/logs/*.log logs/

python rca_analyzer.py
```

**6. Open the report**

```bash
# Windows
start rca_report.html

# Mac
open rca_report.html

# Linux
xdg-open rca_report.html
```

---

## 📁 Project Structure

```
sre-log-analyzer/
├── rca_analyzer.py          # Main script
├── logs/                    # Drop your .log or .txt files here (recursive)
│   ├── app-server.log
│   ├── database.log
│   └── ...
├── rca_report.html          # Generated HTML report (auto-created on run)
├── .env.example             # Environment variable template
├── .env                     # Your config & API keys  ← never commit this
├── .gitignore
├── requirements.txt
└── README.md
```

---

## 📦 Requirements

- Python 3.10+
- One of: `groq`, `google-generativeai`, `anthropic` — or Ollama running locally

```
groq
anthropic
google-generativeai
python-dotenv
```

Install all at once:

```bash
pip install groq anthropic google-generativeai python-dotenv
```

---

## 🔁 Switching Providers

Change one line in `.env` — no code changes needed:

```env
LLM_PROVIDER=gemini    # groq | claude | gemini | ollama
```

---

## 🖥️ Using Ollama (fully local, no API key)

```bash
# Install Ollama from https://ollama.com
ollama pull llama3
ollama serve
```

Set in `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3
LOGS_DIR=logs
```

---

## 🔒 Security Note

> ⚠️ **Never commit your `.env` file.** It contains your API keys.
> The `.gitignore` already excludes it. Only commit `.env.example` with placeholder values.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.

---

<div align="center">
  <sub>Built for SREs, developers, and anyone who has stared at logs at 2 AM.</sub>
</div>
