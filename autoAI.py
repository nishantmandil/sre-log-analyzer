"""
=============================================================
  SRE Incident RCA System -- AI-Assisted Log Analysis Tool
  Description: Scans a directory of log files and uses a free
               LLM to generate a beautiful HTML RCA report.

  Supported providers (pick one in your .env file):
    1. Anthropic Claude  ->  https://console.anthropic.com
    2. Google Gemini     ->  https://aistudio.google.com
    3. Groq              ->  https://console.groq.com
    4. Ollama            ->  https://ollama.com (local)

  Install: pip install anthropic google-generativeai groq python-dotenv
=============================================================
"""

from functools import cache
import os
import sys
import json
import glob
import re
import hashlib
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

PROVIDER    = os.getenv("LLM_PROVIDER", "groq")
LOGS_DIR    = os.getenv("LOGS_DIR", "logs")          # folder with all .log / .txt files
REPORT_FILE = "rca_report.html"

CACHE_FILE = "cache.json"

def load_cache():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


# --------------------------------------------------------------
# Step 1 -- Discover all log files in a directory
# --------------------------------------------------------------
def discover_log_files(directory: str) -> list[str]:
    if not os.path.exists(directory):
        raise FileNotFoundError(
            f"Logs directory not found: {directory}\n"
            "Set LOGS_DIR in your .env or create a 'logs/' folder."
        )
    patterns = ["*.log", "*.txt"]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(os.path.join(directory, "**", pattern), recursive=True))
    files = sorted(set(files))
    if not files:
        raise FileNotFoundError(f"No .log or .txt files found in: {directory}")
    return files


# --------------------------------------------------------------
# Step 2 -- Read and filter a single log file
# --------------------------------------------------------------
def read_and_filter(filepath: str) -> tuple[int, str]:
    with open(filepath, "r", errors="ignore") as f:
        lines = f.readlines()
    total = len(lines)
    important = [
        l.rstrip() for l in lines
        if any(kw in l for kw in ["ERROR", "WARNING", "CRITICAL", "FATAL", "EXCEPTION"])
    ]
    return total, "\n".join(important)

timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"

def extract_timeline(lines):
    timestamps = []

    for line in lines:
        match = re.search(timestamp_pattern, line)
        if match:
            timestamps.append(match.group())

    if not timestamps:
        return None

    start = timestamps[0]
    end = timestamps[-1]

    counts = Counter(timestamps)
    peak = counts.most_common(1)[0][0]

    return {
        "incident_start": start,
        "incident_peak": peak,
        "incident_end": end
    }

def group_errors(lines):
    errors = Counter()

    for line in lines:
        if "ERROR" in line:
            key = line.split("ERROR")[-1].strip()
            errors[key] += 1

    return errors


# --------------------------------------------------------------
# Step 3 -- Prompts
# --------------------------------------------------------------
def build_prompts(log_content: str) -> tuple[str, str]:
    system_prompt = (
        "You are a senior Site Reliability Engineer (SRE) with 10+ years of experience. "
        "Analyze application/infrastructure logs and identify: "
        "1. What happened (incident summary) "
        "2. The most likely root cause "
        "3. Impact on users/systems "
        "4. Recommended fix "
        "5. Prevention tips. "
        "Be concise, technical, and actionable."
    )
    user_prompt = f"""Analyze these logs and return ONLY a JSON object (no markdown, no explanation):

=== LOGS ===
{log_content}
============

Return this exact JSON structure:
{{
  "incident_summary": "2-3 sentence summary",
  "root_cause": "The most likely root cause",
  "impact": "What was affected and estimated duration",
  "severity": "CRITICAL | HIGH | MEDIUM | LOW",
  "recommended_fix": ["step 1", "step 2", "step 3"],
  "prevention": ["tip 1", "tip 2", "tip 3"]
}}"""
    return system_prompt, user_prompt


