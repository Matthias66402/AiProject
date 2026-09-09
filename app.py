import json
from datetime import datetime
from urllib.parse import urlencode

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from flask_cors import CORS
from groq import APIStatusError as GroqAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os

import db
from db import ROLES, DEFAULT_ROLE
from embeddings import embed_text, strip_html_to_text
from document_extraction import extract_document_text, ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS
from services import resume_service, joboffer_service
from services.ai_clients import openai_client
from services.assistant_service import AVAILABLE_MODELS, DEFAULT_MODEL, ask_assistant
from services.auth_service import log_in_user
from services.permissions import customer_management_permission, job_management_permission, own_customer_for_session
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
# von React genutzte Nicht-/api/*-Route (noch nicht umgezogen, liefert aber schon JSON).
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
app.register_blueprint(auth_api)
app.register_blueprint(jobs_api)
app.register_blueprint(assistant_api)
app.register_blueprint(customers_api)
app.register_blueprint(users_api)
app.register_blueprint(tools_api)
app.register_blueprint(resumes_api)
db.init_db()

# Endpoint -> Funktion, die aus request.view_args den passenden React-Pfad baut.
# Nur Seiten mit echter React-Entsprechung landen hier - alles andere (Abmelden
# [reiner Redirect ohne eigene Seite], Datei-Auslieferungsrouten, Lösch-Endpunkte,
# /api/*, /static/*) bleibt bewusst außen vor und wird nie umgeleitet.
_REACT_PAGE_ROUTES = {
    "home": lambda args: "/",
    "login": lambda args: "/login",
    "register": lambda args: "/register",
    "jobs": lambda args: "/jobs",
    "edit_job": lambda args: f"/jobs/{args['job_id']}/edit",
    "customers": lambda args: "/customers",
    "edit_customer": lambda args: f"/customers/{args['customer_id']}/edit",
    "users": lambda args: "/users",
    "edit_user": lambda args: f"/users/{args['user_id']}/edit",
    "generate_resume": lambda args: "/tools/resume",
    "generate_joboffer": lambda args: "/tools/joboffer",
    "my_resumes": lambda args: "/resumes",
}


@app.before_request
def redirect_to_react_by_default():
    """React ist die Standard-Oberfläche: GET-Aufrufe einer klassischen Seite mit
    React-Entsprechung leiten dorthin um, sofern der/die Nutzer:in nicht bewusst im
    klassischen UI bleiben möchte. "Klassisch"-Link in React hängt ?classic=1 an,
    das merkt sich (Session-Cookie, endet mit dem Browser-Neustart) und hält
    sämtliche Folgenavigation - inkl. Formular-POSTs und deren Redirects - auf der
    klassischen Seite. ?classic=0 macht diese Wahl wieder rückgängig. POST/PUT/
    DELETE werden nie umgeleitet, sonst würden Formularabsendungen ins Leere laufen."""
    if request.method != "GET":
        return None

    classic_param = request.args.get("classic")
    if classic_param == "1":
        session["ui_pref"] = "classic"
        return None
    if classic_param == "0":
        session.pop("ui_pref", None)
    elif session.get("ui_pref") == "classic":
        return None

    build_react_path = _REACT_PAGE_ROUTES.get(request.endpoint)
    if build_react_path is None:
        return None

    target = f"{_frontend_origin}{build_react_path(request.view_args or {})}"
    # ?classic=... steuert nur diese Weiche und ist für React irrelevant - nicht durchreichen.
    forwarded_args = request.args.to_dict(flat=False)
    forwarded_args.pop("classic", None)
    query_string = urlencode(forwarded_args, doseq=True)
    if query_string:
        target = f"{target}?{query_string}"
    return redirect(target)


@app.context_processor
def inject_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return {"current_user": None}
    return {"current_user": {
        "id": user_id,
        "short_name": session.get("user_short_name"),
        "role": session.get("user_role"),
        "customer_id": session.get("user_customer_id"),
    }}


