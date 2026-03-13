# SRE AI Log Analyzer

A lightweight command-line tool that scans application logs, filters out the noise, and uses a free LLM to generate a structured Root Cause Analysis (RCA) report — in seconds.

No paid API required. Works with Groq, Google Gemini, Anthropic Claude, or a fully local Ollama model.

---

## How it works

```
logs.txt
   |
   |-- reads all lines
   |-- filters ERROR / WARNING / CRITICAL / FATAL / EXCEPTION
   |
   v
Free LLM (Groq / Gemini / Claude / Ollama)
   |
   v
Structured RCA Report
   |-- Incident Summary
   |-- Root Cause
   |-- Impact
   |-- Recommended Fix
   |-- Prevention Tips
   |
   v
rca_report.txt
```

---

## Supported LLM Providers

| Provider | Free Tier | Speed | API Key Required |
|---|---|---|---|
| Groq (Llama 3) | 500K tokens/day | Very fast | Yes — [console.groq.com](https://console.groq.com) |
| Google Gemini | 1,500 req/day | Fast | Yes — [aistudio.google.com](https://aistudio.google.com) |
| Anthropic Claude | Free tier available | Fast | Yes — [console.anthropic.com](https://console.anthropic.com) |
| Ollama (local) | Unlimited | Depends on hardware | No |

---

## Quickstart

**1. Clone the repo**

```bash
git clone https://github.com/your-username/sre-log-analyzer.git
cd sre-log-analyzer
```

**2. Create and activate a virtual environment**

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

**4. Configure your API key**

```bash
cp .env.example .env
```

Open `.env` and fill in your details:

```env
LLM_PROVIDER=groq          # claude | gemini | groq | ollama
GROQ_API_KEY=your_key_here
```

**5. Add your log file and run**

```bash
# Drop your logs into logs.txt, then:
python rca_analyzer.py
```

The RCA report is saved to `rca_report.txt`.

---

## Example Output

```
============================================================
  Incident RCA Report
  Generated : 2024-03-11 10:35:00
  Provider  : GROQ
============================================================

INCIDENT SUMMARY:
A database connection pool exhaustion triggered a cascade of
failures across the /api/orders and /api/users endpoints,
resulting in HTTP 500 errors and a pod restart. The primary
database became unreachable, initiating an automatic failover
to the replica. Service was restored within approximately 4 minutes.

ROOT CAUSE:
The connection pool was undersized (max_connections=100) relative
to traffic demand, compounded by a memory limit of 512Mi that
caused the pod to be OOMKilled before it could recover.

IMPACT:
Users of /api/orders and /api/users experienced failures for
roughly 2 minutes. The primary database was unreachable briefly,
triggering failover with potential replication lag.

RECOMMENDED FIX:
1. Increase max_connections in the connection pool configuration.
2. Raise the container memory limit above 512Mi.
3. Add alerting at 70% pool utilization, not just at exhaustion.

PREVENTION:
Implement auto-scaling for the database connection pool, conduct
regular load testing, and set up proactive monitoring on pool
usage and memory consumption trends.

============================================================
```

---

## Project Structure

```
sre-log-analyzer/
|-- rca_analyzer.py      # Main script
|-- logs.txt             # Your input log file (add your own)
|-- rca_report.txt       # Generated RCA report (auto-created)
|-- .env.example         # Environment variable template
|-- requirements.txt     # Python dependencies
|-- README.md
```

---

## Requirements

- Python 3.10+
- One of: `groq`, `google-generativeai`, `anthropic` (or Ollama running locally)

```
groq
anthropic
google-generativeai
python-dotenv
```

---

## Switching Providers

Just change one line in your `.env` file:

```env
LLM_PROVIDER=gemini    # or claude, groq, ollama
```

No code changes needed.

---

## Using Ollama (fully local)

If you prefer to keep everything on your own machine:

```bash
# Install Ollama from https://ollama.com, then pull a model
ollama pull llama3

# Start the server
ollama serve
```

Set in `.env`:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3
```

---

## Contributing

Pull requests are welcome. For major changes, open an issue first to discuss what you'd like to change.

---

## License

[MIT](LICENSE)
