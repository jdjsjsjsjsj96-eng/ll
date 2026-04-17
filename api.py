from flask import Flask, request, jsonify
import json, os, threading, time, secrets

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", secrets.token_hex(32))

@app.after_request
def add_cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Admin-Password"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

DATA_FILE = "minion_data.json"
API_SECRET = os.environ.get("API_SECRET", "minion_secret")
DASHBOARD_PASSWORD = os.environ.get("DASHBOARD_PASSWORD", "minion_admin")

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "bans": {},
        "kicks": {},
        "warnings": {},
        "nicknames": {},
    }

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

@app.route("/")
def health():
    return "OK", 200

@app.route("/data", methods=["GET"])
def get_data():
    secret = request.headers.get("X-Admin-Password", "")
    if secret != DASHBOARD_PASSWORD:
        return jsonify({"error": "Unauthorized"}), 403
    return jsonify(load_data()), 200

def start_api_thread():
    port = int(os.environ.get("PORT", 8080))
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False),
        daemon=True
    ).start()
