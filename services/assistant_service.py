from groq import APIStatusError as GroqAPIStatusError
from openai import APIStatusError as OpenAIAPIStatusError

import db
from embeddings import embed_text
from services.ai_clients import openai_client, groq_client
from services.ai_usage import log_token_usage
from services.text_utils import strip_think_block

# Verfügbare Zauberer (KI-Modelle). Key = Modell-ID, Value = Anzeigename.
# Weitere Modelle können hier einfach ergänzt werden.
AVAILABLE_MODELS = {
    "openai/gpt-oss-20b": "Groq - gpt-oss-20b (Standard, schnell)",
    "openai/gpt-oss-120b": "Groq - gpt-oss-120b (groß & mächtig)",
    "qwen/qwen3.8-27b": "Qwen - qwen3.8-27b (kompakt & clever)",
    "gpt-5-mini": "OpenAI - gpt-5-mini",
    "gpt-4o-mini": "OpenAI - gpt-4o-mini",
    "gpt-4.1-mini": "OpenAI - gpt-4.1-mini",
}
DEFAULT_MODEL = "gpt-4.1-mini"

AVAILABE_MODEL_NAMES = {
    "openai/gpt-oss-20b": "Groq - Standard",
    "openai/gpt-oss-120b": "Groq - Mächtig",
    "qwen/qwen3.8-27b": "Qwen - Kompakt",
    "gpt-5-mini": "OpenAI - gpt-5-mini",
    "gpt-4o-mini": "OpenAI - gpt-4o-mini",
    "gpt-4.1-mini": "OpenAI - gpt-4.1-mini",
}

# Groq ist optional: ohne (nicht-leeren) GROQ_API_KEY ist groq_client None
# (services/ai_clients.py) und darüber erreichbare Modelle werden weiter unten
# aus allen drei Dicts herausgefiltert.

# Welcher Client (Groq oder OpenAI) für welches Modell zuständig ist.
MODEL_CLIENTS = {
    "openai/gpt-oss-20b": groq_client,
    "openai/gpt-oss-120b": groq_client,
    "qwen/qwen3.8-27b": groq_client,
    "gpt-5-mini": openai_client,
    "gpt-4o-mini": openai_client,
    "gpt-4.1-mini": openai_client,
}

# Modelle, die reasoning_effort unterstützen (siehe ask_assistant).
REASONING_MODELS = {"openai/gpt-oss-20b", "openai/gpt-oss-120b", "gpt-5-mini"}

if groq_client is None:
    _unavailable_models = {model_id for model_id, model_client in MODEL_CLIENTS.items() if model_client is None}
    AVAILABLE_MODELS = {k: v for k, v in AVAILABLE_MODELS.items() if k not in _unavailable_models}
    AVAILABE_MODEL_NAMES = {k: v for k, v in AVAILABE_MODEL_NAMES.items() if k not in _unavailable_models}
    MODEL_CLIENTS = {k: v for k, v in MODEL_CLIENTS.items() if k not in _unavailable_models}


# Niedrigerer Schwellwert als MIN_MATCH_SIMILARITY (0.71, fürs Resume<->Job-
# Matching zwischen zwei Matching-Profilen gleichen Formats): hier steht eine
# kurze Frage gegen ein ganzes Profil, das liefert naturgemäß
# niedrigere Kosinus-Ähnlichkeiten, obwohl der Treffer inhaltlich passt. Das
# Modell entscheidet über den Prompt selbst, ob ein Treffer aus der Liste
# tatsächlich zur Frage passt.
_QUESTION_MATCH_MIN_SIMILARITY = 0.3


def _relevant_jobs_context(embedding, logger=None):
    """Sucht per Embedding-Ähnlichkeit (dieselbe pgvector-Suche wie beim
    Resume<->Job-Matching) die zur Frage passendsten, aktuell veröffentlichten
    Stellenangebote und formatiert sie als kurzen Kontext-Block für den
    Assistenten. Gibt None zurück, wenn kein Embedding vorliegt oder keine
    ausreichend ähnlichen Jobs existieren - der Assistent fällt dann auf sein
    Wissen über die Seitenstruktur zurück, statt Details zu erfinden."""
    if not embedding:
        return None
    jobs = db.find_matching_jobs(embedding, top_k=5, min_similarity=_QUESTION_MATCH_MIN_SIMILARITY)
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


