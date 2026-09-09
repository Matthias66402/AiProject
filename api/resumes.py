import os

from flask import Blueprint, current_app, jsonify, request, session
from groq import APIStatusError as GroqAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError

import db
from document_extraction import ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS
from services import resume_service
from services.ai_clients import openai_client
from services.assistant_service import DEFAULT_MODEL

resumes_api = Blueprint("resumes_api", __name__, url_prefix="/api/resumes")


def _serialize_resume(row):
    """Wie bei jobs/customers: Datumsfelder als ISO-String. Zusätzlich werden
    embedding (nur intern fürs Matching relevant) und content (voller
    HTML-Text, vom Frontend nicht benötigt - die Anzeige läuft über das
    eingebettete PDF) aus der Antwort entfernt."""
    row = dict(row)
    if row.get("created_at") is not None and hasattr(row["created_at"], "isoformat"):
        row["created_at"] = row["created_at"].isoformat()
    row.pop("embedding", None)
    row.pop("content", None)
    return row


@resumes_api.route("", methods=["GET"])
def list_resumes():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(error="Nicht angemeldet."), 401
    return jsonify(resumes=[_serialize_resume(r) for r in db.list_resumes_for_user(user_id)])


@resumes_api.route("/<int:resume_id>", methods=["GET"])
def get_resume(resume_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(error="Nicht angemeldet."), 401

    resume = db.get_resume(resume_id)
    if not resume or resume["user_id"] != user_id:
        return jsonify(error="Nicht gefunden."), 404

    matching_jobs = db.find_matching_jobs(resume["embedding"], top_k=5) if resume.get("embedding") else []
    return jsonify(resume=_serialize_resume(resume), matching_jobs=matching_jobs)


@resumes_api.route("", methods=["POST"])
def generate_resume():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(error="Nicht angemeldet."), 401

    data = request.get_json(silent=True) or {}
    spec = (data.get("spec") or "").strip()
    if not spec:
        return jsonify(error="Bitte beschreibe, was dein Lebenslauf enthalten soll."), 400

    try:
        resume_id = resume_service.generate_resume_document(openai_client, DEFAULT_MODEL, user_id, spec, current_app.logger)
    except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
        current_app.logger.warning("API error %s: %s", e.status_code, e.body)
        return jsonify(error="Der Lebenslauf konnte gerade nicht erstellt werden. Bitte später erneut versuchen."), 502

    return jsonify(resume=_serialize_resume(db.get_resume(resume_id))), 201


@resumes_api.route("/upload", methods=["POST"])
def upload_resume():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(error="Nicht angemeldet."), 401

    uploaded_file = request.files.get("resume_file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify(error="Keine Datei ausgewählt."), 400

    ext = os.path.splitext(uploaded_file.filename)[1].lower()
    if ext not in ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS:
        return jsonify(error="Bitte eine Datei im PDF-, Word- (.docx) oder LibreOffice-Format (.odt) hochladen."), 400

    try:
        resume_id = resume_service.create_resume_from_upload(openai_client, user_id, uploaded_file, current_app.logger)
    except Exception as e:
        current_app.logger.warning("Fehler beim Auslesen des hochgeladenen Lebenslaufs: %s", e)
        return jsonify(error="Die Datei konnte nicht gelesen werden. Bitte Format und Inhalt prüfen."), 400

    if resume_id is None:
        return jsonify(error="In der Datei konnte kein Text gefunden werden. Bitte eine Datei mit auslesbarem Text hochladen."), 400

    return jsonify(resume=_serialize_resume(db.get_resume(resume_id))), 201


@resumes_api.route("/<int:resume_id>", methods=["DELETE"])
def delete_resume(resume_id):
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(error="Nicht angemeldet."), 401

    resume = db.get_resume(resume_id)
    if not resume or resume["user_id"] != user_id:
        return jsonify(error="Nicht gefunden."), 404

    if resume["document_link"]:
        file_path = os.path.join(resume_service.RESUME_DIR, os.path.basename(resume["document_link"]))
        if os.path.exists(file_path):
            os.remove(file_path)
    db.delete_resume(resume_id)
    return jsonify(success=True)
