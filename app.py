import json
from datetime import datetime

from flask import Flask, request, url_for, session, send_from_directory, jsonify
from flask_cors import CORS
from flasgger import Swagger
from groq import APIStatusError as GroqAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from dotenv import load_dotenv
import os

import db
from document_extraction import extract_document_text, ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS
from services import resume_service, joboffer_service
from services.ai_clients import openai_client
from services.assistant_service import DEFAULT_MODEL
from services.permissions import job_management_permission
from api.auth import auth_api
from api.jobs import jobs_api
from api.assistant import assistant_api
from api.customers import customers_api
from api.users import users_api
from api.tools import tools_api
from api.resumes import resumes_api

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
# Begrenzt die Größe hochgeladener Lebenslauf-Dateien (Schutz vor überdimensionierten Uploads).
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
# Erlaubt dem separaten React-Frontend (anderer Port, siehe frontend/), die /api/*-Routen
# mit Session-Cookie anzusprechen. FRONTEND_ORIGIN ist konfigurierbar, falls das Frontend
# mal nicht mehr auf dem Vite-Standardport 5173 läuft. /jobs/extract-upload ist die einzige
# von React per fetch() genutzte Nicht-/api/*-Route (liefert aber schon JSON) - die übrigen
# Nicht-/api/*-Routen (Datei-Auslieferung: view_resume/view_joboffer/my_resume_file) werden
# von React nur als <img>/<iframe>/<a href> eingebunden, wofür kein CORS nötig ist.
# /static/* braucht ebenfalls CORS: Browser laden @font-face-Schriften (hier Font Awesome)
# nur dann von einem fremden Origin, wenn Access-Control-Allow-Origin gesetzt ist - sonst
# bleiben die fa-Icons unsichtbar, obwohl die restliche style.css normal greift (die
# benötigt kein CORS). Rein statische, öffentliche Assets, daher "*" ohne Credentials.
_frontend_origin = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
CORS(app, resources={
    r"/api/*": {"origins": _frontend_origin, "supports_credentials": True},
    r"/jobs/extract-upload": {"origins": _frontend_origin, "supports_credentials": True},
    r"/static/*": {"origins": "*"},
})
# Swagger/OpenAPI-Doku nur für die /api/*-Routen (die React-REST-API) - die
# klassischen Jinja-Seiten (Formulare, Redirects) sind keine API und würden die
# Spec nur unübersichtlich machen. Die eigentlichen Parameter/Response-Specs
# stehen als YAML-Docstrings direkt bei den jeweiligen Routen in api/*.py.
app.config["SWAGGER"] = {
    "title": "Stellenmarkt-AI API",
    "uiversion": 3,
    "specs_route": "/apidocs/",
}
swagger = Swagger(app, config={
    "headers": [],
    "specs": [
        {
            "endpoint": "apispec",
            "route": "/apispec.json",
            "rule_filter": lambda rule: rule.rule.startswith("/api/"),
            "model_filter": lambda tag: True,
        }
    ],
    "static_url_path": "/flasgger_static",
    "swagger_ui": True,
    "specs_route": "/apidocs/",
}, template={
    "info": {
        "title": "Stellenmarkt-AI API",
        "description": "REST-API des React-Frontends (Stellenangebote, Stellenanbieter, "
                        "Nutzer, Lebensläufe, KI-Tools). Auth läuft über das "
                        "Flask-Session-Cookie, gesetzt von POST /api/auth/login.",
        "version": "1.0.0",
    },
    "securityDefinitions": {
        "sessionAuth": {
            "type": "apiKey",
            "in": "cookie",
            "name": "session",
            "description": "Flask-Session-Cookie, gesetzt durch POST /api/auth/login bzw. /api/auth/register.",
        }
    },
    "definitions": {
        "ErrorResponse": {
            "type": "object",
            "properties": {"error": {"type": "string"}},
        },
        "SuccessResponse": {
            "type": "object",
            "properties": {"success": {"type": "boolean"}},
        },
    },
})

