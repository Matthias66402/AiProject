from weasyprint import HTML
from weasyprint.urls import URLFetcher

# Festes Stylesheet für alle erzeugten PDFs (Lebensläufe, Stellenangebote): Die
# KI liefert bewusst nur schlichtes, semantisches HTML ohne eigenes CSS (siehe
# SIMPLE_HTML_RULE/DOCUMENT_HTML_RULE in text_utils) - das Aussehen kommt von
# hier und kostet so keine Tokens. Bringt ein (älteres) Dokument doch eigenes
# <style> mit, steht das später im Dokument und hat damit Vorrang.
_PDF_STYLESHEET = """
@page {
    size: A4;
    margin: 2cm 2.2cm;
    @bottom-right { content: counter(page) " / " counter(pages); font-size: 8pt; color: #888; }
}
body { font-family: "DejaVu Sans", Arial, sans-serif; font-size: 10pt; line-height: 1.45; color: #222; }
h1 { font-size: 20pt; margin: 0 0 4pt; color: #1a3d5c; }
h1 + p { margin-top: 0; color: #555; }
h2 {
    font-size: 13pt; margin: 18pt 0 6pt; padding-bottom: 3pt;
    color: #1a3d5c; border-bottom: 1.5pt solid #1a3d5c;
}
h3 { font-size: 11pt; margin: 12pt 0 3pt; color: #1a3d5c; }
h4 { font-size: 10pt; margin: 10pt 0 2pt; }
h3 em, h4 em { font-weight: normal; color: #666; }
h2, h3, h4 { page-break-after: avoid; }
p { margin: 0 0 6pt; }
ul, ol { margin: 2pt 0 8pt; padding-left: 16pt; }
li { margin-bottom: 2pt; }
/* Quill speichert Aufzählungen als <ol><li data-list="bullet"> */
li[data-list="bullet"] { list-style-type: disc; }
strong { color: #111; }
hr { border: none; border-top: 0.75pt solid #ccc; margin: 12pt 0; }
table { border-collapse: collapse; width: 100%; margin: 4pt 0 10pt; }
th, td { border: 0.75pt solid #ccc; padding: 3pt 6pt; text-align: left; vertical-align: top; }
th { background: #eef3f7; }
tr { page-break-inside: avoid; }
a { color: #1a3d5c; }
"""


def _blocking_url_fetcher():
    """URLFetcher für WeasyPrint ohne erlaubte Protokolle, d.h. jeder Abruf externer
    Ressourcen (http, file, ...) wird verweigert: Die Dokumente brauchen keine, und
    beim Zuschneiden eines Lebenslaufs kommt das HTML vom Client zurück - ohne
    diese Sperre könnte ein <img src> den Server beliebige URLs oder lokale
    Dateien abrufen lassen. WeasyPrint lässt die Ressource dann einfach weg."""
    return URLFetcher(allowed_protocols=())


def write_html_as_pdf(html_fragment, output_path):
    document = (
        f"<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>{_PDF_STYLESHEET}</style></head>"
        f"<body>{html_fragment}</body></html>"
    )
    HTML(string=document, url_fetcher=_blocking_url_fetcher()).write_pdf(output_path)
