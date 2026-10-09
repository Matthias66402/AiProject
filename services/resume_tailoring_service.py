import json
import os
from datetime import datetime

from flask import url_for

import db
from embeddings import strip_html_to_text
from services.ai_usage import log_token_usage
from services.match_profile_service import profile_and_embed
from services.pdf_service import write_html_as_pdf
from services.resume_service import RESUME_DIR
from services.text_utils import DOCUMENT_HTML_RULE, clean_ai_response, compact_whitespace

_TAILOR_SYSTEM_PROMPT = (
    "Du passt einen bestehenden Lebenslauf an ein konkretes Stellenangebot an, damit die "
    "Eignung für genau diese Stelle besser sichtbar wird. Dabei gilt streng: Du darfst "
    "NICHTS erfinden. Verwende ausschließlich Fakten, die im Original-Lebenslauf stehen.\n"
    "Erlaubt: umformulieren, umsortieren, für die Stelle relevante Erfahrungen und "
    "Kenntnisse hervorheben und ausführlicher darstellen, weniger relevante kürzen oder "
    "weglassen, ein kurzes Profil oben aus den vorhandenen Angaben formulieren, Begriffe "
    "aus dem Stellenangebot verwenden - aber nur dort, wo das Original dieselbe Tätigkeit "
    "oder Kenntnis tatsächlich belegt.\n"
    "Verboten: neue Kenntnisse, Tools, Tätigkeiten, Arbeitgeber, Stationen, Abschlüsse, "
    "Zertifikate, Sprachen, Zahlen, Zeiträume oder Erfolge hinzufügen; Niveaus oder "
    "Dauer übertreiben; Anforderungen der Stelle ergänzen, die im Original fehlen.\n"
    "Name, Kontaktdaten, Zeiträume und Arbeitgeber unverändert übernehmen. Schreibe in "
    "der Sprache des Original-Lebenslaufs.\n"
    f"Antworte ausschließlich mit dem fertigen Lebenslauf ({DOCUMENT_HTML_RULE}), "
    "ohne zusätzliche Erklärungen."
)

_CHECK_SYSTEM_PROMPT = (
    "Du prüfst, ob ein überarbeiteter Lebenslauf Angaben enthält, die im Original-"
    "Lebenslauf nicht belegt sind (neue Kenntnisse, Tätigkeiten, Stationen, Abschlüsse, "
    "Zahlen, Zeiträume, übertriebene Niveaus). Umformulierungen, Kürzungen und "
    "Umsortierungen sind erlaubt und keine Abweichung. Antworte ausschließlich mit JSON "
    'der Form {"unsupported": ["<kurze Beschreibung der unbelegten Angabe>", ...]} - '
    "eine leere Liste, wenn alles belegt ist. Schreibe in der Sprache des Lebenslaufs."
)


def _job_text(job):
    return f"Position: {job['position']}\n\n{strip_html_to_text(job['content'])}"


def _check_unsupported_claims(openai_client, model, original, draft_html, logger=None):
    """Zweiter KI-Aufruf: listet Aussagen des Entwurfs ohne Beleg im Original.
    Liefert bei unlesbarer Antwort eine Liste mit einem Hinweis statt eines
    Fehlers, damit die Vorschau trotzdem erscheint."""
    response = openai_client.chat.completions.create(
        model=model,
        name="resume_tailor_check",  # Name der Generation in Langfuse
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CHECK_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"ORIGINAL-LEBENSLAUF:\n{original}\n\n"
                f"ÜBERARBEITETER LEBENSLAUF:\n{compact_whitespace(strip_html_to_text(draft_html))}"
            )},
        ],
    )
    log_token_usage("resume_tailor_check", model, response)
    try:
        unsupported = json.loads(clean_ai_response(response.choices[0].message.content)).get("unsupported", [])
        return [str(item) for item in unsupported if str(item).strip()]
    except (ValueError, AttributeError) as e:
        if logger:
            logger.warning("Prüfschritt beim Zuschneiden nicht auswertbar: %s", e)
        return ["Die automatische Prüfung konnte nicht ausgewertet werden - bitte den Entwurf selbst gegenlesen."]


def draft_tailored_resume(openai_client, model, resume, job, logger=None):
    """Erzeugt einen auf job zugeschnittenen Entwurf von resume, ohne ihn zu
    speichern: HTML-Entwurf, Liste unbelegter Angaben (Prüfschritt) sowie die
    Ähnlichkeit zur Stelle vor und nach dem Zuschneiden. Lässt
    GroqAPIStatusError/OpenAIAPIStatusError zum Aufrufer durch."""
    original = compact_whitespace(resume["content"])
    response = openai_client.chat.completions.create(
        model=model,
        name="resume_tailor",  # Name der Generation in Langfuse
        messages=[
            {"role": "system", "content": _TAILOR_SYSTEM_PROMPT},
            {"role": "user", "content": f"STELLENANGEBOT:\n{_job_text(job)}\n\nORIGINAL-LEBENSLAUF:\n{original}"},
        ],
    )
    log_token_usage("resume_tailor", model, response)
    draft_html = clean_ai_response(response.choices[0].message.content)

    unsupported = _check_unsupported_claims(openai_client, model, original, draft_html, logger)
    # Wie beim Speichern über das Matching-Profil, damit similarity_after mit
    # den gespeicherten Embeddings vergleichbar ist.
    _, draft_embedding = profile_and_embed(openai_client, "resume", strip_html_to_text(draft_html), logger)
    return {
        "draft_html": draft_html,
        "unsupported": unsupported,
        "similarity_before": db.job_similarity(job["id"], resume.get("embedding")),
        "similarity_after": db.job_similarity(job["id"], draft_embedding),
    }


def save_tailored_resume(openai_client, user_id, job_id, html, logger=None):
    """Speichert einen (in der Vorschau bestätigten) zugeschnittenen Lebenslauf
    als neue Version mit target_job_id = job_id: PDF + Embedding, wie bei
    generate_resume_document. Gibt die id des neuen Eintrags zurück."""
    os.makedirs(RESUME_DIR, exist_ok=True)
    filename = f"lebenslauf_{datetime.now():%Y%m%d_%H%M%S}.pdf"
    write_html_as_pdf(html, os.path.join(RESUME_DIR, filename))
    file_url = url_for('view_resume', filename=filename)
    match_profile, embedding = profile_and_embed(openai_client, "resume", strip_html_to_text(html), logger)
    return db.create_resume(html, file_url, user_id, match_profile=match_profile, embedding=embedding,
                            target_job_id=job_id)
