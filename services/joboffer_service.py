import json
import os
from datetime import date, datetime, timedelta

from flask import url_for

import db
from embeddings import embed_text, strip_html_to_text
from services.ai_usage import log_token_usage
from services.pdf_service import write_html_as_pdf
from services.text_utils import SIMPLE_HTML_RULE, clean_ai_response, compact_whitespace

JOBOFFER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "joboffers")


def extract_joboffer_from_text(openai_client, model, document_text):
    """Lässt die KI den Text eines hochgeladenen Stellenangebot-Dokuments zusammenfassen
    und, falls eindeutig erkennbar, Position/PLZ/Stadt sowie den Gültigkeitszeitraum
    (valid_from/valid_until) extrahieren. Gibt das geparste JSON-Dict zurück, die
    Datumsfelder bereits geprüft als YYYY-MM-DD oder "". Lässt GroqAPIStatusError/OpenAIAPIStatusError sowie
    json.JSONDecodeError/ValueError (bei unerwartetem Antwortformat) zum Aufrufer durch."""
    response = openai_client.chat.completions.create(
        model=model,
        name="joboffer_extract",  # Name der Generation in Langfuse
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Du erhältst den Text eines Stellenangebots.\n\n"
                "Fasse die Stellenbeschreibung sinnvoll zusammen.\n"
                "Extrahiere, falls im Text eindeutig erkennbar: Position, PLZ, Stadt sowie den "
                "Gültigkeitszeitraum der Ausschreibung. Erfinde nichts hinzu.\n"
                f"Heutiges Datum (für Angaben ohne Jahreszahl): {date.today().isoformat()}\n"
                "Antworte nur mit einem JSON-Objekt mit genau diesen Feldern:\n"
                "\"position\": kurze Stellenbezeichnung als Text, sonst \"\"\n"
                "\"zip\": Postleitzahl des Arbeitsortes als Text, sonst \"\"\n"
                "\"city\": Stadt des Arbeitsortes als Text, sonst \"\"\n"
                "\"valid_from\": Veröffentlichungs-/Ausschreibungsdatum als YYYY-MM-DD, sonst \"\"\n"
                "\"valid_until\": Bewerbungsfrist bzw. Ende der Ausschreibung als YYYY-MM-DD, sonst \"\" "
                "(nicht das Ende einer Befristung des Arbeitsverhältnisses, nicht das Eintrittsdatum)\n"
                f"\"content\": gekürzte Zusammenfassung als HTML mit Überschriften/Aufzählungen ({SIMPLE_HTML_RULE}).\n"
                "Keine zusätzliche Ausgabe außerhalb dieses JSON."
            )},
            {"role": "user", "content": compact_whitespace(document_text)},
        ],
    )
    log_token_usage("joboffer_extract", model, response)
    raw = clean_ai_response(response.choices[0].message.content)
    data = json.loads(raw)
    for field in ("valid_from", "valid_until"):
        data[field] = _iso_date_or_empty(data.get(field))
    if data["valid_from"] and data["valid_until"] and data["valid_from"] > data["valid_until"]:
        data["valid_from"] = ""
    return data


def _iso_date_or_empty(value):
    """Datumsangabe der KI prüfen: gültiges YYYY-MM-DD bleibt, alles andere wird ""."""
    try:
        return date.fromisoformat(str(value or "").strip()).isoformat()
    except ValueError:
        return ""


def generate_joboffer(openai_client, model, customer_id, spec, logger=None):
    """Erzeugt per LLM ein Stellenangebot für customer_id (oder einen frei erfundenen
    Dummy-Anbieter, falls customer_id nicht existiert) auf Basis von spec, legt dafür
    automatisch einen passenden Eintrag in jobs an und gibt den file_url des erzeugten
    PDFs zurück. Lässt GroqAPIStatusError/OpenAIAPIStatusError sowie
    json.JSONDecodeError/ValueError (bei unerwartetem Antwortformat oder fehlendem
    position/content-Feld) zum Aufrufer durch."""
    selected_customer = db.get_customer(customer_id)
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
            f"Aufzählungen etc., inklusive der vorgegebenen Kontaktdaten; {SIMPLE_HTML_RULE}), "
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
            f"\"content\" (das vollständige Stellenangebot als formatiertes HTML mit Überschriften, Aufzählungen etc.; {SIMPLE_HTML_RULE}), "
            "ohne zusätzliche Erklärungen außerhalb des JSON."
        )
        user_content = spec

    response = openai_client.chat.completions.create(
        model=model,
        name="joboffer_generate",  # Name der Generation in Langfuse
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
    )
    log_token_usage("joboffer_generate", model, response)
    raw = clean_ai_response(response.choices[0].message.content)
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
    write_html_as_pdf(joboffer_text, os.path.join(JOBOFFER_DIR, filename))
    file_url = url_for('view_joboffer', filename=filename)
    embedding = embed_text(openai_client, f"{position}\n\n{strip_html_to_text(joboffer_text)}", logger)
    db.create_job(position, joboffer_text, valid_from, valid_until, customer_id, file_url, zip_code, city, embedding=embedding)

    return file_url