@app.context_processor
def inject_frontend_url():
    # Für Links aus den klassischen Templates auf bereits nach React umgezogene
    # Seiten (aktuell nur /jobs) - siehe navigation.html.
    return {"FRONTEND_URL": _frontend_origin}



# Kurzbeschreibung je Route für den KI-Assistenten. Die Website ist noch im
# Aufbau, deshalb wird die eigentliche Seitenliste (URL + erlaubte Methoden)
# unten automatisch aus den registrierten Flask-Routen erzeugt - hier muss
# bei neuen Routen nur noch der Zweck ergänzt werden, der Rest bleibt sync.
PAGE_DESCRIPTIONS = {
    "home": "Startseite mit dem KI-Assistenten (diese Seite)",
    "login": "Anmeldeseite für bestehende Nutzer. Erreichbar über das Konto-Menü oben rechts in der Navigation (Symbol + Beschriftung 'Konto'), dort auf 'Anmelden' klicken - nur sichtbar, wenn niemand eingeloggt ist",
    "register": "Registrierungsseite für neue Nutzer. Erreichbar über das Konto-Menü oben rechts in der Navigation (Symbol + Beschriftung 'Konto'), dort auf 'Registrieren' klicken - nur sichtbar, wenn niemand eingeloggt ist",
    "logout": "Abmelden. Erreichbar über das Konto-Menü oben rechts in der Navigation - dort steht im eingeloggten Zustand nicht 'Konto', sondern der Kurzname des angemeldeten Nutzers; darauf klicken, um das Menü zu öffnen, dort erscheint 'Abmelden'",
    "users": "Nutzerverwaltung: Liste aller Nutzer + neuen Nutzer anlegen, inkl. Rollenvergabe. Nur für Admins, im Hauptmenü als 'Nutzer' verlinkt",
    "edit_user": "Einen bestehenden Nutzer bearbeiten, inkl. Rollenvergabe. Nur für Admins",
    "jobs": "Stellenangebote: Liste für alle sichtbar (auch nicht eingeloggt), im Hauptmenü als 'Stellenangebote' verlinkt. Neue Stelle anlegen für Admins (beliebiger Kunde) sowie für Nutzer mit Rolle 'customer' und zugeordnetem Stellenanbieter (nur für den eigenen Kunden) - dabei kann optional ein Stellenangebot-Dokument (PDF, .docx, .odt) hochgeladen werden, das Position, PLZ, Stadt und eine Zusammenfassung als Beschreibung automatisch befüllt",
    "edit_job": "Ein bestehendes Stellenangebot ansehen. Admins sowie 'customer'-Nutzer für ihren eigenen Stellenanbieter bekommen ein Bearbeiten-Formular (inkl. Löschen), für alle anderen nur eine Leseansicht (Position, Kunde, PLZ/Stadt, Gültigkeit als Text, bei KI-generierten Stellen zusätzlich das PDF eingebettet) ohne Speichern-Möglichkeit",
    "delete_job": "Ein Stellenangebot löschen. Nur für Admins",
    "customers": "Stellenanbieter (Kunden): Liste für alle sichtbar, im Hauptmenü als 'Stellenanbieter' verlinkt. Neuen Stellenanbieter anlegen nur für Admins",
    "edit_customer": "Einen bestehenden Stellenanbieter ansehen. Für Admins ein Bearbeiten-Formular, für alle anderen nur eine Leseansicht (Firma, Adresse, PLZ, Stadt als Text) ohne Speichern-Möglichkeit. Darunter zusätzlich die Liste der zu diesem Stellenanbieter gehörenden Stellenangebote",
    "delete_customer": "Einen Stellenanbieter löschen. Nur für Admins",
    "generate_resume": "Lebenslauf für einen bestehenden, per Auswahlliste gewählten Nutzer generieren (immer mit dessen echtem Namen; der Wohnort wird nur übernommen, wenn bei ihm PLZ und Stadt hinterlegt sind, sonst frei erfunden). Nur für Admins, erreichbar über das 'Tools'-Menü in der Navigation",
    "generate_joboffer": "Stellenangebot für einen per Auswahlliste gewählten Stellenanbieter generieren; legt dabei automatisch auch einen passenden Eintrag unter 'Stellenangebote' an. Nur für Admins, erreichbar über das 'Tools'-Menü in der Navigation",
    "my_resumes": "Eigene Lebensläufe des eingeloggten Nutzers ansehen: der neueste eingebettet (PDF direkt, andere Formate als Download-Link), per Auswahlliste sind auch ältere Versionen abrufbar. Neue Lebensläufe entweder per KI generieren lassen oder eine eigene Datei (PDF, .docx, .odt) hochladen - beides wird für die Stellen-Empfehlung vektorisiert. Nur für eingeloggte Nutzer mit Rolle 'user', erreichbar über das Konto-Menü oben rechts in der Navigation",
}


