from flask import Flask, request, jsonify
from flask_cors import CORS
import subprocess
import os
import uuid

app = Flask(__name__)
CORS(app)  # Allows frontend to talk to backend

SANDBOX_DIR = os.path.join(os.path.dirname(__file__), "sandbox")

@app.route("/run", methods=["POST"])
def run_code():
    data = request.get_json()

    # 1. Validate input
    if not data or "code" not in data:
        return jsonify({"error": "No code provided"}), 400

    code = data["code"]

    # 2. Save code to a temp file with a unique name
    file_id   = str(uuid.uuid4())[:8]        # e.g. "a3f9bc12"
    file_path = os.path.join(SANDBOX_DIR, f"{file_id}.py")

    with open(file_path, "w") as f:
        f.write(code)

    # 3. Run the code in a subprocess (isolated from main process)
    try:
        result = subprocess.run(
            ["python", file_path],
            capture_output=True,    # grab stdout and stderr
            text=True,              # return strings not bytes
            timeout=10              # kill if it runs longer than 10 seconds
        )
        output = result.stdout or result.stderr or "(no output)"

    except subprocess.TimeoutExpired:
        output = "❌ Error: Code took too long to run (10s limit)"

    except Exception as e:
        output = f"❌ Error: {str(e)}"

    finally:
        # 4. Always clean up the temp file
        if os.path.exists(file_path):
            os.remove(file_path)

    # 5. Return result
    return jsonify({
        "output":   output,
        "security": "⏳ Security scan coming in Phase 4!"
    })


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)