import json

from flask import Blueprint, current_app, jsonify, request, session
from groq import APIStatusError as GroqAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError

import db
from services import joboffer_service, resume_service
from services.ai_clients import openai_client
from services.assistant_service import DEFAULT_MODEL

tools_api = Blueprint("tools_api", __name__, url_prefix="/api/tools")


def _is_admin():
    return session.get("user_role") == "admin"


@tools_api.route("/resume", methods=["POST"])
def generate_resume():
    """Lebenslauf für einen beliebigen, per user_id gewählten Nutzer generieren (nur Admins).
    ---
    tags:
      - Tools
    security:
      - sessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [spec, user_id]
          properties:
            spec:
              type: string
              description: Freitext, was der Lebenslauf enthalten soll.
            user_id:
              type: integer
    responses:
      200:
        description: Lebenslauf wurde erstellt und dem Nutzer zugeordnet.
        schema:
          type: object
          properties:
            file_url: {type: string}
      400:
        description: spec oder user_id fehlt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      502:
        description: KI-Anfrage fehlgeschlagen, bitte später erneut versuchen.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if not _is_admin():
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    spec = (data.get("spec") or "").strip()
    user_id = data.get("user_id")
    if not spec or not user_id:
        return jsonify(error="Bitte zuerst einen Nutzer wählen und beschreiben, was der Lebenslauf enthalten soll."), 400

    try:
        resume_id = resume_service.generate_resume_document(openai_client, DEFAULT_MODEL, int(user_id), spec, current_app.logger)
    except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
        current_app.logger.warning("API error %s: %s", e.status_code, e.body)
        return jsonify(error="Der Lebenslauf konnte gerade nicht erstellt werden. Bitte später erneut versuchen."), 502

    return jsonify(file_url=db.get_resume(resume_id)["document_link"])


@tools_api.route("/joboffer", methods=["POST"])
def generate_joboffer():
    """Stellenangebot für einen per customer_id gewählten Stellenanbieter generieren
    (legt dabei automatisch auch eine Stelle unter /api/jobs an). Nur Admins.
    ---
    tags:
      - Tools
    security:
      - sessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [spec, customer_id]
          properties:
            spec:
              type: string
              description: Freitext, was das Stellenangebot enthalten soll.
            customer_id:
              type: integer
    responses:
      200:
        description: Stellenangebot wurde erstellt und als Stelle angelegt.
        schema:
          type: object
          properties:
            file_url: {type: string}
      400:
        description: spec oder customer_id fehlt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      502:
        description: KI-Anfrage fehlgeschlagen, bitte später erneut versuchen.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if not _is_admin():
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    spec = (data.get("spec") or "").strip()
    customer_id = data.get("customer_id")
    if not spec or not customer_id:
        return jsonify(error="Bitte zuerst einen Stellenanbieter wählen und beschreiben, was das Stellenangebot enthalten soll."), 400

    try:
        file_url = joboffer_service.generate_joboffer(openai_client, DEFAULT_MODEL, int(customer_id), spec, current_app.logger)
    except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
        current_app.logger.warning("API error %s: %s", e.status_code, e.body)
        return jsonify(error="Das Stellenangebot konnte gerade nicht erstellt werden. Bitte später erneut versuchen."), 502
    except (json.JSONDecodeError, ValueError) as e:
        current_app.logger.warning("Unerwartetes KI-Antwortformat: %s", e)
        return jsonify(error="Das Stellenangebot konnte gerade nicht erstellt werden. Bitte später erneut versuchen."), 502

    return jsonify(file_url=file_url)