def build_site_map():
    """Erzeugt eine aktuelle Liste aller Routen aus app.url_map, ergänzt um
    die Kurzbeschreibung aus PAGE_DESCRIPTIONS. Läuft bei jeder Anfrage neu,
    damit neue/geänderte Routen sofort ohne Prompt-Pflege sichtbar sind."""
    lines = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint in ("static", "favicon"):
            continue
        description = PAGE_DESCRIPTIONS.get(rule.endpoint, "(noch keine Beschreibung hinterlegt)")
        methods = ", ".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        lines.append(f"- {rule.rule} [{methods}] -> {description}")
    # Kein eigener Flask-Route-Eintrag (der Wechsel hängt nur ?classic=1/0 an die
    # jeweils aktuelle Seite an), aber eine Funktion, die die KI kennen muss, sonst
    # verneint sie fälschlich, dass es sie gibt.
    lines.append(
        "- (kein eigener Menüpunkt/Seite, sondern auf jeder Seite oben rechts in der Navigation, "
        "direkt links neben dem Konto-Menü) [GET] -> Wechsel zwischen der neuen React-Oberfläche "
        "(Standard, Link-Beschriftung 'Klassisch' führt zur alten Oberfläche) und der klassischen "
        "Flask-Oberfläche (Link-Beschriftung 'Reaktiv' führt zur neuen Oberfläche); die Wahl bleibt "
        "bis zum nächsten Browser-Neustart erhalten"
    )
    return "\n".join(lines)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route('/', methods=["GET", "POST"])
def home():  # put application's code here
    if request.method == "POST":
        question = request.form.get("question")
        answer, selected_model = ask_assistant(question, request.form.get("model"), build_site_map(), app.logger)
        return render_template('index.html', content_template='home.html', answer=answer, models=AVAILABLE_MODELS, selected_model=selected_model)
    else:
        return render_template('index.html', content_template='home.html', models=AVAILABLE_MODELS, selected_model=DEFAULT_MODEL)

