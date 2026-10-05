import html
import re

from openai import APIError as OpenAIAPIError

from services.ai_usage import log_token_usage

EMBEDDING_MODEL = "text-embedding-3-small"

_STYLE_SCRIPT_RE = re.compile(r"<(style|script)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html_to_text(content):
    """Wandelt HTML-Fragmente/-Dokumente (job/resume content) in reinen, auf
    Whitespace normalisierten Text um - saubere Eingabe fürs Embedding.
    Entfernt <style>/<script>-Blöcke komplett inkl. Inhalt (nicht nur die
    Tags) - sonst landet z.B. CSS-Deklarationen aus generierten Lebenslauf-
    HTML-Dokumenten als Text im Embedding und verfälscht die Ähnlichkeit."""
    text = _STYLE_SCRIPT_RE.sub(" ", content or "")
    text = html.unescape(_TAG_RE.sub(" ", text))
    return _WHITESPACE_RE.sub(" ", text).strip()


def embed_text(openai_client, text, logger=None):
    """Berechnet ein Embedding für text. Gibt bei API-Fehlern (Status-, Verbindungs-
    oder Timeout-Fehler - alle Subklassen von openai.APIError) None zurück, statt
    den aufrufenden Request scheitern zu lassen - Embeddings sind ein sekundäres
    Feature gegenüber dem eigentlichen Job-/Resume-Anlegen."""
    try:
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
        log_token_usage("embedding", EMBEDDING_MODEL, response)
        return response.data[0].embedding
    except OpenAIAPIError as e:
        if logger:
            logger.warning("Embedding-API-Fehler: %s", e)
        return None


def embed_texts(openai_client, texts, logger=None):
    """Wie embed_text, aber für mehrere Texte in einem API-Call (spart Zeit/Calls
    bei vielen Dokumenten, z.B. im Backfill-Skript). Gibt eine Liste in derselben
    Reihenfolge wie texts zurück; schlägt der Call fehl, ist jeder Eintrag None."""
    if not texts:
        return []
    try:
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        log_token_usage(f"embedding_batch({len(texts)})", EMBEDDING_MODEL, response)
        result = [None] * len(texts)
        for item in response.data:
            result[item.index] = item.embedding
        return result
    except OpenAIAPIError as e:
        if logger:
            logger.warning("Embedding-API-Fehler (Batch von %d): %s", len(texts), e)
        return [None] * len(texts)


def to_vector_literal(embedding):
    """Formatiert ein Embedding als pgvector-Text-Literal (z.B. "[0.1,-0.2]"),
    zum Schreiben über einen %s::vector-Cast."""
    return "[" + ",".join(repr(float(x)) for x in embedding) + "]"
