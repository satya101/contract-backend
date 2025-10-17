import os
import io
import json
import smtplib
import tempfile
from email.message import EmailMessage
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# --- OpenAI ---
from openai import OpenAI

# --- Document tooling ---
import fitz  # PyMuPDF
from docx import Document

# OCR (optional). If tesseract binary isn't present, we disable OCR gracefully.
try:
    import pytesseract  # type: ignore
    from PIL import Image  # type: ignore
    _HAS_TESSERACT = True
except Exception:
    _HAS_TESSERACT = False

# ----------------------------------------------------------------------------
# App & CORS
# ----------------------------------------------------------------------------
app = FastAPI(title="Contract Backend (Section 32)")

FRONTEND_ORIGIN = os.getenv("FRONTEND_ORIGIN")  # e.g. https://contractdashboardfinal.netlify.app
if FRONTEND_ORIGIN:
    allow_origins = [FRONTEND_ORIGIN]
else:
    # permissive for development; tighten in prod
    allow_origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------------------------------------------------------
# OpenAI client
# ----------------------------------------------------------------------------
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not set")
client = OpenAI(api_key=OPENAI_API_KEY)
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ----------------------------------------------------------------------------
# Extraction utilities
# ----------------------------------------------------------------------------

def extract_pdf_with_pages(path: str, ocr: bool = True) -> List[Dict[str, Any]]:
    doc = fitz.open(path)
    pages: List[Dict[str, Any]] = []
    for i, page in enumerate(doc):
        text = page.get_text("text") or ""
        if not text.strip() and ocr:
            if _HAS_TESSERACT:
                try:
                    pix = page.get_pixmap(dpi=300)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    text = pytesseract.image_to_string(img)
                except Exception:
                    text = text or ""
            else:
                # Vision OCR fallback via OpenAI (no Tesseract needed)
                try:
                    pix = page.get_pixmap(dpi=240)
                    import base64
                    b64 = base64.b64encode(pix.tobytes("png")).decode("utf-8")
                    vision_prompt = "Extract all readable text on this page. Return plain text only."
                    resp = client.chat.completions.create(
                        model=os.getenv("OPENAI_VISION_MODEL", "gpt-4o-mini"),
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": vision_prompt},
                                {"type": "input_image", "image_url": f"data:image/png;base64,{b64}"}
                            ],
                        }],
                        temperature=0.0,
                    )
                    text = resp.choices[0].message.content or ""
                except Exception:
                    text = text or ""
        pages.append({"page": i + 1, "text": text})
    return pages


def extract_docx_with_pages(path: str) -> List[Dict[str, Any]]:
    """DOCX has no true pagination; treat whole doc as page 1."""
    d = Document(path)
    text = "\n".join(p.text for p in d.paragraphs)
    return [{"page": 1, "text": text}]


def chunk_pages(pages: List[Dict[str, Any]], max_chars: int = 8000) -> List[Dict[str, Any]]:
    """Group page texts into chunks of ~max_chars, carrying page provenance."""
    chunks: List[Dict[str, Any]] = []
    buff, buff_pages = "", []
    for p in pages:
        header = f"[[PAGE {p['page']}]]\n"
        candidate = header + (p.get("text") or "") + "\n\n"
        if len(buff) + len(candidate) > max_chars and buff:
            chunks.append({"text": buff, "pages": buff_pages[:]})
            buff, buff_pages = "", []
        buff += candidate
        buff_pages.append(p["page"])
    if buff:
        chunks.append({"text": buff, "pages": buff_pages})
    return chunks