@app.route('/login', methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        user = db.get_user_by_email(email)
        if user and check_password_hash(user["password_hash"], password):
            log_in_user(user)
            return redirect(url_for('home'))
        error = "E-Mail oder Passwort ist falsch."

    return render_template('index.html', content_template='login.html', error=error)


@app.route('/register', methods=["GET", "POST"])
def register():
    error = None
    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        short_name = request.form.get("short_name", "").strip()
        email = request.form.get("email", "").strip()
        zip_code = request.form.get("zip", "").strip()
        city = request.form.get("city", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not (first_name and last_name and short_name and email and zip_code and city and password):
            error = "Bitte alle Felder ausfüllen."
        elif password != password_confirm:
            error = "Die Passwörter stimmen nicht überein."
        elif db.get_user_by_email(email):
            error = "Diese E-Mail-Adresse ist bereits registriert."
        else:
            db.create_user(first_name, last_name, short_name, email, generate_password_hash(password), DEFAULT_ROLE, zip_code, city)
            log_in_user(db.get_user_by_email(email))
            return redirect(url_for('home'))

    return render_template('index.html', content_template='register.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/users', methods=["GET", "POST"])
def users():
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        short_name = request.form.get("short_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", DEFAULT_ROLE)
        if role not in ROLES:
            role = DEFAULT_ROLE
        zip_code = request.form.get("zip", "").strip() or None
        city = request.form.get("city", "").strip() or None
        customer_id = request.form.get("customer_id") or None
        if role != "customer":
            customer_id = None

        if first_name and last_name and short_name and email and password:
            db.create_user(first_name, last_name, short_name, email, generate_password_hash(password), role, zip_code, city, customer_id)

        return redirect(url_for('users'))

    return render_template('index.html', content_template='user.html', users=db.list_users(), editing_user=None, roles=ROLES, customers=db.list_customers(), resumes=[])


@app.route('/users/<int:user_id>/edit', methods=["GET", "POST"])
def edit_user(user_id):
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))

    if request.method == "POST":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        short_name = request.form.get("short_name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", DEFAULT_ROLE)
        if role not in ROLES:
            role = DEFAULT_ROLE
        password_hash = generate_password_hash(password) if password else None
        zip_code = request.form.get("zip", "").strip() or None
        city = request.form.get("city", "").strip() or None
        customer_id = request.form.get("customer_id") or None
        if role != "customer":
            customer_id = None

        if first_name and last_name and short_name and email:
            db.update_user(user_id, first_name, last_name, short_name, email, role, password_hash, zip_code, city, customer_id)

        return redirect(url_for('users'))

    return render_template('index.html', content_template='user.html', users=db.list_users(), editing_user=db.get_user(user_id), roles=ROLES, customers=db.list_customers(), resumes=db.list_resumes_for_user(user_id))


JOBS_PER_PAGE_DEFAULT = 10
JOBS_PER_PAGE_OPTIONS = [10, 25, 50, 100]


def _paginate_jobs(customer_id=None):
    """Liest page/per_page aus der Query-String (per_page begrenzt auf
    JOBS_PER_PAGE_OPTIONS, sonst Default 10; page begrenzt auf die tatsächliche
    Seitenzahl) und gibt (jobs, page, per_page, total_pages) zurück."""
    per_page = request.args.get("per_page", type=int)
    if per_page not in JOBS_PER_PAGE_OPTIONS:
        per_page = JOBS_PER_PAGE_DEFAULT
    total = db.count_jobs(customer_id)
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(request.args.get("page", type=int) or 1, 1)
    page = min(page, total_pages)
    jobs_list = db.list_jobs(customer_id, limit=per_page, offset=(page - 1) * per_page)
    return jobs_list, page, per_page, total_pages


@app.route('/jobs', methods=["GET", "POST"])
def jobs():
    if request.method == "POST":
        permission = job_management_permission()
        if not permission:
            return redirect(url_for('jobs'))

        position = request.form.get("position", "").strip()
        content = request.form.get("content", "").strip()
        valid_from = request.form.get("valid_from") or None
        valid_until = request.form.get("valid_until") or None
        customer_id = request.form.get("customer_id") if permission == "admin" else permission
        zip_code = request.form.get("zip", "").strip() or None
        city = request.form.get("city", "").strip() or None
        document_link = request.form.get("document_link", "").strip() or None

        if position and content and customer_id:
            embedding = embed_text(openai_client, f"{position}\n\n{strip_html_to_text(content)}", app.logger)
            db.create_job(position, content, valid_from, valid_until, int(customer_id), document_link=document_link, zip_code=zip_code, city=city, embedding=embedding)

        return redirect(url_for('jobs'))

    jobs_list, page, per_page, total_pages = _paginate_jobs()
    return render_template('index.html', content_template='jobs.html', jobs=jobs_list, customers=db.list_customers(), editing_job=None, own_customer=own_customer_for_session(), page=page, per_page=per_page, total_pages=total_pages, per_page_options=JOBS_PER_PAGE_OPTIONS)


