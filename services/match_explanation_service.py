import hashlib
import json

import db
from services.ai_usage import log_token_usage
from services.match_profile_service import PROFILE_MODEL
from services.text_utils import clean_ai_response

# Version des Begründungs-Prompts - fließt in profiles_hash ein, eine Erhöhung
# macht also alle zwischengespeicherten Begründungen ungültig.
# 2 = Lücken nur noch fachlich, keine Formulierungsunterschiede.
EXPLANATION_VERSION = 2

# Höchstzahl der Einträge je Liste - die Anzeige in der Trefferliste ist schmal.
_MAX_ITEMS = 5

_EXPLANATION_SYSTEM_PROMPT = (
    "Du erklärst, warum ein Lebenslauf zu einem Stellenangebot passt oder nicht. Du "
    "erhältst zwei Matching-Profile im selben Format (Rolle, Berufsfeld, Fachkenntnisse, "
    "Werkzeuge und Technologien, Erfahrung, Ausbildung, Sprachen) - eines der Stelle, "
    "eines des Lebenslaufs. Antworte ausschließlich mit JSON der Form "
    '{"summary": "<ein kurzer Satz zur Gesamteinschätzung>", '
    '"matches": ["<Übereinstimmung>", ...], "gaps": ["<Anforderung der Stelle, die im '
    'Lebenslauf-Profil fehlt>", ...]}. '
    f"Je Liste höchstens {_MAX_ITEMS} kurze Stichpunkte (wenige Wörter), die wichtigsten "
    "zuerst; leere Liste, wenn es nichts gibt. Lücken sind nur fachliche Anforderungen "
    "(Kenntnisse, Werkzeuge, Abschlüsse, Sprachen, Erfahrung), die der Lebenslauf "
    "inhaltlich nicht abdeckt - keine Formulierungsunterschiede: Was sinngemäß erfüllt ist "
    "(z.B. 10 Jahre Berufserfahrung bei geforderter Erfahrung), ist keine Lücke. Verwende "
    "nur, was in den Profilen steht - nichts erfinden oder ergänzen. Sprich die Person "
    "nicht an, schreibe neutral auf Deutsch."
)


def _profiles_hash(job, resume):
    """Schlüssel für den Zwischenspeicher: ändert sich eines der Profile (z.B.
    Stelle bearbeitet, neuer Profil-Prompt) oder der Begründungs-Prompt, wird
    die gespeicherte Begründung nicht mehr verwendet."""
    raw = f"{EXPLANATION_VERSION}\n{job['match_profile']}\n---\n{resume['match_profile']}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _as_list(value):
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:_MAX_ITEMS]


def explain_match(openai_client, job, resume):
    """Begründung, warum resume zu job passt: {"summary", "matches", "gaps",
    "cached"}. Grundlage sind nur die beiden Matching-Profile (kurz, daher
    günstig). Wird pro Paar in match_explanations zwischengespeichert und nur
    neu erzeugt, wenn sich ein Profil oder der Prompt geändert hat. Erwartet,
    dass beide Einträge ein match_profile haben. Lässt
    GroqAPIStatusError/OpenAIAPIStatusError sowie json.JSONDecodeError/ValueError
    (unerwartetes Antwortformat) zum Aufrufer durch."""
    profiles_hash = _profiles_hash(job, resume)
    cached = db.get_match_explanation(job["id"], resume["id"])
    if cached and cached["profiles_hash"] == profiles_hash:
        return {"summary": cached["summary"], "matches": cached["matches"], "gaps": cached["gaps"], "cached": True}

    response = openai_client.chat.completions.create(
        model=PROFILE_MODEL,
        name="match_explanation",  # Name der Generation in Langfuse
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _EXPLANATION_SYSTEM_PROMPT},
            {"role": "user", "content": (
                f"PROFIL DER STELLE:\n{job['match_profile']}\n\n"
                f"PROFIL DES LEBENSLAUFS:\n{resume['match_profile']}"
            )},
        ],
    )
    log_token_usage("match_explanation", PROFILE_MODEL, response)
    data = json.loads(clean_ai_response(response.choices[0].message.content))
    summary = str(data.get("summary") or "").strip()
    if not summary:
        raise ValueError("Begründung ohne summary")
    matches, gaps = _as_list(data.get("matches")), _as_list(data.get("gaps"))
    db.save_match_explanation(job["id"], resume["id"], profiles_hash, summary, matches, gaps)
    return {"summary": summary, "matches": matches, "gaps": gaps, "cached": False}