from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import uuid

app = Flask(__name__)
CORS(app)

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox")


def scan_code(file_path):
    """Run Bandit security scan on the given file."""
    try:
        result = subprocess.run(
            [
                "bandit",
                "-r",           # recursive (works on single files too)
                "-f", "txt",    # human-readable output
                "-ll",          # only medium and high severity issues
                file_path
            ],
            capture_output=True,
            text=True,
            timeout=30          # increased from 15 to 30
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


@app.route("/run", methods=["POST"])
def run_code():
    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data["code"]

    # 1. Save code to temp file
    file_id   = str(uuid.uuid4())[:8]
    file_name = f"{file_id}.py"
    file_path = os.path.join(SANDBOX_DIR, file_name)

    with open(file_path, "w") as f:
        f.write(code)

    # 2. Security scan FIRST (before running!)
    security_result = scan_code(file_path)

    # 3. Run inside Docker
    try:
        result = subprocess.run(
            [
                "docker", "run",
                "--rm",                          # auto-remove container after run
                "--network", "none",             # no internet access
                "--memory", "128m",              # max 128MB RAM
                "--cpus", "0.5",                 # max 50% of one CPU core
                "--pids-limit", "50",            # NEW: prevent fork bombs
                "-v", f"{os.path.abspath(SANDBOX_DIR)}:/code:ro",  # NEW: read-only mount
                "sandbox-runner",
                "python", f"/code/{file_name}"
            ],
            capture_output=True,
            text=True,
            timeout=60          # increased from 15 to 60
        )
        output = result.stdout or result.stderr or "(no output)"

    except subprocess.TimeoutExpired:
        output = "❌ Code took too long to run (60s limit)"
    except Exception as e:
        output = f"❌ Error: {str(e)}"
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify({
        "output":   output,
        "security": security_result
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)