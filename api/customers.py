from flask import Blueprint, jsonify, request, session

import db
from services.permissions import customer_management_permission

customers_api = Blueprint("customers_api", __name__, url_prefix="/api/customers")

CUSTOMERS_PER_PAGE_DEFAULT = 10
CUSTOMERS_PER_PAGE_OPTIONS = [5, 10, 25, 50]

_DATE_FIELDS = ("created_at", "updated_at")


def _serialize_dates(row):
    for field in _DATE_FIELDS:
        value = row.get(field)
        if value is not None and hasattr(value, "isoformat"):
            row[field] = value.isoformat()
    return row


def _paginate():
    per_page = request.args.get("per_page", type=int)
    if per_page not in CUSTOMERS_PER_PAGE_OPTIONS:
        per_page = CUSTOMERS_PER_PAGE_DEFAULT
    total = db.count_customers()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(request.args.get("page", type=int) or 1, 1)
    page = min(page, total_pages)
    customers_list = db.list_customers(limit=per_page, offset=(page - 1) * per_page)
    return customers_list, page, per_page, total_pages


@customers_api.route("", methods=["GET"])
def list_customers():
    """Liste + Pagination - Pendant zu customers()/GET (app.py). Der Redirect für
    'customer'-Nutzer auf ihren eigenen Datensatz passiert im Frontend anhand von
    /api/auth/me, nicht hier."""
    customers_list, page, per_page, total_pages = _paginate()
    return jsonify(
        customers=[_serialize_dates(dict(c)) for c in customers_list],
        page=page,
        per_page=per_page,
        total_pages=total_pages,
        per_page_options=CUSTOMERS_PER_PAGE_OPTIONS,
        can_create=session.get("user_role") == "admin",
    )


@customers_api.route("", methods=["POST"])
def create_customer():
    if session.get("user_role") != "admin":
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    company_name = (data.get("company_name") or "").strip()
    street = (data.get("street") or "").strip()
    street_number = (data.get("street_number") or "").strip()
    zip_code = (data.get("zip") or "").strip()
    city = (data.get("city") or "").strip()

    if not (company_name and street and street_number and zip_code and city):
        return jsonify(error="Bitte alle Felder ausfüllen."), 400

    db.create_customer(company_name, street, street_number, zip_code, city)
    return jsonify(success=True), 201


@customers_api.route("/<int:customer_id>", methods=["GET"])
def get_customer(customer_id):
    customer = db.get_customer(customer_id)
    if not customer:
        return jsonify(error="Nicht gefunden."), 404

    result = _serialize_dates(dict(customer))
    result["can_manage"] = customer_management_permission(customer_id)
    return jsonify(customer=result)


@customers_api.route("/<int:customer_id>", methods=["PUT"])
def update_customer(customer_id):
    if not customer_management_permission(customer_id):
        return jsonify(error="Nicht berechtigt."), 403

    data = request.get_json(silent=True) or {}
    company_name = (data.get("company_name") or "").strip()
    street = (data.get("street") or "").strip()
    street_number = (data.get("street_number") or "").strip()
    zip_code = (data.get("zip") or "").strip()
    city = (data.get("city") or "").strip()

    if not (company_name and street and street_number and zip_code and city):
        return jsonify(error="Bitte alle Felder ausfüllen."), 400

    db.update_customer(customer_id, company_name, street, street_number, zip_code, city)
    return jsonify(success=True)


@customers_api.route("/<int:customer_id>", methods=["DELETE"])
def delete_customer(customer_id):
    if session.get("user_role") != "admin":
        return jsonify(error="Nicht berechtigt."), 403
    db.delete_customer(customer_id)
    return jsonify(success=True)
