import json
import re
from datetime import datetime, timedelta

from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from weasyprint import HTML
from groq import Groq, APIStatusError as GroqAPIStatusError
from openai import OpenAI, APIStatusError as OpenAIAPIStatusError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os

import db
from db import ROLES, DEFAULT_ROLE

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?|\n?```\s*$")


def _strip_code_fence(text):
    return CODE_FENCE_RE.sub("", text.strip()).strip()

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
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
    }}


def _log_in_user(user):
    session["user_id"] = user["id"]
    session["user_short_name"] = user["short_name"]
    session["user_role"] = user["role"]

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
    "users": "Nutzerverwaltung: Liste aller Nutzer + neuen Nutzer anlegen, inkl. Rollenvergabe. Nur für Admins, im Hauptmenü als 'Benutzer' verlinkt",
    "edit_user": "Einen bestehenden Nutzer bearbeiten, inkl. Rollenvergabe. Nur für Admins",
    "jobs": "Stellenangebote verwalten, im Hauptmenü als 'Stellenangebote' verlinkt",
    "edit_job": "Ein bestehendes Stellenangebot bearbeiten",
    "delete_job": "Ein Stellenangebot löschen",
    "customers": "Stellenanbieter (Kunden) verwalten, im Hauptmenü als 'Stellenanbieter' verlinkt",
    "edit_customer": "Einen bestehenden Stellenanbieter bearbeiten",
    "delete_customer": "Einen Stellenanbieter löschen",
    "generate_resume": "Lebenslauf generieren. Nur für Admins, erreichbar über das 'Tools'-Menü in der Navigation",
    "generate_joboffer": "Stellenangebot generieren. Nur für Admins, erreichbar über das 'Tools'-Menü in der Navigation",
}


def build_site_map():
    """Erzeugt eine aktuelle Liste aller Routen aus app.url_map, ergänzt um
    die Kurzbeschreibung aus PAGE_DESCRIPTIONS. Läuft bei jeder Anfrage neu,
    damit neue/geänderte Routen sofort ohne Prompt-Pflege sichtbar sind."""
    lines = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
        if rule.endpoint == "static":
            continue
        description = PAGE_DESCRIPTIONS.get(rule.endpoint, "(noch keine Beschreibung hinterlegt)")
        methods = ", ".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        lines.append(f"- {rule.rule} [{methods}] -> {description}")
    return "\n".join(lines)


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
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not (first_name and last_name and short_name and email and password):
            error = "Bitte alle Felder ausfüllen."
        elif password != password_confirm:
            error = "Die Passwörter stimmen nicht überein."
        elif db.get_user_by_email(email):
            error = "Diese E-Mail-Adresse ist bereits registriert."
        else:
            db.create_user(first_name, last_name, short_name, email, generate_password_hash(password), DEFAULT_ROLE)
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

        if first_name and last_name and short_name and email and password:
            db.create_user(first_name, last_name, short_name, email, generate_password_hash(password), role)

        return redirect(url_for('users'))

    return render_template('index.html', content_template='user.html', users=db.list_users(), editing_user=None, roles=ROLES)


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

        if first_name and last_name and short_name and email:
            db.update_user(user_id, first_name, last_name, short_name, email, role, password_hash)

        return redirect(url_for('users'))

    return render_template('index.html', content_template='user.html', users=db.list_users(), editing_user=db.get_user(user_id), roles=ROLES)


@app.route('/jobs', methods=["GET", "POST"])
def jobs():
    if request.method == "POST":
        if session.get("user_role") != "admin":
            return redirect(url_for('jobs'))

        position = request.form.get("position", "").strip()
        content = request.form.get("content", "").strip()
        valid_from = request.form.get("valid_from") or None
        valid_until = request.form.get("valid_until") or None
        customer_id = request.form.get("customer_id")
        zip_code = request.form.get("zip", "").strip() or None
        city = request.form.get("city", "").strip() or None

        if position and content and customer_id:
            db.create_job(position, content, valid_from, valid_until, int(customer_id), zip_code=zip_code, city=city)

        return redirect(url_for('jobs'))

    return render_template('index.html', content_template='jobs.html', jobs=db.list_jobs(), customers=db.list_customers(), editing_job=None)


@app.route('/jobs/<int:job_id>/edit', methods=["GET", "POST"])
def edit_job(job_id):
    if request.method == "POST":
        if session.get("user_role") != "admin":
            return redirect(url_for('jobs'))

        position = request.form.get("position", "").strip()
        content = request.form.get("content", "").strip()
        valid_from = request.form.get("valid_from") or None
        valid_until = request.form.get("valid_until") or None
        customer_id = request.form.get("customer_id")
        zip_code = request.form.get("zip", "").strip() or None
        city = request.form.get("city", "").strip() or None

        if position and content and customer_id:
            db.update_job(job_id, position, content, valid_from, valid_until, int(customer_id), zip_code=zip_code, city=city)

        return redirect(url_for('jobs'))

    return render_template('index.html', content_template='jobs.html', jobs=db.list_jobs(), customers=db.list_customers(), editing_job=db.get_job(job_id))


@app.route('/jobs/<int:job_id>/delete', methods=["POST"])
def delete_job(job_id):
    if session.get("user_role") != "admin":
        return redirect(url_for('jobs'))
    db.delete_job(job_id)
    return redirect(url_for('jobs'))


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

    return render_template('index.html', content_template='customer.html', customers=db.list_customers(), editing_customer=None)


@app.route('/customers/<int:customer_id>/edit', methods=["GET", "POST"])
def edit_customer(customer_id):
    if request.method == "POST":
        if session.get("user_role") != "admin":
            return redirect(url_for('customers'))

        company_name = request.form.get("company_name", "").strip()
        street = request.form.get("street", "").strip()
        street_number = request.form.get("street_number", "").strip()
        zip_code = request.form.get("zip", "").strip()
        city = request.form.get("city", "").strip()

        if company_name and street and street_number and zip_code and city:
            db.update_customer(customer_id, company_name, street, street_number, zip_code, city)

        return redirect(url_for('customers'))

    return render_template('index.html', content_template='customer.html', customers=db.list_customers(), editing_customer=db.get_customer(customer_id))


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


@app.route('/tools/resume', methods=["GET", "POST"])
def generate_resume():
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))

    message = None
    file_url = None
    if request.method == "POST":
        spec = request.form.get("spec", "").strip()
        if not spec:
            message = "Bitte zuerst beschreiben, was der Lebenslauf enthalten soll."
        else:
            try:
                response = openai_client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    messages=[
                        {"role": "system", "content": (
                            "Du erstellst einen Dummy-Lebenslauf mit frei erfundenen, kreativen Personendaten  "
                            "(keine echten Personen) auf Basis der Vorgaben des Nutzers. "
                            "Antworte ausschließlich mit dem fertigen Lebenslauf im HTML-Format, "
                            "ohne zusätzliche Erklärungen."
                        )},
                        {"role": "user", "content": spec},
                    ],
                )
                resume_text = _strip_code_fence(THINK_BLOCK_RE.sub("", response.choices[0].message.content).strip())

                os.makedirs(RESUME_DIR, exist_ok=True)
                filename = f"lebenslauf_{datetime.now():%Y%m%d_%H%M%S}.pdf"
                _write_html_as_pdf(resume_text, os.path.join(RESUME_DIR, filename))

                message = "Lebenslauf wurde erstellt:"
                file_url = url_for('view_resume', filename=filename)
            except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
                app.logger.warning("API error %s: %s", e.status_code, e.body)
                message = "Der Lebenslauf konnte gerade nicht erstellt werden. Bitte später erneut versuchen."

    return render_template('index.html', content_template='resume.html', message=message, file_url=file_url)


@app.route('/tools/resume/<path:filename>')
def view_resume(filename):
    if session.get("user_role") != "admin":
        return redirect(url_for('home'))
    return send_from_directory(RESUME_DIR, filename)


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
                response = openai_client.chat.completions.create(
                    model=DEFAULT_MODEL,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": (
                            "Du erstellst ein Dummy-Stellenangebot mit frei erfundenen, kreativen Angaben "
                            "(kein echtes Unternehmen) auf Basis der Vorgaben des Nutzers. "
                            "Antworte ausschließlich mit einem JSON-Objekt mit genau vier Feldern: "
                            "\"position\" (kurze Stellenbezeichnung als Klartext, z.B. \"Softwareentwickler (m/w/d)\"), "
                            "\"zip\" (Postleitzahl des Arbeitsortes als Text), "
                            "\"city\" (Stadt des Arbeitsortes als Text) und "
                            "\"content\" (das vollständige Stellenangebot als formatiertes HTML mit Überschriften, Aufzählungen etc.), "
                            "ohne zusätzliche Erklärungen außerhalb des JSON."
                        )},
                        {"role": "user", "content": spec},
                    ],
                )
                raw = _strip_code_fence(THINK_BLOCK_RE.sub("", response.choices[0].message.content).strip())
                data = json.loads(raw)
                position = (data.get("position") or "").strip()
                joboffer_text = (data.get("content") or "").strip()
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
                db.create_job(position, joboffer_text, valid_from, valid_until, int(customer_id), file_url, zip_code, city)

                message = "Stellenangebot wurde erstellt und als Stelle angelegt:"
            except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
                app.logger.warning("API error %s: %s", e.status_code, e.body)
                message = "Das Stellenangebot konnte gerade nicht erstellt werden. Bitte später erneut versuchen."
            except (json.JSONDecodeError, ValueError) as e:
                app.logger.warning("Unerwartetes KI-Antwortformat: %s", e)
                message = "Das Stellenangebot konnte gerade nicht erstellt werden. Bitte später erneut versuchen."

    return render_template('index.html', content_template='joboffer.html', message=message, file_url=file_url, customers=db.list_customers())


@app.route('/tools/joboffer/<path:filename>')
def view_joboffer(filename):
    # Offen für alle: Stellenangebots-PDFs werden im (ebenfalls öffentlichen)
    # Stellen-Ansichtsmodus für Nicht-Admins eingebettet.
    return send_from_directory(JOBOFFER_DIR, filename)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
