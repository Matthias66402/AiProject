import os

from groq import Groq, APIStatusError as GroqAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError

import db
from embeddings import embed_text
from services.ai_clients import openai_client
from services.text_utils import strip_think_block

# Verfügbare Zauberer (KI-Modelle). Key = Modell-ID, Value = Anzeigename.
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

# Groq ist optional: ohne (nicht-leeren) GROQ_API_KEY bleibt der Client None und
# darüber erreichbare Modelle werden weiter unten aus allen drei Dicts
# herausgefiltert, statt einen Client mit leerem Key zu erzeugen, der erst
# beim ersten Aufruf fehlschlagen würde.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Welcher Client (Groq oder OpenAI) für welches Modell zuständig ist.
MODEL_CLIENTS = {
    "openai/gpt-oss-20b": groq_client,
    "openai/gpt-oss-120b": groq_client,
    "qwen/qwen3.6-27b": groq_client,
    "groq/compound-mini": groq_client,
    "gpt-5-mini": openai_client,
    "gpt-4o-mini": openai_client,
    "gpt-4.1-mini": openai_client,
}

if groq_client is None:
    _unavailable_models = {model_id for model_id, model_client in MODEL_CLIENTS.items() if model_client is None}
    AVAILABLE_MODELS = {k: v for k, v in AVAILABLE_MODELS.items() if k not in _unavailable_models}
    AVAILABE_MODEL_NAMES = {k: v for k, v in AVAILABE_MODEL_NAMES.items() if k not in _unavailable_models}
    MODEL_CLIENTS = {k: v for k, v in MODEL_CLIENTS.items() if k not in _unavailable_models}


def _relevant_jobs_context(question, logger=None):
    """Sucht per Embedding-Ähnlichkeit (dieselbe pgvector-Suche wie beim
    Resume<->Job-Matching) die zur Frage passendsten, aktuell veröffentlichten
    Stellenangebote und formatiert sie als kurzen Kontext-Block für den
    Assistenten. Gibt None zurück, wenn kein Embedding berechnet werden konnte
    oder keine ausreichend ähnlichen Jobs existieren - der Assistent fällt dann
    auf sein Wissen über die Seitenstruktur zurück, statt Details zu erfinden."""
    embedding = embed_text(openai_client, question, logger)
    if not embedding:
        return None
    # Niedrigerer Schwellwert als beim Resume<->Job-Matching (MIN_MATCH_SIMILARITY,
    # 0.60): dort werden zwei stellenanzeigen-artige Dokumente verglichen, hier
    # eine kurze Frage gegen eine ganze Stellenbeschreibung - das liefert
    # naturgemäß niedrigere Kosinus-Ähnlichkeiten, obwohl der Job inhaltlich
    # passt. Das Modell entscheidet über den Prompt selbst, ob ein Treffer aus
    # der Liste tatsächlich zur Frage passt.
    jobs = db.find_matching_jobs(embedding, top_k=5, min_similarity=0.3)
    if not jobs:
        return None
    lines = []
    for job in jobs:
        city = job.get("city") or "Ort nicht angegeben"
        if job.get("valid_from") or job.get("valid_until"):
            valid = f"gültig {job.get('valid_from') or '?'} bis {job.get('valid_until') or '?'}"
        else:
            valid = "kein Gültigkeitszeitraum hinterlegt"
        lines.append(f"- {job['position']} bei {job['customer_name']} ({city}), {valid}")
    return "\n".join(lines)


def ask_assistant(question, model_id, site_map, logger=None):
    """Stellt eine Frage an das gewählte KI-Modell, mit der aktuellen
    Seitenstruktur (site_map, siehe build_site_map() in app.py) sowie den zur
    Frage passendsten aktuellen Stellenangeboten (siehe _relevant_jobs_context)
    als Systemkontext. Gibt (answer, resolved_model_id) zurück - resolved_model_id
    weicht von model_id ab, wenn dieses unbekannt/nicht verfügbar war."""
    if model_id not in AVAILABLE_MODELS:
        model_id = DEFAULT_MODEL

    wizard_name = AVAILABE_MODEL_NAMES.get(model_id, "KI-Modelle")
    active_client = MODEL_CLIENTS.get(model_id, openai_client)

    jobs_context = _relevant_jobs_context(question, logger)
    jobs_section = (
        "\n\nZur Frage passende, aktuell veröffentlichte Stellenangebote (per Ähnlichkeitssuche ermittelt):\n"
        f"{jobs_context}\n\n"
        "Nutze diese Liste, um konkrete Stellenangebote zu nennen, wenn danach gefragt wird. "
        "Erfinde keine Details (z.B. Anforderungen, Gehalt), die hier nicht stehen - verweise für Details auf die Stellenangebote-Seite. "
        "Falls kein Stellenangebot hier zur Frage passt, sag das offen, statt eines der obigen zu erfinden passend zu machen."
        if jobs_context else ""
    )

    try:
        response = active_client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": (
                    "Du bist ein Assistent, der bei allgemeinen Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung hilft.\n\n"
                    "Das ist die vollständige, aktuelle Seitenstruktur der Website (Route, erlaubte HTTP-Methoden, Zweck):\n"
                    f"{site_map}\n\n"
                    "Diese Liste ist deine einzige Wissensquelle über den Aufbau der Website. "
                    "Wenn eine Seite, ein Menüpunkt oder eine Funktion hier nicht auftaucht, existiert sie nicht - "
                    "erfinde in diesem Fall nichts, sondern sage klar, dass es das nicht gibt. "
                    "Die Website ist noch im Aufbau, die Liste kann sich also häufig ändern - verlasse dich ausschließlich auf die aktuelle Liste oben, nicht auf frühere Annahmen. "
                    "Antworte kurz und knapp in normaler Sprache (z.B. Menüpunkt-Name), ohne die technische Route (z.B. /jobs) zu nennen."
                    f"{jobs_section}"
                )},
                {"role": "user", "content": question},
            ],
        )
        return strip_think_block(response.choices[0].message.content), model_id
    except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
        if e.status_code == 429:
            if logger:
                logger.warning("API 429 details: %s", e.body)
            return f"🧙 {wizard_name} ist müde und hat für heute keine Zaubersprüche mehr übrig. Bitte versuche es morgen erneut.", model_id
        if logger:
            logger.warning("API error %s: %s", e.status_code, e.body)
        return f"🧙 {wizard_name}s Kristallkugel ist gerade getrübt. Bitte versuche es später noch einmal.", model_id
