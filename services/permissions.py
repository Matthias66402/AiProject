from flask import session

import db


def job_management_permission():
    """Gibt zurück, für welche customer_id der eingeloggte Nutzer Stellen anlegen/
    bearbeiten/löschen darf: den String 'admin' für Admins (alle Kunden erlaubt),
    eine customer_id (int) für Rolle 'customer' mit zugeordnetem Stellenanbieter,
    sonst None (keine Berechtigung)."""
    role = session.get("user_role")
    if role == "admin":
        return "admin"
    if role == "customer" and session.get("user_customer_id"):
        return session["user_customer_id"]
    return None


def own_customer_for_session():
    """Der dem eingeloggten Nutzer zugeordnete Stellenanbieter (Rolle 'customer'),
    für die Anzeige im Stellen-Formular. None für alle anderen Rollen/ohne Zuordnung."""
    if session.get("user_role") == "customer" and session.get("user_customer_id"):
        return db.get_customer(session["user_customer_id"])
    return None
