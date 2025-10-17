import fitz  # PyMuPDF
from docx import Document
from typing import List, Dict, Any

try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    _HAS_TESSERACT = True
except Exception:
    _HAS_TESSERACT = False

def extract_pdf_with_pages(path: str, ocr: bool = True) -> List[Dict[str, Any]]:
    doc = fitz.open(path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        if not text.strip() and ocr and _HAS_TESSERACT:
            try:
                pix = page.get_pixmap(dpi=300)
                import io
                img = Image.open(io.BytesIO(pix.tobytes("png")))
                text = pytesseract.image_to_string(img)
            except Exception:
                text = text or ""
        pages.append({"page": i + 1, "text": text})
    return pages

def extract_docx_with_pages(path: str) -> List[Dict[str, Any]]:
    d = Document(path)
    text = "\\n".join(p.text for p in d.paragraphs)
    return [{"page": 1, "text": text}]