app.register_blueprint(auth_api)
app.register_blueprint(jobs_api)
app.register_blueprint(assistant_api)
app.register_blueprint(customers_api)
app.register_blueprint(users_api)
app.register_blueprint(tools_api)
app.register_blueprint(resumes_api)
db.init_db()

# Kurzbeschreibung je Seite der React-Oberfläche für den KI-Assistenten. Anders
# als früher (Stand: reine Flask-Templates) nicht mehr automatisch aus
# app.url_map erzeugt - die Flask-Routen sind inzwischen nur noch API-
# Endpunkte/Datei-Auslieferung, keine Seiten mehr, und React-Router-Pfade
# tauchen dort gar nicht auf. Bei neuen React-Seiten hier manuell ergänzen.
REACT_PAGES = [
    ("/", "Startseite mit dem KI-Assistenten (diese Seite)"),
    ("/login", "Anmeldeseite für bestehende Nutzer. Erreichbar über das Konto-Menü oben rechts in der Navigation (Symbol + Beschriftung 'Konto'), dort auf 'Anmelden' klicken - nur sichtbar, wenn niemand eingeloggt ist"),
    ("/register", "Registrierungsseite für neue Nutzer. Erreichbar über das Konto-Menü oben rechts in der Navigation (Symbol + Beschriftung 'Konto'), dort auf 'Registrieren' klicken - nur sichtbar, wenn niemand eingeloggt ist"),
    ("/jobs", "Stellenangebote: Liste für alle sichtbar (auch nicht eingeloggt), im Hauptmenü als 'Stellenangebote' verlinkt, mit Suche, Seitenblättern und pro Zeile 'Ansehen' bzw. 'Bearbeiten'/'Löschen'. Für eingeloggte Nutzer mit Rolle 'user' sind Stellen hervorgehoben und mit 'Passt zu dir' samt Prozentwert markiert, wenn einer ihrer Lebensläufe zu mindestens 60 % zur Stelle passt (Vektor-Ähnlichkeit). Für Nutzer mit Rolle 'customer' zeigen die eigenen Stellen einen Hinweis wie '3 passende Kandidat:innen', der zur Stellenseite mit den Kandidat:innen führt. Neue Stelle anlegen für Admins (beliebiger Kunde) sowie für Nutzer mit Rolle 'customer' und zugeordnetem Stellenanbieter (nur für den eigenen Kunden) - dabei kann optional ein Stellenangebot-Dokument (PDF, .docx, .odt) hochgeladen werden, das Position, PLZ, Stadt und eine Zusammenfassung als Beschreibung automatisch befüllt"),
    ("/jobs/<id>/edit", "Detailseite eines Stellenangebots, erreichbar über 'Ansehen'/'Bearbeiten' in der Stellenangebote-Liste. Oben Position, Stellenanbieter, Ort und Status (Aktiv, Läuft bald ab, Abgelaufen, Geplant), darunter links die Stellendaten. Admins sowie 'customer'-Nutzer für ihren eigenen Stellenanbieter bekommen ein Bearbeiten-Formular (Speichern, oben Löschen/Abbrechen) und rechts daneben die Liste 'Passende Kandidat:innen' mit Ähnlichkeit in Prozent (ein Klick öffnet das Nutzerprofil; Lebensläufe, die die Person speziell auf diese Stelle angepasst hat, sind mit 'angepasst' gekennzeichnet). Alle anderen sehen eine Leseansicht ohne Speichern. Eingeloggte Nutzer mit Rolle 'user' haben rechts das Feld 'Lebenslauf anpassen': dort eine eigene Lebenslauf-Version als 'Ausgangsversion' wählen und 'Für diese Stelle anpassen' klicken - die KI formuliert, sortiert und gewichtet die vorhandenen Angaben auf die Stelle hin um, ohne etwas zu erfinden. Es erscheint zuerst ein Entwurf mit der Ähnlichkeit vorher/nachher, einer automatischen Prüfung auf im Original nicht belegte Angaben und einer Vorschau; erst mit 'Übernehmen' wird er als neue Lebenslauf-Version gespeichert ('Verwerfen' verwirft ihn). Eine so angepasste Version zählt beim Matching nur für diese eine Stelle"),
    ("/customers", "Stellenanbieter (Kunden): Liste für alle sichtbar, im Hauptmenü als 'Stellenanbieter' verlinkt, mit Suche, Seitenblättern und Löschen direkt pro Zeile (nur Admins). Neuen Stellenanbieter anlegen nur für Admins"),
    ("/customers/<id>/edit", "Detailseite eines Stellenanbieters: oben Firmenname und Adresse, links die Unternehmensdaten - als Bearbeiten-Formular für Admins und für 'customer'-Nutzer beim eigenen Stellenanbieter, für alle anderen als Leseansicht. Rechts daneben die Stellenangebote dieses Stellenanbieters mit Suchfeld (Position) und Seitenblättern, je mit Status und Gültigkeit; ein Klick öffnet die Stelle. 'customer'-Nutzer sehen bei ihren Stellen zusätzlich die Anzahl passender Kandidat:innen"),
    ("/users", "Nutzerverwaltung: Liste aller Nutzer + neuen Nutzer anlegen, inkl. Rollenvergabe. Nur für Admins (und lesend für 'customer'-Nutzer), im Hauptmenü als 'Nutzer' verlinkt"),
    ("/users/<id>/edit", "Nutzerprofil: links die Nutzerdaten, rechts die hochgeladenen Lebensläufe (angepasste Versionen mit 'Angepasst für <Stelle>'). Admins können die Daten inkl. Rolle bearbeiten; 'customer'-Nutzer sehen das Profil nur lesend, z.B. nach Klick auf eine Person unter 'Passende Kandidat:innen'"),
    ("/tools/resume", "Lebenslauf für einen bestehenden, per Auswahlliste gewählten Nutzer generieren (immer mit dessen echtem Namen; der Wohnort wird nur übernommen, wenn bei ihm PLZ und Stadt hinterlegt sind, sonst frei erfunden). Nur für Admins, erreichbar über das Konto-Menü (Nutzername oben rechts) in der Navigation"),
    ("/tools/joboffer", "Stellenangebot für einen per Auswahlliste gewählten Stellenanbieter generieren; legt dabei automatisch auch einen passenden Eintrag unter 'Stellenangebote' an. Nur für Admins, erreichbar über das Konto-Menü (Nutzername oben rechts) in der Navigation"),
    ("/resumes", "Eigene Lebensläufe des eingeloggten Nutzers ansehen: der neueste eingebettet (PDF direkt, andere Formate als Download-Link), per Auswahlliste sind auch ältere Versionen abrufbar, inkl. Löschen. Auf eine Stelle angepasste Versionen heißen dort '... angepasst für <Stelle>'. Darunter die zur gewählten Version passenden Stellenangebote mit Ähnlichkeit in Prozent (bei einer angepassten Version nur ihre Zielstelle). Neue Lebensläufe entweder per KI generieren lassen oder eine eigene Datei (PDF, .docx, .odt) hochladen - beides wird für die Stellen-Empfehlung vektorisiert. Nur für eingeloggte Nutzer mit Rolle 'user', erreichbar über das Konto-Menü oben rechts in der Navigation"),
]

