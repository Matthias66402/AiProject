from openai import APIError as OpenAIAPIError

from embeddings import embed_text, strip_html_to_text
from services.ai_usage import log_token_usage

# Modell für die Profil-Erzeugung - bewusst fest statt des im Assistenten
# wählbaren Modells: Profile aller Jobs und Lebensläufe sollen einheitlich
# formuliert sein, sonst sinkt die Vergleichbarkeit der Embeddings.
PROFILE_MODEL = "gpt-4.1-mini"

_KIND_LABELS = {"job": "Stellenangebot", "resume": "Lebenslauf"}

_PROFILE_SYSTEM_PROMPT = (
    "Du erstellst aus einem {label} ein neutrales Matching-Profil. Es wird per "
    "Embedding mit Profilen der Gegenseite verglichen (Lebensläufe mit Stellenangeboten), "
    "daher nutzen beide Seiten exakt dasselbe Format:\n"
    "Rolle: <Berufsbezeichnung(en) bzw. ausgeschriebene Position>\n"
    "Berufsfeld: <Fachrichtung und Branche>\n"
    "Fachkenntnisse: <fachliche Kenntnisse und Tätigkeiten, kommagetrennt>\n"
    "Werkzeuge und Technologien: <Software, Tools, Methoden, Maschinen, kommagetrennt>\n"
    "Erfahrung: <Berufserfahrung in Jahren und Seniorität, z.B. Berufseinstieg, Fachkraft, Senior, Leitung>\n"
    "Ausbildung: <Abschlüsse, Ausbildungen, Zertifikate>\n"
    "Sprachen: <Sprachen mit Niveau>\n\n"
    "Regeln: Übernimm nur, was im Text steht - nichts erfinden oder ableiten. Gibt der "
    "Text zu einer Zeile nichts her, lass die ganze Zeile weg (kein 'keine Angabe' o.ä. - "
    "solche Füllzeilen würden unpassende Profile einander ähnlicher machen). Lass außerdem "
    "weg: Namen, Kontaktdaten, Adressen und Orte, "
    "Geburtsdaten, Hobbys, Arbeitgeber- und Firmennamen, Unternehmensbeschreibungen, "
    "Benefits, Gehalt, Bewerbungsablauf und Gültigkeitsdaten. Schreibe auf Deutsch; "
    "Fachbegriffe und Tool-Namen in ihrer üblichen Schreibweise. Antworte ausschließlich "
    "mit den Zeilen des Profils."
)


def job_profile_input(position, content):
    """Eingabetext für das Matching-Profil einer Stelle: Position + Beschreibung
    als reiner Text (content ist HTML aus dem Rich-Text-Editor)."""
    return f"Position: {position}\n\n{strip_html_to_text(content)}"


def build_match_profile(openai_client, kind, text, logger=None):
    """Lässt die KI aus dem reinen Text eines Stellenangebots (kind='job') bzw.
    Lebenslaufs (kind='resume') ein einheitliches Matching-Profil erzeugen:
    nur Rolle, Berufsfeld, Kenntnisse, Werkzeuge, Erfahrung, Ausbildung und
    Sprachen - ohne persönliche Daten, Ort, Benefits u.ä., die das Embedding
    sonst verwässern. Ort und Gültigkeit werden stattdessen als harte Filter
    im SQL geprüft (models/job.py). Gibt None zurück, wenn kein Text vorliegt
    oder die API einen Fehler meldet."""
    if not text or not text.strip():
        return None
    try:
        response = openai_client.chat.completions.create(
            model=PROFILE_MODEL,
            name=f"match_profile_{kind}",  # Name der Generation in Langfuse
            temperature=0,
            messages=[
                {"role": "system", "content": _PROFILE_SYSTEM_PROMPT.format(label=_KIND_LABELS[kind])},
                {"role": "user", "content": text},
            ],
        )
    except OpenAIAPIError as e:
        if logger:
            logger.warning("Matching-Profil-API-Fehler: %s", e)
        return None
    log_token_usage(f"match_profile_{kind}", PROFILE_MODEL, response)
    return (response.choices[0].message.content or "").strip() or None


def profile_and_embed(openai_client, kind, text, logger=None):
    """Erzeugt das Matching-Profil zu text und dessen Embedding - Grundlage
    für alles Matching zwischen Lebensläufen und Stellenangeboten. Gibt
    (match_profile, embedding) zurück; schlägt einer der Schritte fehl, beide
    als None (bewusst kein Rückfall auf ein Embedding des Rohtexts, das mit
    den Profil-Embeddings nicht vergleichbar wäre). backfill_embeddings.py
    holt fehlende Profile später nach."""
    profile = build_match_profile(openai_client, kind, text, logger)
    if profile is None:
        return None, None
    embedding = embed_text(openai_client, profile, logger)
    if embedding is None:
        return None, None
    return profile, embedding
