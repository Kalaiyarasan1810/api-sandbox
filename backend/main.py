from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import uuid

app = Flask(__name__)
CORS(app)

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox")

@app.route("/run", methods=["POST"])
def run_code():
    data = request.get_json()

    if not data or "code" not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data["code"]

    # 1. Save code to a temp file
    file_id   = str(uuid.uuid4())[:8]
    file_name = f"{file_id}.py"
    file_path = os.path.join(SANDBOX_DIR, file_name)

    with open(file_path, "w") as f:
        f.write(code)

    # 2. Run inside Docker container (isolated!)
    try:
        result = subprocess.run(
            [
                "docker", "run",
                "--rm",                          # auto-remove container after run
                "--network", "none",             # no internet access
                "--memory", "128m",              # max 128MB RAM
                "--cpus", "0.5",                 # max 50% of one CPU core
                "-v", f"{os.path.abspath(SANDBOX_DIR)}:/code",  # mount sandbox folder
                "sandbox-runner",                # our image
                "python", f"/code/{file_name}"  # run the user's file
            ],
            capture_output=True,
            text=True,
            timeout=15
        )
        output = result.stdout or result.stderr or "(no output)"

    except subprocess.TimeoutExpired:
        output = "❌ Error: Code took too long to run (15s limit)"

    except Exception as e:
        output = f"❌ Error: {str(e)}"

    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

    return jsonify({
        "output": output,
        "security": "⏳ Security scan coming in Phase 4!"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)