from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import uuid
import re

app = Flask(__name__)
CORS(app)

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox")


# ── API Key Patterns ──────────────────────────────────────────────────────────

API_KEY_PATTERNS = {
    "OpenAI API key":    r"sk-[a-zA-Z0-9]{32,}",
    "AWS access key":    r"AKIA[0-9A-Z]{16}",
    "AWS secret key":    r"(?i)aws.{0,20}secret.{0,20}['\"][0-9a-zA-Z/+]{40}['\"]",
    "GitHub token":      r"ghp_[a-zA-Z0-9]{36}",
    "Google API key":    r"AIza[0-9A-Za-z\-_]{35}",
    "Stripe secret key": r"sk_live_[0-9a-zA-Z]{24,}",
    "Slack token":       r"xox[baprs]-[0-9a-zA-Z\-]{10,}",
    "Generic secret":    r"(?i)(api_key|apikey|secret_key|access_token)\s*=\s*['\"][a-zA-Z0-9_\-]{16,}['\"]",
}

PLACEHOLDER_WORDS = {"your", "example", "placeholder", "here", "test", "dummy", "sample", "xxx"}


def scan_api_keys(code: str) -> dict:
    """Scan code for hardcoded API keys / secrets using regex patterns."""
    findings = []
    for name, pattern in API_KEY_PATTERNS.items():
        matches = re.findall(pattern, code)
        # Filter obvious placeholders from the Generic secret rule
        if name == "Generic secret":
            matches = [
                m for m in matches
                if not any(word in m.lower() for word in PLACEHOLDER_WORDS)
            ]
        if matches:
            findings.append({
                "type":     name,
                "count":    len(matches),
                "severity": "HIGH",
            })
    return {
        "found":  len(findings) > 0,
        "issues": findings,
    }


# ── Bandit Scanner ────────────────────────────────────────────────────────────

def scan_code(file_path: str) -> str:
    """Run Bandit security scan on the given file."""
    try:
        result = subprocess.run(
            [
                "bandit",
                "-r",        # recursive (works on single files too)
                "-f", "txt", # human-readable output
                "-ll",       # only medium and high severity issues
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=30
        )

        output = result.stdout.strip()

        if "No issues identified" in output:
            return "✅ No security issues found!"

        if output:
            return output

        if result.stderr:
            return f"Scanner error: {result.stderr}"

        return "✅ No security issues found!"

    except subprocess.TimeoutExpired:
        return "❌ Security scan timed out"
    except Exception as e:
        return f"❌ Scanner error: {str(e)}"


# ── /run endpoint ─────────────────────────────────────────────────────────────

@app.route("/run", methods=["POST"])
def run_code():
    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data["code"]

    # ── Stage 1: API key scan (runs on raw string, no file needed) ────────────
    key_scan = scan_api_keys(code)
    if key_scan["found"]:
        issues = key_scan["issues"]
        lines  = [f"  [HIGH] {i['type']} — {i['count']} occurrence(s)" for i in issues]
        report = "\n".join(lines)
        return jsonify({
            "output":         "",
            "security":       f"🔑 BLOCKED — Hardcoded API keys detected:\n{report}\n\nRemove secrets before running.",
            "api_key_issues": issues,
            "blocked":        True,
        })

    # ── Stage 2: Save to temp file + Bandit scan ──────────────────────────────
    file_id   = str(uuid.uuid4())[:8]
    file_name = f"{file_id}.py"
    file_path = os.path.join(SANDBOX_DIR, file_name)

    with open(file_path, "w") as f:
        f.write(code)

    # Security scan FIRST (before running!)
    security_result = scan_code(file_path)

    # ── Stage 3: Run inside Docker (with fallback for Render free tier) ───────
    try:
        result = subprocess.run(
            [
                "docker", "run",
                "--rm",                         # auto-remove container after run
                "--network", "none",            # no internet access
                "--memory", "128m",             # max 128MB RAM
                "--cpus", "0.5",                # max 50% of one CPU core
                "--pids-limit", "50",           # prevent fork bombs
                "-v", f"{os.path.abspath(SANDBOX_DIR)}:/code:ro",  # read-only mount
                "sandbox-runner",
                "python", f"/code/{file_name}"
            ],
            capture_output=True,
            text=True,
            timeout=60
        )
        output = result.stdout or result.stderr or "(no output)"

    except FileNotFoundError:
        # Docker not installed on this server (e.g. Render free tier)
        # Fall back to direct execution with a short timeout
        try:
            fallback = subprocess.run(
                ["python", file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
            output = (fallback.stdout or fallback.stderr or "(no output)") + \
                     "\n\n⚠️ Note: running without Docker sandbox (Render free tier)"
        except Exception as fallback_err:
            output = f"❌ Fallback execution error: {str(fallback_err)}"

    except subprocess.TimeoutExpired:
        output = "❌ Code took too long to run (60s limit)"

    except Exception as e:
        output = f"❌ Error: {str(e)}"

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify({
        "output":         output,
        "security":       security_result,
        "api_key_issues": [],
        "blocked":        False,
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))   # use Render's PORT or default to 5000
    app.run(debug=False, host="0.0.0.0", port=port)