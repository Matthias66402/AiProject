from flask import Blueprint, jsonify, request, session
from werkzeug.security import generate_password_hash

import db
from db import DEFAULT_ROLE, ROLES
from services.permissions import user_read_permission

users_api = Blueprint("users_api", __name__, url_prefix="/api/users")

_DATE_FIELDS = ("created_at", "updated_at")


def _serialize_dates(row):
    for field in _DATE_FIELDS:
        value = row.get(field)
        if value is not None and hasattr(value, "isoformat"):
            row[field] = value.isoformat()
    return row


def _serialize_user(row):
    """Wie _serialize_dates, entfernt zusätzlich den Passwort-Hash - der darf
    die API nie verlassen, auch nicht gehasht."""
    row = _serialize_dates(dict(row))
    row.pop("password_hash", None)
    return row


def _is_admin():
    return session.get("user_role") == "admin"


@users_api.route("", methods=["GET"])
def list_users():
    """Alle Nutzer auflisten (Admins und 'customer'-Nutzer).
    ---
    tags:
      - Users
    security:
      - sessionAuth: []
    responses:
      200:
        description: Nutzerliste (ohne Passwort-Hash) plus verfügbare Rollen und Stellenanbieter.
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if not user_read_permission():
        return jsonify(error="Nicht berechtigt - Bitte kontaktieren Sie uns für weitere Informationen."), 403
    return jsonify(
        users=[_serialize_user(u) for u in db.list_users()],
        roles=ROLES,
        customers=[_serialize_dates(dict(c)) for c in db.list_customers()],
    )


@users_api.route("", methods=["POST"])
def create_user():
    """Neuen Nutzer anlegen, inkl. Rollenvergabe (nur Admins).
    ---
    tags:
      - Users
    security:
      - sessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [first_name, last_name, short_name, email, password]
          properties:
            first_name: {type: string}
            last_name: {type: string}
            short_name: {type: string}
            email: {type: string, format: email}
            password: {type: string, format: password}
            role: {type: string, description: "Eine der verfügbaren Rollen, siehe GET /api/users."}
            zip: {type: string}
            city: {type: string}
            customer_id: {type: integer, description: "Nur bei role='customer' berücksichtigt."}
    responses:
      201:
        description: Nutzer wurde angelegt.
        schema:
          $ref: '#/definitions/SuccessResponse'
      400:
        description: Pflichtfeld fehlt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if not _is_admin():
        return jsonify(error="Nicht berechtigt - Bitte kontaktieren Sie uns für weitere Informationen."), 403

    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    short_name = (data.get("short_name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") or DEFAULT_ROLE
    if role not in ROLES:
        role = DEFAULT_ROLE
    zip_code = (data.get("zip") or "").strip() or None
    city = (data.get("city") or "").strip() or None
    customer_id = data.get("customer_id") or None
    if role != "customer":
        customer_id = None

    if not (first_name and last_name and short_name and email and password):
        return jsonify(error="Bitte alle Pflichtfelder ausfüllen."), 400

    db.create_user(first_name, last_name, short_name, email, generate_password_hash(password), role, zip_code, city, customer_id)
    return jsonify(success=True), 201


@users_api.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Einen Nutzer ansehen, inkl. dessen Lebensläufen (Admins und 'customer'-Nutzer).
    ---
    tags:
      - Users
    security:
      - sessionAuth: []
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Nutzer (ohne Passwort-Hash) plus dessen Lebensläufe.
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      404:
        description: Nicht gefunden.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if not user_read_permission():
        return jsonify(error="Nicht berechtigt - Bitte kontaktieren Sie uns für weitere Informationen."), 403

    user = db.get_user(user_id)
    if not user:
        return jsonify(error="Nicht gefunden."), 404

    return jsonify(
        user=_serialize_user(user),
        resumes=[_serialize_dates(dict(r)) for r in db.list_resumes_for_user(user_id)],
    )


@users_api.route("/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    """Nutzer bearbeiten, inkl. Rollenvergabe (nur Admins).
    ---
    tags:
      - Users
    security:
      - sessionAuth: []
    parameters:
      - name: user_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [first_name, last_name, short_name, email]
          properties:
            first_name: {type: string}
            last_name: {type: string}
            short_name: {type: string}
            email: {type: string, format: email}
            password: {type: string, format: password, description: "Optional - nur bei Änderung angeben."}
            role: {type: string}
            zip: {type: string}
            city: {type: string}
            customer_id: {type: integer, description: "Nur bei role='customer' berücksichtigt."}
    responses:
      200:
        description: Nutzer wurde aktualisiert.
        schema:
          $ref: '#/definitions/SuccessResponse'
      400:
        description: Pflichtfeld fehlt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    if not _is_admin():
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    last_name = (data.get("last_name") or "").strip()
    short_name = (data.get("short_name") or "").strip()
    email = (data.get("email") or "").strip()
    password = data.get("password") or ""
    role = data.get("role") or DEFAULT_ROLE
    if role not in ROLES:
        role = DEFAULT_ROLE
    password_hash = generate_password_hash(password) if password else None
    zip_code = (data.get("zip") or "").strip() or None
    city = (data.get("city") or "").strip() or None
    customer_id = data.get("customer_id") or None
    if role != "customer":
        customer_id = None

    if not (first_name and last_name and short_name and email):
        return jsonify(error="Bitte alle Pflichtfelder ausfüllen."), 400

    db.update_user(user_id, first_name, last_name, short_name, email, role, password_hash, zip_code, city, customer_id)
    return jsonify(success=True)