# --------------------------------------------------------------
# Step 4 -- LLM Providers
# --------------------------------------------------------------
def analyze_with_claude(log_content: str) -> dict:
    try:
        import anthropic
    except ImportError:
        sys.exit("Run: pip install anthropic")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set in .env")
    client = anthropic.Anthropic(api_key=api_key)
    system_prompt, user_prompt = build_prompts(log_content)
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )
    raw = message.content[0].text
    return json.loads(raw.strip().strip("```json").strip("```").strip())


def analyze_with_gemini(log_content: str) -> dict:
    try:
        import google.generativeai as genai
    except ImportError:
        sys.exit("Run: pip install google-generativeai")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY not set in .env")
    genai.configure(api_key=api_key)
    system_prompt, user_prompt = build_prompts(log_content)
    model = genai.GenerativeModel(model_name="gemini-1.5-flash", system_instruction=system_prompt)
    response = model.generate_content(user_prompt)
    raw = response.text.strip().strip("```json").strip("```").strip()
    return json.loads(raw)


def analyze_with_groq(log_content: str) -> dict:
    try:
        from groq import Groq
    except ImportError:
        sys.exit("Run: pip install groq")
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        sys.exit("GROQ_API_KEY not set in .env")
    client = Groq(api_key=api_key)
    system_prompt, user_prompt = build_prompts(log_content)
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    raw = response.choices[0].message.content.strip().strip("```json").strip("```").strip()
    return json.loads(raw)


def analyze_with_ollama(log_content: str) -> dict:
    import urllib.request, json as _json
    system_prompt, user_prompt = build_prompts(log_content)
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")
    payload = _json.dumps({
        "model": ollama_model,
        "prompt": f"{system_prompt}\n\n{user_prompt}",
        "stream": False
    }).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = _json.loads(resp.read())
    raw = result.get("response", "{}").strip().strip("```json").strip("```").strip()
    return _json.loads(raw)


def analyze_logs_with_ai(log_content: str) -> dict:
    providers = {
        "claude": analyze_with_claude,
        "gemini": analyze_with_gemini,
        "groq":   analyze_with_groq,
        "ollama": analyze_with_ollama,
    }
    if PROVIDER not in providers:
        sys.exit(f"Unknown provider '{PROVIDER}'. Valid: {', '.join(providers.keys())}")
    return providers[PROVIDER](log_content)


def process_file(filepath, cache):

    try:
        total_lines, important = read_and_filter(filepath)

        if not important:
            return {
                "file": filepath,
                "status": "clean",
                "total_lines": total_lines,
                "important_lines": 0
            }

        filehash = file_hash(filepath)

        if filehash in cache:
            return cache[filehash]

        important_lines = important.splitlines()

        timeline = extract_timeline(important_lines)

        grouped = group_errors(important_lines)

        grouped_text = "\n".join([f"{k}: {v}" for k, v in grouped.items()])

        ai_input = important + "\n\nError Summary:\n" + grouped_text

        rca = analyze_logs_with_ai(ai_input)

        result = {
            "file": filepath,
            "status": "analyzed",
            "total_lines": total_lines,
            "important_lines": len(important_lines),
            "timeline": timeline,
            "rca": rca,
        }

        cache[filehash] = result

        return result

    except Exception as e:
        return {
            "file": filepath,
            "status": "failed",
            "error": str(e)
        }

