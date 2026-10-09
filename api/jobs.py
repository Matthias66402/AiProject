from flask import Blueprint, current_app, jsonify, request, session

import db
from services.ai_clients import openai_client
from services.match_profile_service import job_profile_input, profile_and_embed
from services.permissions import job_management_permission, own_customer_for_session

jobs_api = Blueprint("jobs_api", __name__, url_prefix="/api/jobs")

JOBS_PER_PAGE_DEFAULT = 10
JOBS_PER_PAGE_OPTIONS = [10, 25, 50, 100]

# Auswahl 'Entfernung' der Stellensuche (Rolle 'user'): Wert -> maximale
# Luftlinie in km um die eigene PLZ. 'relocate' (umzugsbereit) bzw. ein
# fehlender/unbekannter Wert filtert nicht. Muss zu DISTANCE_OPTIONS in
# frontend/src/config.js passen.
DISTANCE_KM = {"near": 10, "25": 25, "50": 50, "100": 100}

_DATE_FIELDS = ("created_at", "updated_at", "valid_from", "valid_until")


def _serialize_dates(row):
    """Flasks jsonify() serialisiert date/datetime als RFC-1123-String (z.B. "Fri, 04
    Sep 2026 00:00:00 GMT") statt ISO-Format - unbrauchbar für <input type="date">
    im Frontend. Wandelt die bekannten Datumsfelder vorher explizit in ISO-Strings um."""
    for field in _DATE_FIELDS:
        value = row.get(field)
        if value is not None and hasattr(value, "isoformat"):
            row[field] = value.isoformat()
    return row


def _serialize_job(row):
    """Wie _serialize_dates, entfernt zusätzlich embedding und match_profile (nur
    intern fürs Matching relevant, 1536 Zahlen pro Stelle - bläht die Antwort sonst auf)."""
    row = _serialize_dates(row)
    row.pop("embedding", None)
    row.pop("match_profile", None)
    return row


def _paginate(customer_id=None, search=None, matching_user_id=None, with_candidates=False,
              origin_zip=None, max_distance_km=None):
    per_page = request.args.get("per_page", type=int)
    # Jeder Wert bis zur größten Option ist erlaubt (z. B. SIDE_PANEL_PER_PAGE aus
    # frontend/src/config.js), die Optionen sind nur die Auswahl im Pager.
    if per_page is None or not 1 <= per_page <= max(JOBS_PER_PAGE_OPTIONS):
        per_page = JOBS_PER_PAGE_DEFAULT
    total = db.count_jobs(customer_id, search=search, matching_user_id=matching_user_id,
                          with_candidates=with_candidates, origin_zip=origin_zip, max_distance_km=max_distance_km)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(request.args.get("page", type=int) or 1, 1)
    page = min(page, total_pages)
    jobs_list = db.list_jobs(customer_id, limit=per_page, offset=(page - 1) * per_page, search=search,
                             matching_user_id=matching_user_id, with_candidates=with_candidates,
                             origin_zip=origin_zip, max_distance_km=max_distance_km)
    return jobs_list, page, per_page, total_pages, total