# Kein eigener React-Router-Pfad (nur eine Aktion im Konto-Menü), aber die KI
# muss sie kennen, sonst verneint sie fälschlich, dass es sie gibt.
_NON_PAGE_ACTIONS = [
    "Abmelden - erreichbar über das Konto-Menü oben rechts in der Navigation: dort steht im eingeloggten Zustand nicht 'Konto', sondern der Kurzname des angemeldeten Nutzers; darauf klicken, um das Menü zu öffnen, dort erscheint 'Abmelden'",
]


def build_site_map():
    """Liefert die Seitenliste der React-Oberfläche (einzige UI) für den
    KI-Assistenten als Freitext."""
    lines = [f"- {path} -> {description}" for path, description in REACT_PAGES]
    lines += [f"- {action}" for action in _NON_PAGE_ACTIONS]
    return "\n".join(lines)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


RESUME_DIR = resume_service.RESUME_DIR
JOBOFFER_DIR = joboffer_service.JOBOFFER_DIR


@app.route('/tools/resume/<path:filename>')
def view_resume(filename):
    if session.get("user_role") not in ("admin", "customer"):
        return jsonify(error="Nicht berechtigt."), 403
    return send_from_directory(RESUME_DIR, filename)


@app.route('/jobs/extract-upload', methods=["POST"])
def extract_job_upload():
    """Liest ein hochgeladenes Stellenangebot-Dokument (PDF/.docx/.odt) aus und lässt
    per KI eine Zusammenfassung sowie ggf. Position/PLZ/Stadt daraus extrahieren, zur
    Vorbefüllung des 'Stelle anlegen'-Formulars. Legt selbst noch keine Stelle an."""
    if not job_management_permission():
        return jsonify(error="Nicht berechtigt."), 403

    uploaded_file = request.files.get("job_file")
    if not uploaded_file or not uploaded_file.filename:
        return jsonify(error="Keine Datei ausgewählt."), 400

    ext = os.path.splitext(uploaded_file.filename)[1].lower()
    if ext not in ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS:
        return jsonify(error="Bitte eine Datei im PDF-, Word- (.docx) oder LibreOffice-Format (.odt) hochladen."), 400

    try:
        document_text = extract_document_text(uploaded_file.filename, uploaded_file.stream).strip()
    except Exception as e:
        app.logger.warning("Fehler beim Auslesen des hochgeladenen Stellenangebots: %s", e)
        return jsonify(error="Die Datei konnte nicht gelesen werden. Bitte Format und Inhalt prüfen."), 400

    if not document_text:
        return jsonify(error="In der Datei konnte kein Text gefunden werden."), 400

    try:
        data = joboffer_service.extract_joboffer_from_text(openai_client, DEFAULT_MODEL, document_text)
    except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
        app.logger.warning("API error %s: %s", e.status_code, e.body)
        return jsonify(error="Die Datei konnte gerade nicht verarbeitet werden. Bitte später erneut versuchen."), 502
    except (json.JSONDecodeError, ValueError) as e:
        app.logger.warning("Unerwartetes KI-Antwortformat: %s", e)
        return jsonify(error="Die Datei konnte gerade nicht verarbeitet werden. Bitte später erneut versuchen."), 502

    os.makedirs(JOBOFFER_DIR, exist_ok=True)
    filename = f"stellenangebot_{datetime.now():%Y%m%d_%H%M%S}{ext}"
    uploaded_file.stream.seek(0)
    uploaded_file.save(os.path.join(JOBOFFER_DIR, filename))

    return jsonify(
        position=(data.get("position") or "").strip(),
        zip=(data.get("zip") or "").strip(),
        city=(data.get("city") or "").strip(),
        content=(data.get("content") or "").strip(),
        document_link=url_for('view_joboffer', filename=filename),
    )


@app.route('/resumes/<int:resume_id>/file')
def my_resume_file(resume_id):
    resume = db.get_resume(resume_id)
    if not resume or resume["user_id"] != session.get("user_id") or not resume["document_link"]:
        return jsonify(error="Nicht gefunden."), 404
    filename = os.path.basename(resume["document_link"])
    return send_from_directory(RESUME_DIR, filename)


@app.route('/tools/joboffer/<path:filename>')
def view_joboffer(filename):
    # Offen für alle: Stellenangebots-PDFs werden im (ebenfalls öffentlichen)
    # Stellen-Ansichtsmodus für Nicht-Admins eingebettet.
    return send_from_directory(JOBOFFER_DIR, filename)

if __name__ == '__main__':
    # Debug-Modus (Reloader + Werkzeug-Debugger) nur per FLASK_DEBUG=1 - der Debugger
    # erlaubt im Fehlerfall Codeausführung im Browser und darf nie öffentlich laufen.
    app.run(debug=os.environ.get("FLASK_DEBUG", "0") == "1", host='0.0.0.0', port=5003)