@app.route('/jobs/<int:job_id>/edit', methods=["GET", "POST"])
def edit_job(job_id):
    if request.method == "POST":
        job = db.get_job(job_id)
        permission = job_management_permission()
        if not job or not (permission == "admin" or permission == job["customer_id"]):
            return redirect(url_for('jobs'))

        position = request.form.get("position", "").strip()
        content = request.form.get("content", "").strip()
        valid_from = request.form.get("valid_from") or None
        valid_until = request.form.get("valid_until") or None
        customer_id = request.form.get("customer_id") if permission == "admin" else job["customer_id"]
        zip_code = request.form.get("zip", "").strip() or None
        city = request.form.get("city", "").strip() or None

        if position and content and customer_id:
            embedding = embed_text(openai_client, f"{position}\n\n{strip_html_to_text(content)}", app.logger)
            db.update_job(job_id, position, content, valid_from, valid_until, int(customer_id), zip_code=zip_code, city=city, embedding=embedding)

        return redirect(url_for('jobs'))

    job = db.get_job(job_id)
    from_customer_id = request.args.get("from_customer", type=int)
    came_from_customer = bool(job and from_customer_id and from_customer_id == job["customer_id"])
    jobs_list, page, per_page, total_pages = _paginate_jobs(job["customer_id"] if came_from_customer else None)
    matching_resumes = db.find_matching_resumes(job["embedding"], top_k=5) if job and job.get("embedding") else []

    return render_template('index.html', content_template='jobs.html', jobs=jobs_list, customers=db.list_customers(), editing_job=job, came_from_customer=came_from_customer, matching_resumes=matching_resumes, own_customer=own_customer_for_session(), page=page, per_page=per_page, total_pages=total_pages, per_page_options=JOBS_PER_PAGE_OPTIONS)


@app.route('/jobs/<int:job_id>/delete', methods=["POST"])
def delete_job(job_id):
    job = db.get_job(job_id)
    permission = job_management_permission()
    if not job or not (permission == "admin" or permission == job["customer_id"]):
        return redirect(url_for('jobs'))
    db.delete_job(job_id)
    return redirect(url_for('jobs'))

CUSTOMERS_PER_PAGE_DEFAULT = 10
CUSTOMERS_PER_PAGE_OPTIONS = [5, 10, 25, 50]


