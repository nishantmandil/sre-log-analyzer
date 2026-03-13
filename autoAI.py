"""
=============================================================
  SRE Incident RCA System -- AI-Assisted Log Analysis Tool
  Description: Scans logs.txt and uses a free LLM to suggest
               root cause of errors if present.

  Supported providers (pick one in your .env file):
    1. Anthropic Claude  ->  https://console.anthropic.com   (free tier)
    2. Google Gemini     ->  https://aistudio.google.com     (free tier)
    3. Groq              ->  https://console.groq.com        (free, very fast)
    4. Ollama            ->  https://ollama.com              (local, no API key)

  Install: pip install anthropic google-generativeai groq python-dotenv
=============================================================
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Set your preferred provider via LLM_PROVIDER in .env
# Options: claude | gemini | groq | ollama
PROVIDER = os.getenv("LLM_PROVIDER", "groq")

LOG_FILE    = "logs.txt"
REPORT_FILE = "rca_report.txt"


# --------------------------------------------------------------
# Step 1 -- Read the log file
# --------------------------------------------------------------
def read_logs(filepath: str) -> str:
    """Read log file and return its content as a string."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Log file not found: {filepath}\n"
            "Please create a 'logs.txt' file in the same directory as this script."
        )

    with open(filepath, "r") as f:
        logs = f.read()

    print(f"Loaded log file : {filepath}")
    print(f"Total lines     : {len(logs.splitlines())}\n")
    return logs


# --------------------------------------------------------------
# Step 2 -- Filter only ERROR / WARNING / CRITICAL lines
# --------------------------------------------------------------
def extract_important_lines(logs: str) -> str:
    """Extract only WARNING, ERROR, and CRITICAL log lines."""
    important = []
    for line in logs.splitlines():
        if any(level in line for level in ["ERROR", "WARNING", "CRITICAL", "FATAL", "EXCEPTION"]):
            important.append(line)

    if not important:
        return ""

    print(f"Found {len(important)} warning/error/critical lines worth investigating.\n")
    return "\n".join(important)


# --------------------------------------------------------------
# Step 3 -- Build the prompts
# --------------------------------------------------------------
def build_prompts(log_content: str) -> tuple[str, str]:
    system_prompt = (
        "You are a senior Site Reliability Engineer (SRE) with 10+ years of experience. "
        "Your job is to analyze application/infrastructure logs and identify: "
        "1. What happened (incident summary) "
        "2. The most likely root cause "
        "3. Impact on users/systems "
        "4. Recommended fix or next steps. "
        "Be concise, technical, and actionable. Structure your response clearly."
    )

    user_prompt = f"""Analyze these logs and provide a root cause analysis (RCA):

=== LOGS ===
{log_content}
============

Respond in this exact format:

INCIDENT SUMMARY:
[2-3 sentence summary of what happened]

ROOT CAUSE:
[The most likely root cause]

IMPACT:
[What was affected and for how long]

RECOMMENDED FIX:
[Step by step remediation actions]

PREVENTION:
[How to prevent this in future]
"""
    return system_prompt, user_prompt


# --------------------------------------------------------------
# Step 4a -- Anthropic Claude
# --------------------------------------------------------------
def analyze_with_claude(log_content: str) -> dict:
    try:
        import anthropic
    except ImportError:
        sys.exit("Missing dependency. Run: pip install anthropic")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit("ANTHROPIC_API_KEY not set in .env\nGet a free key at https://console.anthropic.com")

    client = anthropic.Anthropic(api_key=api_key)
    system_prompt, user_prompt = build_prompts(log_content)

    print("Sending logs to Claude (Anthropic) for analysis ...\n")
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}]
    )

    return {
        "analysis": message.content[0].text,
        "tokens_used": message.usage.input_tokens + message.usage.output_tokens,
        "model": message.model,
    }


