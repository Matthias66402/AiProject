import re
from datetime import date

from embeddings import strip_html_to_text
from services.ai_usage import log_token_usage
from services.text_utils import LETTER_HTML_RULE, clean_ai_response, compact_whitespace

_COVER_LETTER_SYSTEM_PROMPT = (
    "Du schreibst ein Motivationsschreiben (Anschreiben) für eine Bewerbung auf ein konkretes "
    "Stellenangebot, auf Basis des Lebenslaufs der Bewerberin bzw. des Bewerbers. Dabei gilt "
    "streng: Du darfst NICHTS erfinden. Verwende ausschließlich Fakten, die im Lebenslauf "
    "stehen - keine neuen Kenntnisse, Tätigkeiten, Stationen, Abschlüsse, Zahlen oder Erfolge.\n"
    "Inhalt: Bezug auf die konkrete Stelle und das Unternehmen, warum die Person passt (die "
    "zwei bis drei für die Stelle wichtigsten, im Lebenslauf belegten Erfahrungen und "
    "Kenntnisse mit Bezug auf die Anforderungen), Motivation für genau diese Stelle, kurzer "
    "Schluss mit Bitte um ein Gespräch. Höchstens eine Seite, ca. 250-350 Wörter Fließtext, "
    "sachlich-freundlicher Ton, keine Floskelketten. Anforderungen der Stelle, die der "
    "Lebenslauf nicht abdeckt, nicht behaupten - höchstens Lernbereitschaft betonen.\n"
    "Absender (Name, Anschrift, Kontaktdaten) wörtlich aus dem Lebenslauf übernehmen - Straße "
    "und Hausnummer nur, wenn sie dort stehen, sonst nur PLZ und Ort; niemals eine Adresse, "
    "Telefonnummer oder E-Mail erfinden oder Platzhalter einsetzen. Empfänger mit der "
    "angegebenen Anschrift des Unternehmens. Ist keine Ansprechperson bekannt, die Anrede "
    "'Sehr geehrte Damen und Herren' verwenden. Schreibe in der Sprache des Stellenangebots.\n"
    f"Antworte ausschließlich mit dem fertigen Schreiben ({LETTER_HTML_RULE}), "
    "ohne zusätzliche Erklärungen."
)

_PARAGRAPH_RE = re.compile(r"<p>(.*?)</p>", re.DOTALL)


def _mark_letter_parts(html, today):
    """Setzt die Klassen für das Brief-Layout (Stylesheets in pdf_service und
    static/style.css). Die KI liefert bewusst kein class-Attribut
    (LETTER_HTML_RULE), die Teile ergeben sich aus der Reihenfolge:
    letter-right   - Absender (erster Absatz) und Ort/Datum (über das vorgegebene Datum)
    letter-subject - Betreff (erster Absatz, der mit <strong> beginnt), Abstand davor/danach
    letter-signature - Name (letzter Absatz), Abstand zur Grußformel"""
    paragraphs = list(_PARAGRAPH_RE.finditer(html))
    if len(paragraphs) < 2:
        return html
    classes = {paragraphs[0].start(): "letter-right", paragraphs[-1].start(): "letter-signature"}
    date_paragraph = next((m for m in paragraphs if today in m.group(1)), None)
    if date_paragraph:
        classes[date_paragraph.start()] = "letter-right"
    subject = next((m for m in paragraphs[1:-1] if m.group(1).lstrip().startswith("<strong>")), None)
    if subject:
        classes[subject.start()] = "letter-subject"
    for start in sorted(classes, reverse=True):
        html = f'{html[:start]}<p class="{classes[start]}">{html[start + len("<p>"):]}'
    return html


def draft_cover_letter(openai_client, model, resume, job, customer):
    """Erzeugt ein Motivationsschreiben (HTML) aus resume für job, ohne es zu
    speichern; customer liefert die Empfängeranschrift. Lässt
    GroqAPIStatusError/OpenAIAPIStatusError zum Aufrufer durch."""
    address = ", ".join(filter(None, [
        " ".join(filter(None, [customer.get("street"), customer.get("street_number")])),
        " ".join(filter(None, [customer.get("zip"), customer.get("city")])),
    ]))
    job_text = (
        f"Unternehmen: {job['customer_name']}\n"
        f"Anschrift: {address}\n"
        f"Position: {job['position']}\n\n{compact_whitespace(strip_html_to_text(job['content']))}"
    )
    today = f"{date.today():%d.%m.%Y}"
    response = openai_client.chat.completions.create(
        model=model,
        name="cover_letter",  # Name der Generation in Langfuse
        messages=[
            {"role": "system", "content": _COVER_LETTER_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"DATUM: {today}\n\n"
                f"STELLENANGEBOT:\n{job_text}\n\n"
                f"LEBENSLAUF:\n{compact_whitespace(resume['content'])}"
            )},
        ],
    )
    log_token_usage("cover_letter", model, response)
    return _mark_letter_parts(clean_ai_response(response.choices[0].message.content), today)
