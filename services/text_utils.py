import re

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?|\n?```\s*$")


def strip_think_block(text):
    """Entfernt <think>-Blöcke, in denen manche Modelle (z.B. Qwen) ihre
    Denkschritte ausgeben."""
    return _THINK_BLOCK_RE.sub("", text).strip()


def strip_code_fence(text):
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def clean_ai_response(text):
    """Vorverarbeitung einer KI-Antwort, die strukturierten Inhalt (JSON/HTML)
    enthalten soll: entfernt sowohl <think>-Blöcke als auch umschließende
    Markdown-Codefences."""
    return strip_code_fence(strip_think_block(text))
