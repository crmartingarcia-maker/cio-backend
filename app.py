import os
import re

from flask import Flask, request, jsonify
from flask_cors import CORS
from customerio import analytics

# Settings come from the host's environment, never from this file.
analytics.write_key = os.environ["CIO_WRITE_KEY"]
analytics.host = os.environ.get("CIO_HOST", "https://cdp-eu.customer.io")
ALLOWED_ORIGIN = os.environ.get("ALLOWED_ORIGIN", "https://crmartingarcia-maker.github.io")

# Only these event names are accepted from the website.
ALLOWED_EVENTS = {"form_submitted", "button_clicked"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024  # reject requests bigger than 10 KB

# Browsers may call these two addresses only from the allowed website.
CORS(app, resources={
    r"/identify": {"origins": ALLOWED_ORIGIN},
    r"/track": {"origins": ALLOWED_ORIGIN},
})

USER_ID_RULE = re.compile(r"^web-[A-Za-z0-9_-]{1,60}$")
KEY_RULE = re.compile(r"^[A-Za-z0-9_]{1,40}$")


def clean_values(values):
    """Keep at most 10 simple values (text up to 200 characters, numbers, true/false)."""
    if not isinstance(values, dict) or len(values) > 10:
        return None
    cleaned = {}
    for key, value in values.items():
        if not KEY_RULE.match(str(key)):
            return None
        if isinstance(value, str):
            value = value[:200]
        elif not isinstance(value, (int, float, bool)):
            return None
        cleaned[key] = value
    return cleaned


@app.route("/")
def home():
    return jsonify({"status": "backend is running"})


@app.route("/identify", methods=["POST"])
def receive_identify():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", ""))
    traits = clean_values(data.get("traits", {}))
    if not USER_ID_RULE.match(user_id):
        return jsonify({"error": "user_id must start with web- and use letters, numbers, _ or -"}), 400
    if traits is None:
        return jsonify({"error": "traits must be a small set of simple values"}), 400
    analytics.identify(user_id, traits)
    analytics.flush()
    return jsonify({"status": "identify sent", "user_id": user_id})


@app.route("/track", methods=["POST"])
def receive_track():
    data = request.get_json(silent=True) or {}
    user_id = str(data.get("user_id", ""))
    event = data.get("event")
    properties = clean_values(data.get("properties", {}))
    if not USER_ID_RULE.match(user_id):
        return jsonify({"error": "user_id must start with web- and use letters, numbers, _ or -"}), 400
    if event not in ALLOWED_EVENTS:
        return jsonify({"error": "event must be one of: " + ", ".join(sorted(ALLOWED_EVENTS))}), 400
    if properties is None:
        return jsonify({"error": "properties must be a small set of simple values"}), 400
    analytics.track(user_id, event, properties)
    analytics.flush()
    return jsonify({"status": "event sent", "user_id": user_id, "event": event})
