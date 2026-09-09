from flask import session


def log_in_user(user):
    """Schreibt die Login-Session für einen Nutzer (dict wie von db.get_user()/
    db.get_user_by_email()). Von der klassischen Login-/Registrierungs-Route
    (app.py) und der JSON-API (api/auth.py) genutzt."""
    session["user_id"] = user["id"]
    session["user_short_name"] = user["short_name"]
    session["user_role"] = user["role"]
    session["user_customer_id"] = user.get("customer_id")
