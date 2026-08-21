import re

from flask import Flask, render_template, request
from groq import Groq, APIStatusError
from dotenv import load_dotenv
import os

THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)

load_dotenv()

app = Flask(__name__)
client = Groq(api_key=os.environ["GROQ_API_KEY"])

# Verfügbare Zauberer (KI-Modelle). Key = Groq-Modell-ID, Value = Anzeigename.
# Weitere Modelle können hier einfach ergänzt werden.
AVAILABLE_MODELS = {
    "openai/gpt-oss-20b": "Merlin (Standard, schnell)",
    "openai/gpt-oss-120b": "Gandalf (groß & mächtig)",
    "qwen/qwen3.6-27b": "Rincewind (kompakt & clever)",
    "groq/compound-mini": "Radagast (agentisch, mit Websuche)",
}
DEFAULT_MODEL = "openai/gpt-oss-20b"


@app.route('/', methods=["GET", "POST"])
def home():  # put application's code here
    if request.method == "POST":
        question = request.form.get("question")
        selected_model = request.form.get("model")
        if selected_model not in AVAILABLE_MODELS:
            selected_model = DEFAULT_MODEL

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
                answer = "🧙 Merlin ist müde und hat für heute keine Zaubersprüche mehr übrig. Bitte versuche es morgen erneut."
            else:
                app.logger.warning("Groq API error %s: %s", e.status_code, e.body)
                answer = "🧙 Merlins Kristallkugel ist gerade getrübt. Bitte versuche es später noch einmal."

        return render_template('index.html', answer=answer, models=AVAILABLE_MODELS, selected_model=selected_model)
    else:
        return render_template('index.html', models=AVAILABLE_MODELS, selected_model=DEFAULT_MODEL)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)