# --------------------------------------------------------------
# Step 5 -- Generate beautiful HTML report
# --------------------------------------------------------------
def generate_html_report(results: list[dict], output_path: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total_files   = len(results)
    clean_files   = sum(1 for r in results if r["status"] == "clean")
    error_files   = sum(1 for r in results if r["status"] == "analyzed")
    failed_files  = sum(1 for r in results if r["status"] == "failed")
    critical_count = sum(1 for r in results if r.get("rca", {}).get("severity") == "CRITICAL")
    high_count     = sum(1 for r in results if r.get("rca", {}).get("severity") == "HIGH")

    def severity_class(sev):
        return {"CRITICAL": "sev-critical", "HIGH": "sev-high",
                "MEDIUM": "sev-medium", "LOW": "sev-low"}.get(sev, "sev-low")

    def severity_icon(sev):
        return {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(sev, "🟢")

    cards_html = ""
    for i, r in enumerate(results):
        fname = os.path.basename(r["file"])
        if r["status"] == "clean":
            cards_html += f"""
            <div class="card card-clean" data-index="{i}">
                <div class="card-header">
                    <div class="file-info">
                        <span class="file-icon">📄</span>
                        <div>
                            <div class="file-name">{fname}</div>
                            <div class="file-meta">{r['total_lines']} lines &nbsp;·&nbsp; {r['file']}</div>
                        </div>
                    </div>
                    <span class="badge badge-clean">✅ Clean</span>
                </div>
                <p class="clean-msg">No errors, warnings, or critical events detected.</p>
            </div>"""
        elif r["status"] == "failed":
            cards_html += f"""
            <div class="card card-failed" data-index="{i}">
                <div class="card-header">
                    <div class="file-info">
                        <span class="file-icon">📄</span>
                        <div>
                            <div class="file-name">{fname}</div>
                            <div class="file-meta">{r['file']}</div>
                        </div>
                    </div>
                    <span class="badge badge-failed">⚠️ Parse Error</span>
                </div>
                <p class="clean-msg">Could not analyze: {r.get('error','Unknown error')}</p>
            </div>"""
        else:
            rca = r["rca"]
            sev = rca.get("severity", "LOW")
            sc  = severity_class(sev)
            si  = severity_icon(sev)
            fix_items  = "".join(f"<li>{s}</li>" for s in rca.get("recommended_fix", []))
            prev_items = "".join(f"<li>{s}</li>" for s in rca.get("prevention", []))
            cards_html += f"""
            <div class="card card-issue {sc}-border" data-index="{i}">
                <div class="card-header" onclick="toggleCard(this)">
                    <div class="file-info">
                        <span class="file-icon">📄</span>
                        <div>
                            <div class="file-name">{fname}</div>
                            <div class="file-meta">{r['total_lines']} lines &nbsp;·&nbsp; {r['important_lines']} flagged &nbsp;·&nbsp; {r['file']}</div>
                        </div>
                    </div>
                    <div class="header-right">
                        <span class="badge {sc}">{si} {sev}</span>
                        <span class="chevron">▼</span>
                    </div>
                </div>
                <div class="card-body">
                    <div class="rca-grid">
                        <div class="rca-section">
                            <div class="rca-label">📋 Incident Summary</div>
                            <div class="rca-content">{rca.get('incident_summary','—')}</div>
                        </div>
                        <div class="rca-section">
                            <div class="rca-label">🔍 Root Cause</div>
                            <div class="rca-content">{rca.get('root_cause','—')}</div>
                        </div>
                        <div class="rca-section">
                            <div class="rca-label">💥 Impact</div>
                            <div class="rca-content">{rca.get('impact','—')}</div>
                        </div>
                        <div class="rca-section full-width">
                            <div class="rca-label">🛠 Recommended Fix</div>
                            <ul class="rca-list">{fix_items}</ul>
                        </div>
                        <div class="rca-section full-width">
                            <div class="rca-label">🛡 Prevention</div>
                            <ul class="rca-list">{prev_items}</ul>
                        </div>
                    </div>
                </div>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SRE RCA Report — {timestamp}</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg: #0d1117;
    --surface: #161b22;
    --surface2: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #7d8590;
    --accent: #58a6ff;
    --critical: #f85149;
    --high: #f0883e;
    --medium: #d29922;
    --low: #3fb950;
    --clean: #238636;
    --radius: 10px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'IBM Plex Sans', sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 0 0 60px;
  }}

  /* ── Header ── */
  .header {{
    background: linear-gradient(135deg, #0d1117 0%, #161b22 50%, #0d1117 100%);
    border-bottom: 1px solid var(--border);
    padding: 40px 48px 32px;
    position: relative;
    overflow: hidden;
  }}
  .header::before {{
    content: '';
    position: absolute;
    top: -80px; right: -80px;
    width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(88,166,255,0.08) 0%, transparent 70%);
    pointer-events: none;
  }}
  .header-top {{
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
  }}
  .brand {{
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .brand-icon {{
    width: 48px; height: 48px;
    background: linear-gradient(135deg, #1f6feb, #388bfd);
    border-radius: 12px;
    display: flex; align-items: center; justify-content: center;
    font-size: 24px;
    box-shadow: 0 4px 20px rgba(88,166,255,0.3);
  }}
  .brand-title {{ font-size: 22px; font-weight: 700; letter-spacing: -0.3px; }}
  .brand-sub {{ font-size: 13px; color: var(--text-muted); margin-top: 2px; font-family: 'IBM Plex Mono', monospace; }}
  .meta-pill {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 6px 14px;
    font-size: 12px;
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
  }}

  /* ── Stats ── */
  .stats {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    gap: 16px;
    margin-top: 32px;
  }}
  .stat {{
    background: var(--surface2);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 18px 20px;
    transition: border-color 0.2s;
  }}
  .stat:hover {{ border-color: var(--accent); }}
  .stat-value {{ font-size: 32px; font-weight: 700; font-family: 'IBM Plex Mono', monospace; line-height: 1; }}
  .stat-label {{ font-size: 12px; color: var(--text-muted); margin-top: 6px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .stat.critical .stat-value {{ color: var(--critical); }}
  .stat.high .stat-value {{ color: var(--high); }}
  .stat.clean-stat .stat-value {{ color: var(--low); }}
  .stat.total .stat-value {{ color: var(--accent); }}

  /* ── Filters ── */
  .controls {{
    padding: 24px 48px 0;
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
  }}
  .filter-btn {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 7px 16px;
    font-size: 13px;
    color: var(--text-muted);
    cursor: pointer;
    transition: all 0.2s;
    font-family: 'IBM Plex Sans', sans-serif;
  }}
  .filter-btn:hover, .filter-btn.active {{
    background: var(--accent);
    border-color: var(--accent);
    color: #0d1117;
    font-weight: 600;
  }}
  .search-box {{
    margin-left: auto;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 7px 16px;
    font-size: 13px;
    color: var(--text);
    width: 220px;
    font-family: 'IBM Plex Sans', sans-serif;
    outline: none;
    transition: border-color 0.2s;
  }}
  .search-box:focus {{ border-color: var(--accent); }}
  .search-box::placeholder {{ color: var(--text-muted); }}

  /* ── Cards ── */
  .cards {{
    padding: 24px 48px 0;
    display: flex;
    flex-direction: column;
    gap: 14px;
  }}
  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    transition: border-color 0.2s, transform 0.2s;
    animation: fadeIn 0.3s ease both;
  }}
  .card:hover {{ border-color: #484f58; transform: translateY(-1px); }}
  @keyframes fadeIn {{ from {{ opacity:0; transform: translateY(8px); }} to {{ opacity:1; transform: translateY(0); }} }}

  .card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    cursor: pointer;
    user-select: none;
  }}
  .file-info {{ display: flex; align-items: center; gap: 12px; }}
  .file-icon {{ font-size: 20px; }}
  .file-name {{ font-weight: 600; font-size: 15px; }}
  .file-meta {{ font-size: 12px; color: var(--text-muted); margin-top: 2px; font-family: 'IBM Plex Mono', monospace; }}
  .header-right {{ display: flex; align-items: center; gap: 12px; }}
  .chevron {{ color: var(--text-muted); font-size: 12px; transition: transform 0.2s; }}
  .card-header.open .chevron {{ transform: rotate(180deg); }}

  /* Severity borders */
  .sev-critical-border {{ border-left: 3px solid var(--critical) !important; }}
  .sev-high-border     {{ border-left: 3px solid var(--high) !important; }}
  .sev-medium-border   {{ border-left: 3px solid var(--medium) !important; }}
  .sev-low-border      {{ border-left: 3px solid var(--low) !important; }}

  /* Badges */
  .badge {{
    padding: 4px 12px; border-radius: 12px;
    font-size: 12px; font-weight: 600;
    font-family: 'IBM Plex Mono', monospace;
    white-space: nowrap;
  }}
  .sev-critical {{ background: rgba(248,81,73,0.15); color: var(--critical); border: 1px solid rgba(248,81,73,0.3); }}
  .sev-high     {{ background: rgba(240,136,62,0.15); color: var(--high);     border: 1px solid rgba(240,136,62,0.3); }}
  .sev-medium   {{ background: rgba(210,153,34,0.15); color: var(--medium);   border: 1px solid rgba(210,153,34,0.3); }}
  .sev-low      {{ background: rgba(63,185,80,0.15);  color: var(--low);      border: 1px solid rgba(63,185,80,0.3); }}
  .badge-clean  {{ background: rgba(35,134,54,0.15);  color: var(--clean);    border: 1px solid rgba(35,134,54,0.3); }}
  .badge-failed {{ background: rgba(210,153,34,0.15); color: var(--medium);   border: 1px solid rgba(210,153,34,0.3); }}

  /* Card body */
  .card-body {{ display: none; padding: 0 20px 20px; border-top: 1px solid var(--border); }}
  .card-body.open {{ display: block; animation: slideDown 0.25s ease; }}
  @keyframes slideDown {{ from {{ opacity:0; transform: translateY(-6px); }} to {{ opacity:1; transform: translateY(0); }} }}

  .rca-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-top: 16px;
  }}
  .rca-section {{ background: var(--surface2); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }}
  .rca-section.full-width {{ grid-column: 1 / -1; }}
  .rca-label {{ font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px; }}
  .rca-content {{ font-size: 14px; line-height: 1.6; color: var(--text); }}
  .rca-list {{ padding-left: 18px; }}
  .rca-list li {{ font-size: 14px; line-height: 1.7; color: var(--text); }}

  .clean-msg {{ padding: 0 20px 16px; font-size: 14px; color: var(--text-muted); }}

  /* Hidden cards */
  .card.hidden {{ display: none; }}

  /* Footer */
  .footer {{
    text-align: center;
    padding: 40px;
    font-size: 12px;
    color: var(--text-muted);
    font-family: 'IBM Plex Mono', monospace;
  }}

  @media (max-width: 700px) {{
    .header, .controls, .cards {{ padding-left: 20px; padding-right: 20px; }}
    .rca-grid {{ grid-template-columns: 1fr; }}
    .search-box {{ width: 100%; margin-left: 0; }}
  }}
</style>
</head>
<body>

<div class="header">
  <div class="header-top">
    <div class="brand">
      <div class="brand-icon">🔍</div>
      <div>
        <div class="brand-title">SRE Incident RCA Report</div>
        <div class="brand-sub">provider: {PROVIDER.upper()} &nbsp;·&nbsp; generated: {timestamp}</div>
      </div>
    </div>
    <div class="meta-pill">📁 {LOGS_DIR}</div>
  </div>

  <div class="stats">
    <div class="stat total">
      <div class="stat-value">{total_files}</div>
      <div class="stat-label">Total Files</div>
    </div>
    <div class="stat critical">
      <div class="stat-value">{critical_count}</div>
      <div class="stat-label">Critical</div>
    </div>
    <div class="stat high">
      <div class="stat-value">{high_count}</div>
      <div class="stat-label">High</div>
    </div>
    <div class="stat">
      <div class="stat-value" style="color:var(--medium)">{error_files}</div>
      <div class="stat-label">Files w/ Issues</div>
    </div>
    <div class="stat clean-stat">
      <div class="stat-value">{clean_files}</div>
      <div class="stat-label">Clean Files</div>
    </div>
  </div>
</div>

<div class="controls">
  <button class="filter-btn active" onclick="filterCards('all', this)">All ({total_files})</button>
  <button class="filter-btn" onclick="filterCards('issue', this)">Issues ({error_files})</button>
  <button class="filter-btn" onclick="filterCards('clean', this)">Clean ({clean_files})</button>
  <button class="filter-btn" onclick="filterCards('sev-critical', this)">🔴 Critical ({critical_count})</button>
  <input class="search-box" type="text" placeholder="🔎 Search files..." oninput="searchCards(this.value)">
</div>

<div class="cards" id="cards-container">
{cards_html}
</div>

<div class="footer">
  SRE AI Log Analyzer &nbsp;·&nbsp; {total_files} files processed &nbsp;·&nbsp; {timestamp}
</div>

<script>
  function toggleCard(header) {{
    header.classList.toggle('open');
    const body = header.nextElementSibling;
    body.classList.toggle('open');
  }}

  function filterCards(type, btn) {{
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    document.querySelectorAll('.card').forEach(card => {{
      if (type === 'all') {{ card.classList.remove('hidden'); return; }}
      if (type === 'issue') {{ card.classList.toggle('hidden', !card.classList.contains('card-issue')); return; }}
      if (type === 'clean') {{ card.classList.toggle('hidden', !card.classList.contains('card-clean')); return; }}
      card.classList.toggle('hidden', !card.classList.contains(type + '-border'));
    }});
  }}

  function searchCards(query) {{
    const q = query.toLowerCase();
    document.querySelectorAll('.card').forEach(card => {{
      const text = card.innerText.toLowerCase();
      card.classList.toggle('hidden', q.length > 0 && !text.includes(q));
    }});
  }}

  // Auto-expand CRITICAL cards
  document.querySelectorAll('.sev-critical-border').forEach(card => {{
    const header = card.querySelector('.card-header');
    const body   = card.querySelector('.card-body');
    if (header && body) {{ header.classList.add('open'); body.classList.add('open'); }}
  }});
</script>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✅ HTML report saved to: {output_path}")


# --------------------------------------------------------------
# Main
# --------------------------------------------------------------
def main():
    print("=" * 60)
    print("  SRE Log Analyzer — Root Cause Analysis")
    print(f"  Provider : {PROVIDER.upper()}")
    print(f"  Logs Dir : {LOGS_DIR}")
    print("=" * 60 + "\n")

    try:
        log_files = discover_log_files(LOGS_DIR)
    except FileNotFoundError as e:
        sys.exit(str(e))

    print(f"Found {len(log_files)} log file(s) to analyze.\n")

    results = []
    cache = load_cache()

    with ThreadPoolExecutor(max_workers=5) as executor:

        futures = []

        for filepath in log_files:
            futures.append(executor.submit(process_file, filepath, cache))

        for i, future in enumerate(futures, 1):

            result = future.result()

            fname = os.path.basename(result["file"])

            print(f"[{i}/{len(log_files)}] {fname} ... ", end="")

            if result["status"] == "clean":
                print("✅ Clean")

            elif result["status"] == "analyzed":
                sev = result["rca"].get("severity", "?")
                print(f"⚠️ {sev}")

            else:
                print("❌ Failed")

            results.append(result)

            save_cache(cache)

    generate_html_report(results, REPORT_FILE)

    # Summary
    issues = sum(1 for r in results if r["status"] == "analyzed")
    clean  = sum(1 for r in results if r["status"] == "clean")
    print(f"\n📊 Summary: {len(log_files)} files | {issues} with issues | {clean} clean")
    print(f"🌐 Open {REPORT_FILE} in your browser to view the full report.")


if __name__ == "__main__":
    main()
