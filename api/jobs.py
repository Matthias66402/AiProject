from flask import Blueprint, current_app, jsonify, request, session

import db
from embeddings import embed_text, strip_html_to_text
from services.ai_clients import openai_client
from services.permissions import job_management_permission, own_customer_for_session

jobs_api = Blueprint("jobs_api", __name__, url_prefix="/api/jobs")

JOBS_PER_PAGE_DEFAULT = 10
JOBS_PER_PAGE_OPTIONS = [10, 25, 50, 100]

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


def _paginate(customer_id=None, search=None):
    per_page = request.args.get("per_page", type=int)
    if per_page not in JOBS_PER_PAGE_OPTIONS:
        per_page = JOBS_PER_PAGE_DEFAULT
    total = db.count_jobs(customer_id, search=search)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(request.args.get("page", type=int) or 1, 1)
    page = min(page, total_pages)
    jobs_list = db.list_jobs(customer_id, limit=per_page, offset=(page - 1) * per_page, search=search)
    return jobs_list, page, per_page, total_pages


@jobs_api.route("", methods=["GET"])
def list_jobs():
    """Liste + Pagination - Pendant zu jobs()/GET (app.py). customer_id filtert wie
    beim "von dieser Stelle aus zum Kunden zurück"-Flow der klassischen Seite. search
    filtert (nur für die React-Liste, siehe JobsPage.jsx) auf die Position."""
    customer_id = request.args.get("customer_id", type=int)
    search = (request.args.get("search") or "").strip()
    jobs_list, page, per_page, total_pages = _paginate(customer_id, search)
    permission = job_management_permission()
    own_customer = own_customer_for_session()
    return jsonify(
        jobs=[_serialize_dates(dict(job)) for job in jobs_list],
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        per_page_options=JOBS_PER_PAGE_OPTIONS,
        customers=[_serialize_dates(dict(c)) for c in db.list_customers()],
        own_customer=_serialize_dates(dict(own_customer)) if own_customer else None,
        can_create=bool(permission),
    )


@jobs_api.route("", methods=["POST"])
def create_job():
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

    embedding = embed_text(openai_client, f"{position}\n\n{strip_html_to_text(content)}", current_app.logger)
    db.create_job(position, content, valid_from, valid_until, int(customer_id),
                  document_link=document_link, zip_code=zip_code, city=city, embedding=embedding)
    return jsonify(success=True), 201


@jobs_api.route("/<int:job_id>", methods=["GET"])
def get_job(job_id):
    job = db.get_job(job_id)
    if not job:
        return jsonify(error="Nicht gefunden."), 404

    permission = job_management_permission()
    can_manage = permission == "admin" or permission == job["customer_id"]

    result = _serialize_dates(dict(job))
    result.pop("embedding", None)
    result["can_manage"] = can_manage
    # Passende Kandidaten nur für Admins berechnen/ausliefern - wie im Template
    # ({% if editing_job and is_admin %}), damit die Daten Nicht-Admins nicht mal
    # über die Netzwerk-Antwort erreichen.
    if session.get("user_role") == "admin" and job.get("embedding"):
        result["matching_resumes"] = [_serialize_dates(dict(m)) for m in db.find_matching_resumes(job["embedding"], top_k=5)]
    else:
        result["matching_resumes"] = []
    return jsonify(job=result)


@jobs_api.route("/<int:job_id>", methods=["PUT"])
def update_job(job_id):
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

    embedding = embed_text(openai_client, f"{position}\n\n{strip_html_to_text(content)}", current_app.logger)
    db.update_job(job_id, position, content, valid_from, valid_until, int(customer_id),
                  zip_code=zip_code, city=city, embedding=embedding)
    return jsonify(success=True)


@jobs_api.route("/<int:job_id>", methods=["DELETE"])
def delete_job(job_id):
    job = db.get_job(job_id)
    permission = job_management_permission()
    if not job or not (permission == "admin" or permission == job["customer_id"]):
        return jsonify(error="Nicht berechtigt."), 403
    db.delete_job(job_id)
    return jsonify(success=True)