# ----------------------------------------------------------------------------
# Schema & instructions
# ----------------------------------------------------------------------------
SECTION32_SCHEMA: Dict[str, Any] = {
  "type": "object",
  "properties": {
    "title": {
      "type": "object",
      "properties": {
        "owner_names": {"type": "array", "items": {"type": "string"}},
        "volume_folio": {"type": "string"},
        "plan_lot": {"type": "string"},
        "encumbrances": {"type": "array", "items": {"type": "string"}},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "mortgages": {
      "type": "object",
      "properties": {
        "mortgagees": {"type": "array", "items": {"type": "string"}},
        "discharge_required": {"type": "boolean"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "planning_zoning": {
      "type": "object",
      "properties": {
        "zone": {"type": "string"},
        "overlays": {"type": "array", "items": {"type": "string"}},
        "certificate_date": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "rates_outgoings": {
      "type": "object",
      "properties": {
        "council": {"type": "string"},
        "annual_amount": {"type": "string"},
        "owners_corp": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "insurance": {
      "type": "object",
      "properties": {
        "policy_number": {"type": "string"},
        "insurer": {"type": "string"},
        "valid_to": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "building_permits": {
      "type": "object",
      "properties": {
        "permits": {"type": "array", "items": {"type": "string"}},
        "owner_builder": {"type": "boolean"},
        "warranty_insurance": {"type": "string"},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "notices": {
      "type": "object",
      "properties": {
        "adverse_notices": {"type": "array", "items": {"type": "string"}},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "special_conditions": {
      "type": "object",
      "properties": {
        "items": {"type": "array", "items": {"type": "string"}},
        "caveats": {"type": "array", "items": {"type": "string"}},
        "supporting_doc_present": {"type": "boolean"},
        "page_refs": {"type": "array", "items": {"type": "integer"}}
      },
      "required": ["supporting_doc_present", "page_refs"]
    },
    "missing_or_unclear": {
      "type": "array",
      "items": {"type": "string"}
    }
  },
  "required": [
    "title","mortgages","planning_zoning","rates_outgoings",
    "insurance","building_permits","notices","special_conditions","missing_or_unclear"
  ]
}

EXTRACTION_INSTRUCTIONS = """
You are extracting a Victorian Section 32 (Vendor Statement) summary.

RULES:
- Only return valid JSON matching the provided schema.
- Use the exact field names.
- For each section, set supporting_doc_present true/false based on evidence.
- Always include page_refs (list of integers).
- If a field isn't present, leave it empty but still include the key; also add a human-readable note to `missing_or_unclear`.
- Never invent data; if uncertain, state so in `missing_or_unclear`.

Checklist to look for:
- Title (volume/folio, plan/lot, encumbrances/easements, caveats)
- Mortgages/charges & discharge
- Planning/Zoning certificate (zone/overlays, date, authority)
- Rates & outgoings (council, owners corp/strata)
- Insurance (building policy; owner-builder warranty if applicable)
- Building permits (numbers/dates, owner-builder status)
- Notices/adverse matters (from council or authorities)
- Special conditions & caveats (contract specials, restrictions)
"""

# ----------------------------------------------------------------------------
# Model helpers
# ----------------------------------------------------------------------------

def _extract_json(text: str) -> Dict[str, Any]:
    text = (text or "").strip()
    s = text.find("{")
    e = text.rfind("}")
    snippet = text[s:e+1] if s != -1 and e != -1 and e > s else text
    return json.loads(snippet)


def call_model(chunk_text: str) -> Dict[str, Any]:
    prompt = f"""{EXTRACTION_INSTRUCTIONS}

SOURCE:
{chunk_text}

Return JSON ONLY, matching this JSON schema loosely (names/types):
{json.dumps(SECTION32_SCHEMA, indent=2)}
"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    txt = resp.choices[0].message.content or "{}"
    return _extract_json(txt)


def merge_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def union_list(a, b):
        if isinstance(a, list) and isinstance(b, list):
            return sorted(list({x for x in (a + b) if x not in (None, "")}))
        if isinstance(a, list):
            return a
        if isinstance(b, list):
            return b
        return []

    wanted = [
        "title","mortgages","planning_zoning","rates_outgoings",
        "insurance","building_permits","notices","special_conditions"
    ]

    for r in results:
        for key, val in r.items():
            if key in wanted and isinstance(val, dict):
                out.setdefault(key, {})
                cur = out[key]
                for k, v in val.items():
                    if k == "page_refs" and isinstance(v, list):
                        cur.setdefault("page_refs", [])
                        cur["page_refs"] = sorted(list(set(cur["page_refs"] + v)))
                    elif k == "supporting_doc_present":
                        cur["supporting_doc_present"] = bool(v) or cur.get("supporting_doc_present", False)
                    elif isinstance(v, list):
                        cur[k] = union_list(cur.get(k, []), v)
                    else:
                        cur[k] = v or cur.get(k)
            elif key == "missing_or_unclear" and isinstance(val, list):
                out.setdefault("missing_or_unclear", [])
                out["missing_or_unclear"] = union_list(out["missing_or_unclear"], val)

    for req in wanted:
        out.setdefault(req, {})
        out[req].setdefault("supporting_doc_present", False)
        out[req].setdefault("page_refs", [])

    out.setdefault("missing_or_unclear", [])
    return out

# ----------------------------------------------------------------------------
# Pydantic models for auxiliary endpoints
# ----------------------------------------------------------------------------
class AskPayload(BaseModel):
    question: str
    context: Optional[str] = None

class EmailPayload(BaseModel):
    to: str
    subject: str
    body: str

# ----------------------------------------------------------------------------
# Routes
# ----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {"status": "ok", "model": MODEL}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    # Decide OCR based on env & availability
    ocr_enabled = os.getenv("ENABLE_OCR", "false").lower() == "true" and _HAS_TESSERACT

    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    # Extract
    if file.filename.lower().endswith(".pdf"):
        pages = extract_pdf_with_pages(tmp_path, ocr=ocr_enabled)
    elif file.filename.lower().endswith(".docx"):
        pages = extract_docx_with_pages(tmp_path)
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Please upload PDF or DOCX.")

    if not pages or all(not (p.get("text") or "").strip() for p in pages):
        raise HTTPException(status_code=422, detail="No text could be extracted. Enable OCR or provide a text-based file.")

    # Chunk and extract
    chunks = chunk_pages(pages, max_chars=8000)
    results: List[Dict[str, Any]] = []
    for ch in chunks:
        chunk_with_pages = f"(Pages: {ch['pages']})\n" + ch["text"]
        try:
            js = call_model(chunk_with_pages)
            # ensure page refs present
            for sect in ["title","mortgages","planning_zoning","rates_outgoings","insurance","building_permits","notices","special_conditions"]:
                if sect in js and isinstance(js[sect], dict):
                    prs = set(js[sect].get("page_refs", [])) | set(ch["pages"])
                    js[sect]["page_refs"] = sorted(list(prs))
            results.append(js)
        except Exception as e:
            results.append({"missing_or_unclear": [f"Chunk failed: {e}"]})

    summary = merge_results(results)
    return {"summary": summary, "pages": [p["page"] for p in pages], "file": file.filename}


@app.post("/ask")
async def ask(payload: AskPayload):
    if not payload.question or not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    context_snippet = (payload.context or "").strip()
    user_prompt = (
        "You are a contract review assistant. Answer concisely and cite any specific sections/pages if you can.\n\n"
        f"CONTEXT (may be truncated):\n{context_snippet}\n\n"
        f"QUESTION: {payload.question}\n"
    )

    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": user_prompt}],
        temperature=0.2,
    )
    answer = resp.choices[0].message.content or ""
    return {"answer": answer}


@app.post("/share-email")
async def share_email(payload: EmailPayload):
    """Send summary via SMTP if credentials are present; otherwise tell the client to use mailto fallback."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user

    if not (smtp_host and smtp_user and smtp_pass and smtp_from):
        # No SMTP configured; front-end should fallback to mailto
        return {"sent": False, "note": "SMTP not configured; use client mailto fallback."}

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = payload.to
    msg["Subject"] = payload.subject
    msg.set_content(payload.body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return {"sent": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Email send failed: {e}")


# Local dev entrypoint
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
