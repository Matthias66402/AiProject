import re

from flask import Flask, render_template, request, redirect, url_for, session
from groq import Groq, APIStatusError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
import os

import db
from db import ROLES, DEFAULT_ROLE

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]
client = Groq(api_key=os.environ["GROQ_API_KEY"])
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
    "openai/gpt-oss-20b": "Openai - gpt-oss-20b (Standard, schnell)",
    "openai/gpt-oss-120b": "Openai - gpt-oss-120b (groß & mächtig)",
    "qwen/qwen3.6-27b": "Qwen - qwen3.6-27b (kompakt & clever)",
    "groq/compound-mini": "Groq - compound-mini (agentisch, mit Websuche)",
}
DEFAULT_MODEL = "openai/gpt-oss-20b"

AVAILABE_WIZARDS = {
    "openai/gpt-oss-20b": "Openai - Standard",
    "openai/gpt-oss-120b": "Openai - Mächtig",
    "qwen/qwen3.6-27b": "Qwen - Kompakt",
    "groq/compound-mini": "Groq - agentisch",
}


@app.route('/', methods=["GET", "POST"])
def home():  # put application's code here
    if request.method == "POST":
        question = request.form.get("question")
        selected_model = request.form.get("model")
        if selected_model not in AVAILABLE_MODELS:
            selected_model = DEFAULT_MODEL

        wizard_name = AVAILABE_WIZARDS.get(selected_model, "KI-Modelle")

        try:
            response = client.chat.completions.create(
                model=selected_model,
                # messages=[
                #     {"role": "user", "content": "Bitte gib eine originelle, nicht zu lange, falsche Antwort auf folgende Frage: " + question}
                # ],
                messages=[
                    {"role": "system", "content": "Du bist ein Assistent, der bei allgemeinen Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung. Für Fragen zum Verorten der Routen bitte die Routen von app.py bzw. von templates/navigation.html berücksichtigen - nichts dazu erfinden. Bitte kurz und knapp antworten ohne Hintergrundinformation zur genauen Route."},
                    {"role": "user",
                     "content": question}
                ]
            )
            answer = response.choices[0].message.content
            # Manche Modelle (z.B. Qwen) geben ihre Denkschritte in <think>-Tags aus.
            answer = THINK_BLOCK_RE.sub("", answer).strip()
        except APIStatusError as e:
            if e.status_code == 429:
                app.logger.warning("Groq 429 details: %s", e.body)
                answer = f"🧙 {wizard_name} ist müde und hat für heute keine Zaubersprüche mehr übrig. Bitte versuche es morgen erneut."
            else:
                app.logger.warning("Groq API error %s: %s", e.status_code, e.body)
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

        return redirect(url_for('jobs'))

    return render_template('index.html', content_template='jobs.html', users=db.list_users(), editing_user=None, roles=ROLES)

@app.route('/customers', methods=["GET", "POST"])
def customers():
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

    return render_template('index.html', content_template='customer.html', users=db.list_users(), editing_user=None, roles=ROLES)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
