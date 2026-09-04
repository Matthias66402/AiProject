import os

from docx import Document as DocxDocument
from odf import teletype
from odf.opendocument import load as load_odf
from odf.text import P as OdfParagraph
from pypdf import PdfReader

# Von "Lebenslauf hochladen" akzeptierte Dateiformate: PDF, Word (.docx) und
# LibreOffice/OpenDocument (.odt). Legacy .doc (binäres altes Word-Format) wird
# bewusst nicht unterstützt - python-docx kann nur .docx lesen.
ALLOWED_RESUME_UPLOAD_EXTENSIONS = {".pdf", ".docx", ".odt"}


def _extract_text_from_pdf(file_stream):
    reader = PdfReader(file_stream)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_text_from_docx(file_stream):
    document = DocxDocument(file_stream)
    return "\n".join(p.text for p in document.paragraphs)


def _extract_text_from_odt(file_stream):
    document = load_odf(file_stream)
    return "\n".join(teletype.extractText(p) for p in document.getElementsByType(OdfParagraph))


def extract_resume_text(filename, file_stream):
    """Liest den reinen Text aus einer hochgeladenen Lebenslauf-Datei (PDF/.docx/.odt)
    aus. file_stream muss an Position 0 stehen. Wirft ValueError bei nicht
    unterstützter Endung, sonst die jeweilige Parser-Exception bei defekten Dateien -
    beides vom Aufrufer abzufangen, da die Datei von Nutzern hochgeladen wird."""
    ext = os.path.splitext(filename)[1].lower()
    if ext == ".pdf":
        return _extract_text_from_pdf(file_stream)
    if ext == ".docx":
        return _extract_text_from_docx(file_stream)
    if ext == ".odt":
        return _extract_text_from_odt(file_stream)
    raise ValueError(f"Nicht unterstütztes Dateiformat: {ext}")
