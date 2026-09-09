from flask import Blueprint, jsonify, session

auth_api = Blueprint("auth_api", __name__, url_prefix="/api/auth")


@auth_api.route("/me", methods=["GET"])
def me():
    """Aktueller Login-Status für React - Pendant zu inject_current_user() (app.py),
    das die klassischen Jinja-Templates versorgt. Liest dieselbe Flask-Session, damit
    ein über die bestehende /login-Seite angemeldeter Nutzer auch im React-Frontend
    (anderer Port, gleiche Site) erkannt wird."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify(user=None)
    return jsonify(user={
        "id": user_id,
        "short_name": session.get("user_short_name"),
        "role": session.get("user_role"),
        "customer_id": session.get("user_customer_id"),
    })
