import re

from flask import Flask, render_template, request, redirect, url_for
from groq import Groq, APIStatusError
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash
import os

import db
from db import ROLES, DEFAULT_ROLE

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

load_dotenv()

app = Flask(__name__)
client = Groq(api_key=os.environ["GROQ_API_KEY"])
db.init_db()

# Verfügbare Zauberer (KI-Modelle). Key = Groq-Modell-ID, Value = Anzeigename.
# Weitere Modelle können hier einfach ergänzt werden.
AVAILABLE_MODELS = {
    "openai/gpt-oss-20b": "Merlin (Standard, schnell)",
    "openai/gpt-oss-120b": "Gandalf (groß & mächtig)",
    "qwen/qwen3.6-27b": "Rincewind (kompakt & clever)",
    "groq/compound-mini": "Radagast (agentisch, mit Websuche)",
}
DEFAULT_MODEL = "openai/gpt-oss-20b"

AVAILABE_WIZARDS = {
    "openai/gpt-oss-20b": "Merlin",
    "openai/gpt-oss-120b": "Gandalf",
    "qwen/qwen3.6-27b": "Rincewind",
    "groq/compound-mini": "Radagast",
}


@app.route('/', methods=["GET", "POST"])
def home():  # put application's code here
    if request.method == "POST":
        question = request.form.get("question")
        selected_model = request.form.get("model")
        if selected_model not in AVAILABLE_MODELS:
            selected_model = DEFAULT_MODEL

        wizard_name = AVAILABE_WIZARDS.get(selected_model, "Der Zauberer")

        try:
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "user", "content": "Bitte gib eine originelle, nicht zu lange, falsche Antwort auf folgende Frage: " + question}
                ],
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


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
