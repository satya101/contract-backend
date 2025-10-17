# Contract Backend Utils (Section 32 Extraction)

## Files
- `utils/extract.py` — PDF/DOCX extraction with optional OCR (Tesseract if available)
- `utils/chunk.py` — chunk pages into ~8k char blocks with page provenance
- `utils/schema.py` — strict JSON schema + extraction instructions
- `utils/llm.py` — OpenAI call + robust JSON parse + merge across chunks
- `scripts/eval.py` — (starter) evaluation harness for a golden set in `data/gold`

## Install
Add to `requirements.txt` (or pip install):
```
pymupdf
python-docx
pytesseract
Pillow
openai
```

## main.py wiring (example)
```python
import os, tempfile
from fastapi import FastAPI, UploadFile, File
from openai import OpenAI
from utils.extract import extract_pdf_with_pages, extract_docx_with_pages
from utils.chunk import chunk_pages
from utils.schema import SECTION32_SCHEMA, EXTRACTION_INSTRUCTIONS
from utils.llm import call_model, merge_results

app = FastAPI()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

@app.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    if file.filename.lower().endswith(".pdf"):
        pages = extract_pdf_with_pages(tmp_path, ocr=True)
    elif file.filename.lower().endswith(".docx"):
        pages = extract_docx_with_pages(tmp_path)
    else:
        return {"error": "Unsupported file type"}

    chunks = chunk_pages(pages, max_chars=8000)

    results = []
    for ch in chunks:
        chunk_with_pages = f"(Pages: {ch['pages']})\n" + ch["text"]
        try:
            js = call_model(client, MODEL, SECTION32_SCHEMA, EXTRACTION_INSTRUCTIONS, chunk_with_pages)
            for sect in ["title","mortgages","planning_zoning","rates_outgoings","insurance","building_permits","notices","special_conditions"]:
                if sect in js and isinstance(js[sect], dict):
                    prs = set(js[sect].get("page_refs", [])) | set(ch["pages"])
                    js[sect]["page_refs"] = sorted(list(prs))
            results.append(js)
        except Exception as e:
            results.append({"missing_or_unclear": [f"Chunk failed: {e}"]})

    summary = merge_results(results)
    return {"summary": summary}
```
