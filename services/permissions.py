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


def customer_management_permission(customer_id):
    """True, wenn der eingeloggte Nutzer diesen Stellenanbieter anlegen/bearbeiten/
    löschen darf: Admins immer, Nutzer mit Rolle 'customer' nur den ihnen
    zugeordneten (Anlegen/Löschen bleibt Admins vorbehalten, das prüfen die
    aufrufenden Routen zusätzlich selbst)."""
    role = session.get("user_role")
    if role == "admin":
        return True
    return role == "customer" and session.get("user_customer_id") == customer_id
