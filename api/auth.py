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
    (anderer Port, gleiche Site) erkannt wird."""
    if not session.get("user_id"):
        return jsonify(user=None)
    return jsonify(user=_session_user())


@auth_api.route("/login", methods=["POST"])
def login():
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
    session.clear()
    return jsonify(success=True)
