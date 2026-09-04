import json
import re
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, jsonify
from weasyprint import HTML
from groq import Groq, APIStatusError as GroqAPIStatusError
from openai import OpenAI, APIStatusError as OpenAIAPIStatusError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os

import db
from db import ROLES, DEFAULT_ROLE
from embeddings import embed_text, strip_html_to_text
from document_extraction import extract_document_text, ALLOWED_DOCUMENT_UPLOAD_EXTENSIONS

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?|\n?```\s*$")


def _strip_code_fence(text):
    return CODE_FENCE_RE.sub("", text.strip()).strip()

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
# Begrenzt die Größe hochgeladener Lebenslauf-Dateien (Schutz vor überdimensionierten Uploads).
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024
client = Groq(api_key=os.environ["GROQ_API_KEY"])
openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
db.init_db()


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


def _log_in_user(user):
    session["user_id"] = user["id"]
    session["user_short_name"] = user["short_name"]
    session["user_role"] = user["role"]
    session["user_customer_id"] = user.get("customer_id")

# Verfügbare Zauberer (KI-Modelle). Key = Groq-Modell-ID, Value = Anzeigename.
# Weitere Modelle können hier einfach ergänzt werden.
AVAILABLE_MODELS = {
    "openai/gpt-oss-20b": "Groq - gpt-oss-20b (Standard, schnell)",
    "openai/gpt-oss-120b": "Groq - gpt-oss-120b (groß & mächtig)",
    "qwen/qwen3.6-27b": "Qwen - qwen3.6-27b (kompakt & clever)",
    "groq/compound-mini": "Groq - compound-mini (agentisch, mit Websuche)",
    "gpt-5-mini": "OpenAI - gpt-5-mini",
    "gpt-4o-mini": "OpenAI - gpt-4o-mini",
    "gpt-4.1-mini": "OpenAI - gpt-4.1-mini",
}
DEFAULT_MODEL = "gpt-4.1-mini"

AVAILABE_MODEL_NAMES = {
    "openai/gpt-oss-20b": "Groq - Standard",
    "openai/gpt-oss-120b": "Groq - Mächtig",
    "qwen/qwen3.6-27b": "Qwen - Kompakt",
    "groq/compound-mini": "Groq - agentisch",
    "gpt-5-mini": "OpenAI - gpt-5-mini",
    "gpt-4o-mini": "OpenAI - gpt-4o-mini",
    "gpt-4.1-mini": "OpenAI - gpt-4.1-mini",
}

# Welcher Client (Groq oder OpenAI) für welches Modell zuständig ist.
MODEL_CLIENTS = {
    "openai/gpt-oss-20b": client,
    "openai/gpt-oss-120b": client,
    "qwen/qwen3.6-27b": client,
    "groq/compound-mini": client,
    "gpt-5-mini": openai_client,
    "gpt-4o-mini": openai_client,
    "gpt-4.1-mini": openai_client,
}

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
    return "\n".join(lines)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(app.static_folder, "favicon.ico", mimetype="image/vnd.microsoft.icon")


@app.route('/', methods=["GET", "POST"])
def home():  # put application's code here
    if request.method == "POST":
        question = request.form.get("question")
        selected_model = request.form.get("model")
        if selected_model not in AVAILABLE_MODELS:
            selected_model = DEFAULT_MODEL

        wizard_name = AVAILABE_MODEL_NAMES.get(selected_model, "KI-Modelle")
        active_client = MODEL_CLIENTS.get(selected_model, client)

        try:
            response = active_client.chat.completions.create(
                model=selected_model,
                # messages=[
                #     {"role": "user", "content": "Bitte gib eine originelle, nicht zu lange, falsche Antwort auf folgende Frage: " + question}
                # ],
                messages=[
                    {"role": "system", "content": (
                        "Du bist ein Assistent, der bei allgemeinen Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung hilft.\n\n"
                        "Das ist die vollständige, aktuelle Seitenstruktur der Website (Route, erlaubte HTTP-Methoden, Zweck):\n"
                        f"{build_site_map()}\n\n"
                        "Diese Liste ist deine einzige Wissensquelle über den Aufbau der Website. "
                        "Wenn eine Seite, ein Menüpunkt oder eine Funktion hier nicht auftaucht, existiert sie nicht - "
                        "erfinde in diesem Fall nichts, sondern sage klar, dass es das nicht gibt. "
                        "Die Website ist noch im Aufbau, die Liste kann sich also häufig ändern - verlasse dich ausschließlich auf die aktuelle Liste oben, nicht auf frühere Annahmen. "
                        "Antworte kurz und knapp in normaler Sprache (z.B. Menüpunkt-Name), ohne die technische Route (z.B. /jobs) zu nennen."
                    )},
                    {"role": "user",
                     "content": question}
                ]
            )
            answer = response.choices[0].message.content
            # Manche Modelle (z.B. Qwen) geben ihre Denkschritte in <think>-Tags aus.
            answer = THINK_BLOCK_RE.sub("", answer).strip()
        except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
            if e.status_code == 429:
                app.logger.warning("API 429 details: %s", e.body)
                answer = f"🧙 {wizard_name} ist müde und hat für heute keine Zaubersprüche mehr übrig. Bitte versuche es morgen erneut."
            else:
                app.logger.warning("API error %s: %s", e.status_code, e.body)
                answer = f"🧙 {wizard_name}s Kristallkugel ist gerade getrübt. Bitte versuche es später noch einmal."

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
            _log_in_user(user)
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
            _log_in_user(db.get_user_by_email(email))
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


def _job_management_permission():
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


def _own_customer_for_session():
    """Der dem eingeloggten Nutzer zugeordnete Stellenanbieter (Rolle 'customer'),
    für die Anzeige im Stellen-Formular. None für alle anderen Rollen/ohne Zuordnung."""
    if session.get("user_role") == "customer" and session.get("user_customer_id"):
        return db.get_customer(session["user_customer_id"])
    return None


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
        permission = _job_management_permission()
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
    return render_template('index.html', content_template='jobs.html', jobs=jobs_list, customers=db.list_customers(), editing_job=None, own_customer=_own_customer_for_session(), page=page, per_page=per_page, total_pages=total_pages, per_page_options=JOBS_PER_PAGE_OPTIONS)


@app.route('/jobs/<int:job_id>/edit', methods=["GET", "POST"])
def edit_job(job_id):
    if request.method == "POST":
        job = db.get_job(job_id)
        permission = _job_management_permission()
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

    return render_template('index.html', content_template='jobs.html', jobs=jobs_list, customers=db.list_customers(), editing_job=job, came_from_customer=came_from_customer, matching_resumes=matching_resumes, own_customer=_own_customer_for_session(), page=page, per_page=per_page, total_pages=total_pages, per_page_options=JOBS_PER_PAGE_OPTIONS)


@app.route('/jobs/<int:job_id>/delete', methods=["POST"])
def delete_job(job_id):
    job = db.get_job(job_id)
    permission = _job_management_permission()
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

    customers_list, page, per_page, total_pages = _paginate_customers()
    return render_template('index.html', content_template='customer.html', customers=customers_list, editing_customer=None, customer_jobs=None, page=page, per_page=per_page, total_pages=total_pages, per_page_options=CUSTOMERS_PER_PAGE_OPTIONS)


def _can_manage_customer(customer_id):
    """Admins dürfen jeden Stellenanbieter bearbeiten, Nutzer mit Rolle 'customer'
    nur den ihnen zugeordneten (Anlegen/Löschen bleibt Admins vorbehalten)."""
    role = session.get("user_role")
    if role == "admin":
        return True
    return role == "customer" and session.get("user_customer_id") == customer_id


@app.route('/customers/<int:customer_id>/edit', methods=["GET", "POST"])
def edit_customer(customer_id):
    if request.method == "POST":
        if not _can_manage_customer(customer_id):
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


RESUME_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "resumes")
JOBOFFER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "joboffers")


def _write_html_as_pdf(html_fragment, output_path):
    document = f"<!DOCTYPE html><html><head><meta charset=\"utf-8\"></head><body>{html_fragment}</body></html>"
    HTML(string=document).write_pdf(output_path)


def _generate_resume_document(user_id, spec):
    """Erzeugt per LLM einen Lebenslauf-PDF für user_id auf Basis von spec, speichert
    ihn (inkl. Embedding) als neuen Eintrag in resumes und gibt dessen id zurück.
    Lässt GroqAPIStatusError/OpenAIAPIStatusError zum Aufrufer durch."""
    selected_user = db.get_user(user_id)
    if selected_user and selected_user.get("zip") and selected_user.get("city"):
        system_content = (
            "Du erstellst einen Lebenslauf auf Basis der Vorgaben des Nutzers. "
            "Name und Wohnort sind vorgegeben und müssen unverändert übernommen werden, "
            "alle weiteren Angaben (Ausbildung, Erfahrung, Qualifikationen) darfst du frei "
            "und kreativ erfinden. "
            "Antworte ausschließlich mit dem fertigen Lebenslauf im HTML-Format, "
            "ohne zusätzliche Erklärungen."
        )
        user_content = (
            f"Name: {selected_user['first_name']} {selected_user['last_name']}\n"
            f"Wohnort: {selected_user['zip']} {selected_user['city']}\n\n"
            f"{spec}"
        )
    elif selected_user:
        system_content = (
            "Du erstellst einen Lebenslauf auf Basis der Vorgaben des Nutzers. "
            "Der Name ist vorgegeben und muss unverändert übernommen werden. Einen Wohnort hat "
            "der Nutzer nicht hinterlegt - den darfst du ebenso wie alle weiteren Angaben "
            "(Ausbildung, Erfahrung, Qualifikationen) frei und kreativ erfinden. "
            "Antworte ausschließlich mit dem fertigen Lebenslauf im HTML-Format, "
            "ohne zusätzliche Erklärungen."
        )
        user_content = (
            f"Name: {selected_user['first_name']} {selected_user['last_name']}\n\n"
            f"{spec}"
        )
    else:
        system_content = (
            "Du erstellst einen Dummy-Lebenslauf mit frei erfundenen, kreativen Personendaten  "
            "(keine echten Personen) auf Basis der Vorgaben des Nutzers. "
            "Antworte ausschließlich mit dem fertigen Lebenslauf im HTML-Format, "
            "ohne zusätzliche Erklärungen."
        )
        user_content = spec

    response = openai_client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
    )
    resume_text = _strip_code_fence(THINK_BLOCK_RE.sub("", response.choices[0].message.content).strip())

    os.makedirs(RESUME_DIR, exist_ok=True)
    filename = f"lebenslauf_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    _write_html_as_pdf(resume_text, os.path.join(RESUME_DIR, filename))
    file_url = url_for('view_resume', filename=filename)
    embedding = embed_text(openai_client, strip_html_to_text(resume_text), app.logger)
    return db.create_resume(resume_text, file_url, user_id, embedding=embedding)


def _create_resume_from_upload(user_id, uploaded_file):
    """Liest eine hochgeladene Lebenslauf-Datei (PDF/.docx/.odt) aus, speichert sie
    unverändert samt Embedding auf Basis des ausgelesenen Texts als neuen Eintrag in
    resumes und gibt dessen id zurück. Gibt None zurück, wenn sich kein Text
    extrahieren ließ (z.B. gescanntes PDF ohne Textebene)."""
    resume_text = extract_document_text(uploaded_file.filename, uploaded_file.stream).strip()
    if not resume_text:
        return None

    ext = os.path.splitext(uploaded_file.filename)[1].lower()
    os.makedirs(RESUME_DIR, exist_ok=True)
    filename = f"lebenslauf_{datetime.now():%Y%m%d_%H%M%S}{ext}"
    uploaded_file.stream.seek(0)
    uploaded_file.save(os.path.join(RESUME_DIR, filename))
    file_url = url_for('view_resume', filename=filename)
    embedding = embed_text(openai_client, strip_html_to_text(resume_text), app.logger)
    return db.create_resume(resume_text, file_url, user_id, embedding=embedding)


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
                resume_id = _generate_resume_document(int(user_id), spec)
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
    if not _job_management_permission():
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
        response = openai_client.chat.completions.create(
            model=DEFAULT_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Du bekommst den Text eines hochgeladenen Stellenangebot-Dokuments. Fasse die "
                    "Stellenbeschreibung sinnvoll zusammen und extrahiere, falls im Text eindeutig erkennbar, "
                    "weitere Angaben - erfinde nichts frei hinzu. "
                    "Antworte ausschließlich mit einem JSON-Objekt mit genau vier Feldern: "
                    "\"position\" (kurze Stellenbezeichnung als Klartext, leerer String falls nicht erkennbar), "
                    "\"zip\" (Postleitzahl des Arbeitsortes als Text, leerer String falls nicht erkennbar), "
                    "\"city\" (Stadt des Arbeitsortes als Text, leerer String falls nicht erkennbar) und "
                    "\"content\" (eine sinnvoll gekürzte Zusammenfassung der Stellenbeschreibung als formatiertes "
                    "HTML mit Überschriften/Aufzählungen), ohne zusätzliche Erklärungen außerhalb des JSON."
                )},
                {"role": "user", "content": document_text},
            ],
        )
        raw = _strip_code_fence(THINK_BLOCK_RE.sub("", response.choices[0].message.content).strip())
        data = json.loads(raw)
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
                selected_customer = db.get_customer(int(customer_id))
                if selected_customer:
                    company_block = (
                        f"{selected_customer['company_name']}\n"
                        f"{selected_customer['street']} {selected_customer['street_number']}\n"
                        f"{selected_customer['zip']} {selected_customer['city']}"
                    )
                    system_content = (
                        "Du erstellst ein Stellenangebot auf Basis der Vorgaben des Nutzers. "
                        "Unternehmensname und Adresse sind vorgegeben und müssen unverändert als Kontaktdaten "
                        "im Stellenangebot übernommen werden, alle weiteren Angaben (Aufgaben, Anforderungen, "
                        "Benefits etc.) darfst du frei und kreativ erfinden. "
                        "Antworte ausschließlich mit einem JSON-Objekt mit genau zwei Feldern: "
                        "\"position\" (kurze Stellenbezeichnung als Klartext, z.B. \"Softwareentwickler (m/w/d)\") und "
                        "\"content\" (das vollständige Stellenangebot als formatiertes HTML mit Überschriften, "
                        "Aufzählungen etc., inklusive der vorgegebenen Kontaktdaten), "
                        "ohne zusätzliche Erklärungen außerhalb des JSON."
                    )
                    user_content = f"Unternehmen:\n{company_block}\n\n{spec}"
                else:
                    system_content = (
                        "Du erstellst ein Dummy-Stellenangebot mit frei erfundenen, kreativen Angaben "
                        "(kein echtes Unternehmen) auf Basis der Vorgaben des Nutzers. "
                        "Antworte ausschließlich mit einem JSON-Objekt mit genau vier Feldern: "
                        "\"position\" (kurze Stellenbezeichnung als Klartext, z.B. \"Softwareentwickler (m/w/d)\"), "
                        "\"zip\" (Postleitzahl des Arbeitsortes als Text), "
                        "\"city\" (Stadt des Arbeitsortes als Text) und "
                        "\"content\" (das vollständige Stellenangebot als formatiertes HTML mit Überschriften, Aufzählungen etc.), "
                        "ohne zusätzliche Erklärungen außerhalb des JSON."
                    )
                    user_content = spec

                response = openai_client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content},
                    ],
                )
                raw = _strip_code_fence(THINK_BLOCK_RE.sub("", response.choices[0].message.content).strip())
                data = json.loads(raw)
                position = (data.get("position") or "").strip()
                joboffer_text = (data.get("content") or "").strip()
                if selected_customer:
                    zip_code = selected_customer["zip"]
                    city = selected_customer["city"]
                else:
                    zip_code = (data.get("zip") or "").strip() or None
                    city = (data.get("city") or "").strip() or None
                valid_from = datetime.now().date()
                valid_until = valid_from + timedelta(days=30)

                if not position or not joboffer_text:
                    raise ValueError("Antwort enthielt kein position/content-Feld.")

                os.makedirs(JOBOFFER_DIR, exist_ok=True)
                filename = f"stellenangebot_{datetime.now():%Y%m%d_%H%M%S}.pdf"
                _write_html_as_pdf(joboffer_text, os.path.join(JOBOFFER_DIR, filename))
                file_url = url_for('view_joboffer', filename=filename)
                embedding = embed_text(openai_client, f"{position}\n\n{strip_html_to_text(joboffer_text)}", app.logger)
                db.create_job(position, joboffer_text, valid_from, valid_until, int(customer_id), file_url, zip_code, city, embedding=embedding)

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
                    newest_id = _create_resume_from_upload(session["user_id"], uploaded_file)
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
                    newest_id = _generate_resume_document(session["user_id"], spec)
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
