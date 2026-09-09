from flask import Blueprint, current_app, jsonify, request

from services.assistant_service import AVAILABLE_MODELS, DEFAULT_MODEL, ask_assistant

assistant_api = Blueprint("assistant_api", __name__, url_prefix="/api/assistant")


@assistant_api.route("", methods=["GET"])
def get_assistant_info():
    return jsonify(models=AVAILABLE_MODELS, default_model=DEFAULT_MODEL)


@assistant_api.route("/ask", methods=["POST"])
def ask():
    # Lazy import: build_site_map() gehört inhaltlich zu den in app.py registrierten
    # Routen und braucht app.url_map - ein Import auf Modulebene würde einen
    # Zirkelbezug erzeugen, da app.py dieses Blueprint beim Start importiert.
    from app import build_site_map

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(error="Bitte eine Frage eingeben."), 400

    answer, resolved_model = ask_assistant(question, data.get("model"), build_site_map(), current_app.logger)
    return jsonify(answer=answer, model=resolved_model)