@jobs_api.route("", methods=["GET"])
def list_jobs():
    """Liste + Pagination - Pendant zu jobs()/GET (app.py). customer_id filtert wie
    beim "von dieser Stelle aus zum Kunden zurück"-Flow der klassischen Seite. search
    filtert (nur für die React-Liste, siehe JobsPage.jsx) auf die Position.
    ---
    tags:
      - Jobs
    parameters:
      - name: page
        in: query
        type: integer
      - name: per_page
        in: query
        type: integer
        enum: [10, 25, 50, 100]
      - name: customer_id
        in: query
        type: integer
        description: Nur Stellen dieses Stellenanbieters.
      - name: search
        in: query
        type: string
        description: Freitextsuche auf die Position.
      - name: matching
        in: query
        type: integer
        enum: [0, 1]
        description: Nur für Rolle user - 1 = nur Stellen, zu denen ein eigener Lebenslauf passt (ab Schwellwert).
      - name: with_candidates
        in: query
        type: integer
        enum: [0, 1]
        description: Nur für Rollen admin und customer - 1 = nur Stellen mit mindestens einem passenden Stellensuchenden (ab Schwellwert); bei customer zusammen mit customer_id für die eigenen Stellen.
      - name: distance
        in: query
        type: string
        enum: [near, "25", "50", "100", relocate]
        description: Nur für Rolle user mit hinterlegter PLZ - maximale Luftlinie um die eigene PLZ (near = Wohnortnähe, bis 10 km); relocate (umzugsbereit) filtert nicht. Stellen ohne bzw. mit unbekannter PLZ bleiben in der Liste.
    responses:
      200:
        description: Stellenangebote der aktuellen Seite plus Pagination-Metadaten; für Rolle user je Stelle my_match (beste Ähnlichkeit eines eigenen Lebenslaufs ab Schwellwert, sonst null) sowie origin_zip (eigene PLZ als Ausgangspunkt der Entfernungsauswahl, null wenn keine hinterlegt), für Rolle customer bei eigenen Stellen und für Admins bei allen Stellen match_count (Anzahl passender Stellensuchender).
    """
    customer_id = request.args.get("customer_id", type=int)
    search = (request.args.get("search") or "").strip()
    matching_user_id = None
    if request.args.get("matching") == "1" and session.get("user_role") == "user":
        matching_user_id = session.get("user_id")
    with_candidates = (request.args.get("with_candidates") == "1"
                       and session.get("user_role") in ("admin", "customer"))
    origin_zip = max_distance_km = None
    if session.get("user_role") == "user" and session.get("user_id"):
        origin_zip = (db.get_user(session["user_id"]) or {}).get("zip")
        max_distance_km = DISTANCE_KM.get(request.args.get("distance"))
    jobs_list, page, per_page, total_pages, total = _paginate(customer_id, search, matching_user_id, with_candidates,
                                                              origin_zip, max_distance_km)
    permission = job_management_permission()
    own_customer = own_customer_for_session()
    jobs_out = [_serialize_job(dict(job)) for job in jobs_list]
    # Rolle 'user': Stellen markieren, zu denen ein eigener Lebenslauf passt
    # (my_match = beste Ähnlichkeit, sonst None).
    if session.get("user_role") == "user" and session.get("user_id"):
        matches = db.user_match_similarities(session["user_id"], [job["id"] for job in jobs_out])
        for job in jobs_out:
            job["my_match"] = matches.get(job["id"])
    # Rolle 'customer': bei den eigenen Stellen die Anzahl passender
    # Stellensuchender (match_count, fremde Stellen bleiben ohne); Admins bei
    # allen Stellen.
    elif (session.get("user_role") == "customer" and isinstance(permission, int)) or permission == "admin":
        counted_ids = [job["id"] for job in jobs_out
                       if permission == "admin" or job["customer_id"] == permission]
        counts = db.job_match_counts(counted_ids)
        for job in jobs_out:
            if job["id"] in counted_ids:
                job["match_count"] = counts.get(job["id"], 0)
    return jsonify(
        jobs=jobs_out,
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        total=total,
        per_page_options=JOBS_PER_PAGE_OPTIONS,
        customers=[_serialize_dates(dict(c)) for c in db.list_customers()],
        own_customer=_serialize_dates(dict(own_customer)) if own_customer else None,
        can_create=bool(permission),
        origin_zip=origin_zip,
    )


@jobs_api.route("/stats", methods=["GET"])
def job_stats():
    """Kennzahlen für die Zahlenkacheln der Stellenangebote-Liste - eigener Endpoint,
    damit das Match-Zählen nicht bei jeder Suche/jedem Seitenwechsel mitläuft.
    Matches für Admins (alle Stellen), 'customer'-Nutzer (nur eigene Stellen, analog
    zu den passenden Kandidaten auf der Stellen-Detailseite) und 'user'-Nutzer (nur
    die eigenen Lebensläufe, analog zu 'Passt zu dir' in der Liste).
    ---
    tags:
      - Jobs
    responses:
      200:
        description: Kennzahlen.
        schema:
          type: object
          properties:
            active_jobs: {type: integer, description: "Heute gültige Stellen."}
            customers: {type: integer, description: "Stellenanbieter."}
            matches: {type: integer, x-nullable: true, description: "Paare aus gültiger Stelle und Person ab min_similarity; null ohne Berechtigung."}
            matches_scope: {type: string, enum: [all, own, mine], x-nullable: true, description: "all = alle Stellen, own = eigene Stellen (customer), mine = eigene Lebensläufe (user)."}
            min_similarity: {type: number}
    """
    permission = job_management_permission()
    if permission == "admin":
        matches, matches_scope = db.count_active_matches(), "all"
    elif permission:
        matches, matches_scope = db.count_active_matches(customer_id=permission), "own"
    elif session.get("user_role") == "user" and session.get("user_id"):
        matches, matches_scope = db.count_active_matches(user_id=session["user_id"]), "mine"
    else:
        matches, matches_scope = None, None
    return jsonify(
        active_jobs=db.count_active_jobs(),
        customers=db.count_customers(),
        matches=matches,
        matches_scope=matches_scope,
        min_similarity=db.MIN_MATCH_SIMILARITY,
    )


