"""PDF service: extract plain text from an uploaded resume PDF.

This is the only step that does NOT use AI — pdfplumber reads the text layer
of the PDF. (Image-only / scanned PDFs would need OCR, which we don't do here.)
"""
import pdfplumber


def extract_text_from_pdf(file_path: str) -> str:
    """Open a PDF and join the text from all pages into one string."""
    text = ""
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:                  # iterate over every page
            page_text = page.extract_text()     # None if the page has no text layer
            if page_text:
                text += page_text + "\n"
    return text.strip()
