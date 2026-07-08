from __future__ import annotations

import fitz


def make_pdf(text: str = "Hello world from a test PDF.") -> bytes:
    """A minimal one-page PDF containing `text`, built with PyMuPDF."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data
