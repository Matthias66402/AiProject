import logging

# Eigener Logger mit eigenem Handler, damit der Token-Verbrauch unabhängig von
# der Flask-Logkonfiguration erscheint - auch in Skripten ohne App-Kontext
# (z.B. backfill_embeddings.py).
_logger = logging.getLogger("ai_usage")
if not _logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s [ai_usage] %(message)s"))
    _logger.addHandler(_handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


def log_token_usage(purpose, model, response):
    """Protokolliert den Token-Verbrauch einer Chat- oder Embedding-Antwort
    (OpenAI wie Groq). Felder, die ein Anbieter/Modell nicht liefert (z.B.
    gecachte oder Reasoning-Tokens), werden als 0 ausgegeben."""
    usage = getattr(response, "usage", None)
    if usage is None:
        _logger.info("%s model=%s usage=nicht geliefert", purpose, model)
        return
    prompt_details = getattr(usage, "prompt_tokens_details", None)
    completion_details = getattr(usage, "completion_tokens_details", None)
    _logger.info(
        "%s model=%s input=%s (cached=%s) output=%s (reasoning=%s) total=%s",
        purpose,
        model,
        getattr(usage, "prompt_tokens", 0) or 0,
        getattr(prompt_details, "cached_tokens", 0) or 0,
        getattr(usage, "completion_tokens", 0) or 0,
        getattr(completion_details, "reasoning_tokens", 0) or 0,
        getattr(usage, "total_tokens", 0) or 0,
    )