# --------------------------------------------------------------
# Step 4b -- Google Gemini
# --------------------------------------------------------------
def analyze_with_gemini(log_content: str) -> dict:
    try:
        import google.generativeai as genai
    except ImportError:
        sys.exit("Missing dependency. Run: pip install google-generativeai")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        sys.exit("GEMINI_API_KEY not set in .env\nGet a free key at https://aistudio.google.com")

    genai.configure(api_key=api_key)
    system_prompt, user_prompt = build_prompts(log_content)

    print("Sending logs to Gemini (Google) for analysis ...\n")
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_prompt
    )
    response = model.generate_content(user_prompt)

    return {
        "analysis": response.text,
        "tokens_used": "N/A",
        "model": "gemini-1.5-flash",
    }


# --------------------------------------------------------------
# Step 4c -- Groq (Llama 3)
# --------------------------------------------------------------
def analyze_with_groq(log_content: str) -> dict:
    try:
        from groq import Groq
    except ImportError:
        sys.exit("Missing dependency. Run: pip install groq")

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        sys.exit("GROQ_API_KEY not set in .env\nGet a free key at https://console.groq.com")

    client = Groq(api_key=api_key)
    system_prompt, user_prompt = build_prompts(log_content)

    print("Sending logs to Groq (Llama 3) for analysis ...\n")
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )

    return {
        "analysis": response.choices[0].message.content,
        "tokens_used": response.usage.total_tokens,
        "model": response.model,
    }


# --------------------------------------------------------------
# Step 4d -- Ollama (local, no API key needed)
# --------------------------------------------------------------
def analyze_with_ollama(log_content: str) -> dict:
    try:
        import urllib.request, json
    except ImportError:
        pass  # stdlib, always available

    system_prompt, user_prompt = build_prompts(log_content)
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3")

    print(f"Sending logs to local Ollama model '{ollama_model}' for analysis ...\n")

    payload = json.dumps({
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

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
    except Exception as e:
        sys.exit(f"Ollama request failed: {e}\nMake sure Ollama is running with: ollama serve")

    return {
        "analysis": result.get("response", "No response received from Ollama."),
        "tokens_used": result.get("eval_count", "N/A"),
        "model": ollama_model,
    }


# --------------------------------------------------------------
# Step 5 -- Route to the chosen provider
# --------------------------------------------------------------
def analyze_logs_with_ai(log_content: str) -> dict:
    providers = {
        "claude": analyze_with_claude,
        "gemini": analyze_with_gemini,
        "groq":   analyze_with_groq,
        "ollama": analyze_with_ollama,
    }

    if PROVIDER not in providers:
        sys.exit(
            f"Unknown provider '{PROVIDER}'.\n"
            f"Valid options are: {', '.join(providers.keys())}\n"
            f"Set it with LLM_PROVIDER=groq in your .env file."
        )

    return providers[PROVIDER](log_content)


# --------------------------------------------------------------
# Step 6 -- Write the RCA report to disk
# --------------------------------------------------------------
def save_report(analysis: str, output_path: str = "rca_report.txt"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""=============================================================
  Incident RCA Report
  Generated : {timestamp}
  Provider  : {PROVIDER.upper()}
=============================================================

{analysis}

=============================================================
  Generated by SRE AI Log Analyzer
=============================================================
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {output_path}")


# --------------------------------------------------------------
# Main
# --------------------------------------------------------------
def main():
    print("=" * 60)
    print("  SRE Log Analyzer -- Root Cause Analysis")
    print(f"  Provider : {PROVIDER.upper()}")
    print("=" * 60 + "\n")

    logs = read_logs(LOG_FILE)
    important_lines = extract_important_lines(logs)

    if not important_lines:
        print("No errors or warnings found. Logs look clean.")
        return

    print("Lines being sent for analysis:")
    print("-" * 40)
    print(important_lines)
    print("-" * 40 + "\n")

    result = analyze_logs_with_ai(important_lines)

    print("\n" + "=" * 60)
    print("  Root Cause Analysis")
    print("=" * 60)
    print(result["analysis"])
    print("=" * 60)
    print(f"\nTokens used : {result['tokens_used']}  |  Model : {result['model']}")

    save_report(result["analysis"], REPORT_FILE)


if __name__ == "__main__":
    main()