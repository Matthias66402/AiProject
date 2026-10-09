import os

# Langfuse-Drop-in für das OpenAI-SDK: jeder chat.completions-/embeddings-Aufruf
# wird automatisch als Generation (Prompt, Antwort, Modell, Tokens, Kosten,
# Latenz) an Langfuse gemeldet. Konfiguration über LANGFUSE_PUBLIC_KEY,
# LANGFUSE_SECRET_KEY und LANGFUSE_BASE_URL aus der .env; fehlen die Keys,
# verhält sich der Client wie das normale OpenAI-SDK (Tracing nur deaktiviert).
from langfuse.openai import OpenAI

openai_client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Groq ist OpenAI-kompatibel und läuft deshalb über denselben Langfuse-Wrapper
# statt über das groq-SDK, damit auch diese Aufrufe getraced werden. API-Fehler
# kommen dadurch als openai.APIStatusError (wird überall bereits abgefangen).
# Optional: ohne (nicht-leeren) GROQ_API_KEY bleibt der Client None.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
groq_client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1") if GROQ_API_KEY else None
