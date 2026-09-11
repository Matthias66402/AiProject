from flask import Blueprint, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

import db
from db import DEFAULT_ROLE
from services.auth_service import log_in_user

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/auth")


def _session_user():
    return {
        "id": session.get("user_id"),
        "short_name": session.get("user_short_name"),
        "role": session.get("user_role"),
        "customer_id": session.get("user_customer_id"),
    }


@auth_api.route("/me", methods=["GET"])
def me():
    """Aktueller Login-Status für React - Pendant zu inject_current_user() (app.py),
    das die klassischen Jinja-Templates versorgt. Liest dieselbe Flask-Session, damit
    ein über die bestehende /login-Seite angemeldeter Nutzer auch im React-Frontend
    (anderer Port, gleiche Site) erkannt wird.
    ---
    tags:
      - Auth
    security:
      - sessionAuth: []
    responses:
      200:
        description: Login-Status. user ist null, wenn niemand angemeldet ist.
        schema:
          type: object
          properties:
            user:
              type: object
              nullable: true
              properties:
                id: {type: integer}
                short_name: {type: string}
                role: {type: string}
                customer_id: {type: integer, nullable: true}
    """
    if not session.get("user_id"):
        return jsonify(user=None)
    return jsonify(user=_session_user())


@auth_api.route("/login", methods=["POST"])
def login():
    """Mit E-Mail und Passwort anmelden.
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [email, password]
          properties:
            email: {type: string, format: email}
            password: {type: string, format: password}
    responses:
      200:
        description: Anmeldung erfolgreich, setzt das Session-Cookie.
      401:
        description: E-Mail oder Passwort ist falsch.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""

    user = db.get_user_by_email(email)
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="E-Mail oder Passwort ist falsch."), 401

    log_in_user(user)
    return jsonify(user=_session_user())


@auth_api.route("/register", methods=["POST"])
def register():
    """Neuen Nutzer registrieren und direkt anmelden (immer Rolle 'user').
    ---
    tags:
      - Auth
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [first_name, last_name, short_name, email, zip, city, password, password_confirm]
          properties:
            first_name: {type: string}
            last_name: {type: string}
            short_name: {type: string}
            email: {type: string, format: email}
            zip: {type: string}
            city: {type: string}
            password: {type: string, format: password}
            password_confirm: {type: string, format: password}
    responses:
      201:
        description: Registrierung erfolgreich, setzt das Session-Cookie.
      400:
        description: Pflichtfeld fehlt, Passwörter stimmen nicht überein oder E-Mail bereits vergeben.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    short_name = (data.get("short_name") or "").strip()
    email = (data.get("email") or "").strip()
    zip_code = (data.get("zip") or "").strip()
    city = (data.get("city") or "").strip()
    password = data.get("password") or ""
    password_confirm = data.get("password_confirm") or ""

    if not (first_name and last_name and short_name and email and zip_code and city and password):
        return jsonify(error="Bitte alle Felder ausfüllen."), 400
    if password != password_confirm:
        return jsonify(error="Die Passwörter stimmen nicht überein."), 400
    if db.get_user_by_email(email):
        return jsonify(error="Diese E-Mail-Adresse ist bereits registriert."), 400

    db.create_user(first_name, last_name, short_name, email, generate_password_hash(password), DEFAULT_ROLE, zip_code, city)
    log_in_user(db.get_user_by_email(email))
    return jsonify(user=_session_user()), 201


@auth_api.route("/logout", methods=["POST"])
def logout():
    """Abmelden (leert die Session).
    ---
    tags:
      - Auth
    security:
      - sessionAuth: []
    responses:
      200:
        description: Abmeldung erfolgreich.
        schema:
          $ref: '#/definitions/SuccessResponse'
    """
    session.clear()
    return jsonify(success=True)
