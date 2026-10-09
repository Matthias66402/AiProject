import os
from datetime import datetime

from flask import url_for

import db
from document_extraction import extract_document_text
from embeddings import embed_text, strip_html_to_text
from services.ai_usage import log_token_usage
from services.pdf_service import write_html_as_pdf
from services.text_utils import DOCUMENT_HTML_RULE, clean_ai_response

RESUME_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "resumes")


def generate_resume_document(openai_client, model, user_id, spec, logger=None):
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
            f"Antworte ausschließlich mit dem fertigen Lebenslauf ({DOCUMENT_HTML_RULE}), "
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
            f"Antworte ausschließlich mit dem fertigen Lebenslauf ({DOCUMENT_HTML_RULE}), "
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
            f"Antworte ausschließlich mit dem fertigen Lebenslauf ({DOCUMENT_HTML_RULE}), "
            "ohne zusätzliche Erklärungen."
        )
        user_content = spec

    response = openai_client.chat.completions.create(
        model=model,
        name="resume_generate",  # Name der Generation in Langfuse
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
    )
    log_token_usage("resume_generate", model, response)
    resume_text = clean_ai_response(response.choices[0].message.content)

    os.makedirs(RESUME_DIR, exist_ok=True)
    filename = f"lebenslauf_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    write_html_as_pdf(resume_text, os.path.join(RESUME_DIR, filename))
    file_url = url_for('view_resume', filename=filename)
    embedding = embed_text(openai_client, strip_html_to_text(resume_text), logger)
    return db.create_resume(resume_text, file_url, user_id, embedding=embedding)


def create_resume_from_upload(openai_client, user_id, uploaded_file, logger=None):
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
    embedding = embed_text(openai_client, strip_html_to_text(resume_text), logger)
    return db.create_resume(resume_text, file_url, user_id, embedding=embedding)
