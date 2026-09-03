import html
import math
import re

from openai import APIError as OpenAIAPIError

EMBEDDING_MODEL = "text-embedding-3-small"

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html_to_text(content):
    """Wandelt HTML-Fragmente (job/resume content) in reinen, auf Whitespace
    normalisierten Text um - saubere Eingabe fürs Embedding."""
    text = html.unescape(_TAG_RE.sub(" ", content or ""))
    return _WHITESPACE_RE.sub(" ", text).strip()


def embed_text(openai_client, text, logger=None):
    """Berechnet ein Embedding für text. Gibt bei API-Fehlern (Status-, Verbindungs-
    oder Timeout-Fehler - alle Subklassen von openai.APIError) None zurück, statt
    den aufrufenden Request scheitern zu lassen - Embeddings sind ein sekundäres
    Feature gegenüber dem eigentlichen Job-/Resume-Anlegen."""
    try:
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=text)
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
        result = [None] * len(texts)
        for item in response.data:
            result[item.index] = item.embedding
        return result
    except OpenAIAPIError as e:
        if logger:
            logger.warning("Embedding-API-Fehler (Batch von %d): %s", len(texts), e)
        return [None] * len(texts)


def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def top_matches(query_embedding, items, top_k=5):
    """items: Liste von (id, embedding)-Paaren. Gibt die top_k (id, score)
    absteigend nach Ähnlichkeit sortiert zurück."""
    scored = [(item_id, cosine_similarity(query_embedding, embedding)) for item_id, embedding in items]
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[:top_k]