def _paginate_customers():
    """Liest page/per_page aus der Query-String (per_page begrenzt auf
    CUSTOMERS_PER_PAGE_OPTIONS, sonst Default; page begrenzt auf die tatsächliche
    Seitenzahl) und gibt (customers, page, per_page, total_pages) zurück."""
    per_page = request.args.get("per_page", type=int)
    if per_page not in CUSTOMERS_PER_PAGE_OPTIONS:
        per_page = CUSTOMERS_PER_PAGE_DEFAULT
    total = db.count_customers()
    total_pages = max((total + per_page - 1) // per_page, 1)
    page = max(request.args.get("page", type=int) or 1, 1)
    page = min(page, total_pages)
    customers_list = db.list_customers(limit=per_page, offset=(page - 1) * per_page)
    return customers_list, page, per_page, total_pages


@app.route('/customers', methods=["GET", "POST"])
def customers():
    if request.method == "POST":
        if session.get("user_role") != "admin":
            return redirect(url_for('customers'))

        company_name = request.form.get("company_name", "").strip()
        street = request.form.get("street", "").strip()
        street_number = request.form.get("street_number", "").strip()
        zip_code = request.form.get("zip", "").strip()
        city = request.form.get("city", "").strip()

        if company_name and street and street_number and zip_code and city:
            db.create_customer(company_name, street, street_number, zip_code, city)

        return redirect(url_for('customers'))

    # 'customer'-Nutzer mit zugeordnetem Stellenanbieter bekommen statt der Liste
    # aller Stellenanbieter direkt ihr eigenes Bearbeiten-Formular samt eigenen Stellen.
    own_customer_id = session.get("user_customer_id") if session.get("user_role") == "customer" else None
    if own_customer_id:
        return redirect(url_for('edit_customer', customer_id=own_customer_id))

    customers_list, page, per_page, total_pages = _paginate_customers()
    return render_template('index.html', content_template='customer.html', customers=customers_list, editing_customer=None, customer_jobs=None, page=page, per_page=per_page, total_pages=total_pages, per_page_options=CUSTOMERS_PER_PAGE_OPTIONS)


@app.route('/customers/<int:customer_id>/edit', methods=["GET", "POST"])
def edit_customer(customer_id):
    if request.method == "POST":
        if not customer_management_permission(customer_id):
            return redirect(url_for('customers'))

        company_name = request.form.get("company_name", "").strip()
        street = request.form.get("street", "").strip()
        street_number = request.form.get("street_number", "").strip()
        zip_code = request.form.get("zip", "").strip()
        city = request.form.get("city", "").strip()

        if company_name and street and street_number and zip_code and city:
            db.update_customer(customer_id, company_name, street, street_number, zip_code, city)

        return redirect(url_for('customers'))

    customers_list, page, per_page, total_pages = _paginate_customers()
    return render_template('index.html', content_template='customer.html', customers=customers_list, editing_customer=db.get_customer(customer_id), customer_jobs=db.list_jobs(customer_id), page=page, per_page=per_page, total_pages=total_pages, per_page_options=CUSTOMERS_PER_PAGE_OPTIONS)


@app.route('/customers/<int:customer_id>/delete', methods=["POST"])
def delete_customer(customer_id):
    if session.get("user_role") != "admin":
        return redirect(url_for('customers'))
    db.delete_customer(customer_id)
    return redirect(url_for('customers'))


RESUME_DIR = resume_service.RESUME_DIR
JOBOFFER_DIR = joboffer_service.JOBOFFER_DIR


@app.route('/tools/resume', methods=["GET", "POST"])
def generate_resume():
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))

    message = None
    file_url = None
    if request.method == "POST":
        spec = request.form.get("spec", "").strip()
        user_id = request.form.get("user_id")
        if not spec or not user_id:
            message = "Bitte zuerst einen Nutzer wählen und beschreiben, was der Lebenslauf enthalten soll."
        else:
            try:
                resume_id = resume_service.generate_resume_document(openai_client, DEFAULT_MODEL, int(user_id), spec, app.logger)
                file_url = db.get_resume(resume_id)["document_link"]
                message = "Lebenslauf wurde erstellt und dem Nutzer zugeordnet:"
            except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
                app.logger.warning("API error %s: %s", e.status_code, e.body)
                message = "Der Lebenslauf konnte gerade nicht erstellt werden. Bitte später erneut versuchen."

    return render_template('index.html', content_template='resume.html', message=message, file_url=file_url, users=db.list_users())


@app.route('/tools/resume/<path:filename>')
def view_resume(filename):
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))
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


@app.route('/tools/joboffer', methods=["GET", "POST"])
def generate_joboffer():
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))

    message = None
    file_url = None
    if request.method == "POST":
        spec = request.form.get("spec", "").strip()
        customer_id = request.form.get("customer_id")
        if not spec or not customer_id:
            message = "Bitte zuerst einen Stellenanbieter wählen und beschreiben, was das Stellenangebot enthalten soll."
        else:
            try:
                file_url = joboffer_service.generate_joboffer(openai_client, DEFAULT_MODEL, int(customer_id), spec, app.logger)
                message = "Stellenangebot wurde erstellt und als Stelle angelegt:"
            except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
                app.logger.warning("API error %s: %s", e.status_code, e.body)
                message = "Das Stellenangebot konnte gerade nicht erstellt werden. Bitte später erneut versuchen."
            except (json.JSONDecodeError, ValueError) as e:
                app.logger.warning("Unerwartetes KI-Antwortformat: %s", e)
                message = "Das Stellenangebot konnte gerade nicht erstellt werden. Bitte später erneut versuchen."

    return render_template('index.html', content_template='joboffer.html', message=message, file_url=file_url, customers=db.list_customers())