def _relevant_resumes_context(embedding, logger=None):
    """Analog zu _relevant_jobs_context, aber für Lebensläufe (find_matching_resumes):
    sucht die zur Frage passendsten Lebensläufe samt zugehöriger Nutzer. Gibt
    None zurück, wenn kein Embedding vorliegt oder nichts ausreichend ähnlich ist."""
    if not embedding:
        return None
    resumes = db.find_matching_resumes(embedding, top_k=5, min_similarity=_QUESTION_MATCH_MIN_SIMILARITY)
    if not resumes:
        return None
    lines = []
    for resume in resumes:
        name = f"{resume['first_name']} {resume['last_name']}".strip() or resume["short_name"]
        created = resume["created_at"].date().isoformat() if resume.get("created_at") else "?"
        lines.append(f"- {name} (Kurzname: {resume['short_name']}), Lebenslauf vom {created}")
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

    # Eine Embedding-Berechnung für beide Ähnlichkeitssuchen (Jobs + Lebensläufe)
    # wiederverwenden, statt sie doppelt anzufragen.
    question_embedding = embed_text(openai_client, question, logger)

    jobs_context = _relevant_jobs_context(question_embedding, logger)
    jobs_section = (
        "\n\nZur Frage passende, veröffentlichte Stellenangebote (per Ähnlichkeitssuche):\n"
        f"{jobs_context}\n\n"
        "Nenne daraus konkrete Stellen, wenn danach gefragt wird. Erfinde keine Details (z.B. Anforderungen, "
        "Gehalt) - verweise dafür auf die Stellenangebote-Seite. Passt keine davon zur Frage, sag das offen."
        if jobs_context else ""
    )

    resumes_context = _relevant_resumes_context(question_embedding, logger)
    resumes_section = (
        "\n\nPer Vektor-Ähnlichkeitssuche über den vollständigen Lebenslauftext (Werdegang, Fähigkeiten, "
        "Erfahrung) ermittelte, am besten zur Frage passende Personen, absteigend nach Relevanz:\n"
        f"{resumes_context}\n\n"
        "Das ist eine Tatsache, auch wenn der Lebenslauf-Inhalt hier fehlt. Fragt jemand nach Personen mit "
        "bestimmten Fähigkeiten (z.B. 'wer kennt sich mit X aus'), nenne den/die Erstplatzierte(n) konkret mit "
        "Namen, statt auszuweichen. Erfinde keine Zusatzdetails (Firmen, Jahreszahlen, Technologien) - verweise "
        "dafür auf die Nutzerseite. Hat die Frage nichts mit Bewerbungen/Fähigkeiten zu tun, erwähne die Liste nicht."
        if resumes_context else ""
    )

    # Denkmodelle rechnen ihre Denk-Tokens als Output ab; für kurze Assistenten-
    # Antworten reicht niedriger Aufwand. Andere Modelle kennen den Parameter nicht.
    extra_args = {"reasoning_effort": "low"} if model_id in REASONING_MODELS else {}

    try:
        response = active_client.chat.completions.create(
            model=model_id,
            name="assistant",  # Name der Generation in Langfuse
            messages=[
                {"role": "system", "content": (
                    "Du bist ein Assistent, der bei allgemeinen Fragen zur Website, Stellenbewerbung und Stellenveröffentlichung hilft.\n\n"
                    "Das ist die vollständige, aktuelle Seitenstruktur der Website (Pfad, Zweck):\n"
                    f"{site_map}\n\n"
                    "Diese Liste ist deine einzige Wissensquelle über den Aufbau der Website. "
                    "Wenn eine Seite, ein Menüpunkt oder eine Funktion hier nicht auftaucht, existiert sie nicht - "
                    "erfinde in diesem Fall nichts, sondern sage klar, dass es das nicht gibt. "
                    "Die Website ist noch im Aufbau, die Liste kann sich also häufig ändern - verlasse dich ausschließlich auf die aktuelle Liste oben, nicht auf frühere Annahmen. "
                    "Antworte kurz und knapp in normaler Sprache (z.B. Menüpunkt-Name), ohne die technische Route (z.B. /jobs) zu nennen."
                    f"{jobs_section}"
                    f"{resumes_section}"
                )},
                {"role": "user", "content": question},
            ],
            **extra_args,
        )
        log_token_usage("assistant", model_id, response)
        return strip_think_block(response.choices[0].message.content), model_id
    except (GroqAPIStatusError, OpenAIAPIStatusError) as e:
        if e.status_code == 429:
            if logger:
                logger.warning("API 429 details: %s", e.body)
            return f"🧙 {wizard_name} ist müde und hat für heute keine Zaubersprüche mehr übrig. Bitte versuche es morgen erneut.", model_id
        if logger:
            logger.warning("API error %s: %s", e.status_code, e.body)
        return f"🧙 {wizard_name}s Kristallkugel ist gerade getrübt. Bitte versuche es später noch einmal.", model_id
