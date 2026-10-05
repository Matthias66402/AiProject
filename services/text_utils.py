import re

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?|\n?```\s*$")
_INLINE_WHITESPACE_RE = re.compile(r"[ \t\f\v\xa0]+")
_BLANK_LINES_RE = re.compile(r"\n\s*\n\s*")

# Prompt-Bausteine für KI-Ausgaben im HTML-Format: schlichtes, semantisches
# Markup spart Output-Tokens; den Dokumentrahmen ergänzt write_html_as_pdf selbst.
_HTML_FRAGMENT_BASE = (
    "nur ein HTML-Fragment ohne <html>/<head>/<body>/<style> und ohne style-/class-Attribute, "
    "klar und übersichtlich gegliedert mit kurzen Absätzen statt Textblöcken: "
)

# Für Stellenangebote: deren Inhalt wird im Quill-Editor (frontend RichTextEditor)
# bearbeitet, der nur diese Formate kennt - Tabellen/hr gingen dort verloren.
SIMPLE_HTML_RULE = _HTML_FRAGMENT_BASE + (
    "h3 für Abschnitte (z.B. Über uns, Deine Aufgaben, Dein Profil, Wir bieten, Kontakt), "
    "h4 für Unterabschnitte, p für Fließtext, ul/li für Aufzählungen (Aufgaben, Anforderungen, "
    "Benefits je ein kurzer Punkt), ol/li für Abfolgen (z.B. Bewerbungsprozess), strong/em für "
    "wichtige Begriffe; keine anderen Tags (insbesondere keine Tabellen, kein hr)"
)

# Für Lebensläufe: werden nur als PDF angezeigt, nicht im Editor bearbeitet.
DOCUMENT_HTML_RULE = _HTML_FRAGMENT_BASE + (
    "h1 für den Namen, direkt darunter p mit den Kontaktdaten, h2 für Abschnitte (z.B. Profil, "
    "Berufserfahrung, Ausbildung, Kenntnisse, Sprachen), h3 für einzelne Stationen (Position/Abschluss "
    "und Arbeitgeber/Schule) mit dem Zeitraum in em, p für Fließtext, ul/li für Tätigkeiten und "
    "Kenntnisse (je ein kurzer Punkt), strong für wichtige Begriffe, table/tr/th/td nur für "
    "tabellarische Angaben (z.B. Sprachen mit Niveau); kein hr"
)


def compact_whitespace(text):
    """Reduziert Leerzeichen-/Leerzeilen-Folgen (typisch bei aus PDFs extrahiertem
    Text) auf ein Minimum, spart Input-Tokens. Absätze bleiben als einzelne
    Leerzeile erhalten."""
    text = _INLINE_WHITESPACE_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANK_LINES_RE.sub("\n\n", text).strip()


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