@app.route('/resumes', methods=["GET", "POST"])
def my_resumes():
    if not session.get("user_id"):
        return redirect(url_for('home'))

    message = None
    newest_id = None
    if request.method == "POST":
        uploaded_file = request.files.get("resume_file")
        if uploaded_file and uploaded_file.filename:
            ext = os.path.splitext(uploaded_file.filename)[1].lower()
            if ext not in ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS:
                message = "Bitte eine Datei im PDF-, Word- (.docx) oder LibreOffice-Format (.odt) hochladen."
            else:
                try:
                    newest_id = resume_service.create_resume_from_upload(openai_client, session["user_id"], uploaded_file, app.logger)
                    if newest_id is None:
                        message = "In der Datei konnte kein Text gefunden werden. Bitte eine Datei mit auslesbarem Text hochladen."
                    else:
                        message = "Dein Lebenslauf wurde hochgeladen:"
                except Exception as e:
                    app.logger.warning("Fehler beim Auslesen des hochgeladenen Lebenslaufs: %s", e)
                    message = "Die Datei konnte nicht gelesen werden. Bitte Format und Inhalt prüfen."
        else:
            spec = request.form.get("spec", "").strip()
            if not spec:
                message = "Bitte beschreibe, was dein Lebenslauf enthalten soll."
            else:
                try:
                    newest_id = resume_service.generate_resume_document(openai_client, DEFAULT_MODEL, session["user_id"], spec, app.logger)
                    message = "Dein Lebenslauf wurde erstellt:"
                except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
                    app.logger.warning("API error %s: %s", e.status_code, e.body)
                    message = "Der Lebenslauf konnte gerade nicht erstellt werden. Bitte später erneut versuchen."

    resumes = db.list_resumes_for_user(session["user_id"])
    selected_id = newest_id or request.args.get("resume_id", type=int)
    selected_resume = next((r for r in resumes if r["id"] == selected_id), None) or (resumes[0] if resumes else None)
    matching_jobs = db.find_matching_jobs(selected_resume["embedding"], top_k=5) if selected_resume and selected_resume.get("embedding") else []

    return render_template('index.html', content_template='my_resumes.html', resumes=resumes, selected_resume=selected_resume, matching_jobs=matching_jobs, message=message)


@app.route('/resumes/<int:resume_id>/file')
def my_resume_file(resume_id):
    resume = db.get_resume(resume_id)
    if not resume or resume["user_id"] != session.get("user_id") or not resume["document_link"]:
        return redirect(url_for('home'))
    filename = os.path.basename(resume["document_link"])
    return send_from_directory(RESUME_DIR, filename)


@app.route('/resumes/<int:resume_id>/delete', methods=["POST"])
def delete_resume(resume_id):
    resume = db.get_resume(resume_id)
    if not resume or resume["user_id"] != session.get("user_id"):
        return redirect(url_for('home'))
    if resume["document_link"]:
        file_path = os.path.join(RESUME_DIR, os.path.basename(resume["document_link"]))
        if os.path.exists(file_path):
            os.remove(file_path)
    db.delete_resume(resume_id)
    return redirect(url_for('my_resumes'))


@app.route('/tools/joboffer/<path:filename>')
def view_joboffer(filename):
    # Offen für alle: Stellenangebots-PDFs werden im (ebenfalls öffentlichen)
    # Stellen-Ansichtsmodus für Nicht-Admins eingebettet.
    return send_from_directory(JOBOFFER_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