@jobs_api.route("", methods=["POST"])
def create_job():
    """Neues Stellenangebot anlegen (Admins für beliebigen Kunden, 'customer'-Nutzer nur für den eigenen).
    ---
    tags:
      - Jobs
    security:
      - sessionAuth: []
    parameters:
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [position, content, customer_id]
          properties:
            position: {type: string}
            content: {type: string, description: "HTML-Beschreibung."}
            customer_id: {type: integer, description: "Nur für Admins relevant, für 'customer'-Nutzer wird der eigene Kunde erzwungen."}
            valid_from: {type: string, format: date}
            valid_until: {type: string, format: date}
            zip: {type: string}
            city: {type: string}
            document_link: {type: string}
    responses:
      201:
        description: Stelle wurde angelegt.
        schema:
          $ref: '#/definitions/SuccessResponse'
      400:
        description: Position, Beschreibung oder Kunde fehlt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    permission = job_management_permission()
    if not permission:
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    position = (data.get("position") or "").strip()
    content = (data.get("content") or "").strip()
    valid_from = data.get("valid_from") or None
    valid_until = data.get("valid_until") or None
    customer_id = data.get("customer_id") if permission == "admin" else permission
    zip_code = (data.get("zip") or "").strip() or None
    city = (data.get("city") or "").strip() or None
    document_link = (data.get("document_link") or "").strip() or None

    if not (position and content and customer_id):
        return jsonify(error="Bitte Position, Beschreibung und Kunde angeben."), 400

    match_profile, embedding = profile_and_embed(openai_client, "job", job_profile_input(position, content), current_app.logger)
    db.create_job(position, content, valid_from, valid_until, int(customer_id),
                  document_link=document_link, zip_code=zip_code, city=city,
                  match_profile=match_profile, embedding=embedding)
    return jsonify(success=True), 201


@jobs_api.route("/<int:job_id>", methods=["GET"])
def get_job(job_id):
    """Ein Stellenangebot ansehen. matching_resumes (KI-Matching) nur, wenn can_manage true ist.
    ---
    tags:
      - Jobs
    parameters:
      - name: job_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Stellenangebot inkl. can_manage und ggf. matching_resumes.
      404:
        description: Nicht gefunden.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    job = db.get_job(job_id)
    if not job:
        return jsonify(error="Nicht gefunden."), 404

    permission = job_management_permission()
    can_manage = permission == "admin" or permission == job["customer_id"]

    result = _serialize_job(dict(job))
    result["can_manage"] = can_manage
    # Passende Kandidaten für Admins und für den Stellenanbieter der eigenen Stelle
    # berechnen/ausliefern (can_manage deckt beides ab), damit die Daten sonst
    # niemanden über die Netzwerk-Antwort erreichen.
    if can_manage and job.get("embedding"):
        result["matching_resumes"] = [_serialize_dates(dict(m)) for m in db.find_matching_resumes(job["embedding"], top_k=5, job_id=job_id)]
    else:
        result["matching_resumes"] = []
    return jsonify(job=result)


@jobs_api.route("/<int:job_id>", methods=["PUT"])
def update_job(job_id):
    """Stellenangebot bearbeiten (Admins oder der zugehörige 'customer'-Nutzer).
    ---
    tags:
      - Jobs
    security:
      - sessionAuth: []
    parameters:
      - name: job_id
        in: path
        type: integer
        required: true
      - in: body
        name: body
        required: true
        schema:
          type: object
          required: [position, content, customer_id]
          properties:
            position: {type: string}
            content: {type: string}
            customer_id: {type: integer, description: "Nur für Admins änderbar."}
            valid_from: {type: string, format: date}
            valid_until: {type: string, format: date}
            zip: {type: string}
            city: {type: string}
    responses:
      200:
        description: Stelle wurde aktualisiert.
        schema:
          $ref: '#/definitions/SuccessResponse'
      400:
        description: Position, Beschreibung oder Kunde fehlt.
        schema:
          $ref: '#/definitions/ErrorResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    job = db.get_job(job_id)
    permission = job_management_permission()
    if not job or not (permission == "admin" or permission == job["customer_id"]):
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    position = (data.get("position") or "").strip()
    content = (data.get("content") or "").strip()
    valid_from = data.get("valid_from") or None
    valid_until = data.get("valid_until") or None
    customer_id = data.get("customer_id") if permission == "admin" else job["customer_id"]
    zip_code = (data.get("zip") or "").strip() or None
    city = (data.get("city") or "").strip() or None

    if not (position and content and customer_id):
        return jsonify(error="Bitte Position, Beschreibung und Kunde angeben."), 400

    # Profil + Embedding hängen nur von Position und Beschreibung ab - bei
    # unverändertem Text (z.B. nur Gültigkeit/Ort geändert) den KI-Aufruf sparen.
    if position == job["position"] and content == job["content"] and job.get("match_profile") and job.get("embedding"):
        match_profile, embedding = job["match_profile"], job["embedding"]
    else:
        match_profile, embedding = profile_and_embed(openai_client, "job", job_profile_input(position, content),
                                                     current_app.logger)
    db.update_job(job_id, position, content, valid_from, valid_until, int(customer_id),
                  zip_code=zip_code, city=city, match_profile=match_profile, embedding=embedding)
    return jsonify(success=True)


@jobs_api.route("/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    """Stellenangebot löschen (Admins oder der zugehörige 'customer'-Nutzer).
    ---
    tags:
      - Jobs
    security:
      - sessionAuth: []
    parameters:
      - name: job_id
        in: path
        type: integer
        required: true
    responses:
      200:
        description: Stelle wurde gelöscht.
        schema:
          $ref: '#/definitions/SuccessResponse'
      403:
        description: Nicht berechtigt.
        schema:
          $ref: '#/definitions/ErrorResponse'
    """
    job = db.get_job(job_id)
    permission = job_management_permission()
    if not job or not (permission == "admin" or permission == job["customer_id"]):
        return jsonify(error="Nicht berechtigt."), 403
    db.delete_job(job_id)
    return jsonify(success=True)
