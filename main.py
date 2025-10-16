
# === Added integrations: email share & ask ===
import os
import smtplib
from email.message import EmailMessage
from pydantic import BaseModel
from fastapi import HTTPException
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import docx
import fitz  # PyMuPDF
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env")

# Initialize OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize FastAPI app
app = FastAPI()

# Set up CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Contract review backend is live"}

def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    return "\n".join([page.get_text() for page in doc])

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    doc = docx.Document(file_path)
    return "\n".join([para.text for para in doc.paragraphs])

@app.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    """Endpoint to upload a contract and receive a summary."""
    try:
        file_bytes = await file.read()

        if file.filename.endswith(".pdf"):
            content = extract_text_from_pdf(file_bytes)
        elif file.filename.endswith(".docx"):
            temp_path = "temp.docx"
            with open(temp_path, "wb") as f:
                f.write(file_bytes)
            content = extract_text_from_docx(temp_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        if not content.strip():
            raise HTTPException(status_code=400, detail="No text extracted from file")

        # Request summary from OpenAI with model fallback
        messages = [
            {
                "role": "system",
                "content": "You are an experienced contract lawyer assistant. Review this Section 32 Vendor Statement thoroughly from a residential property buyer’s perspective. Extract important details from the provided contract, including parties, title info, mortgages,easements, covenants, zoning, rates, insurance, notices, and any missing documents. Indicate any documentation discrepancies and suggest follow-up actions for the parties involved. Any hidden or ongoing financial liabilities such as unpaid taxes, council rates, or body corporate fees that may transfer to the buyer at settlement. Restrictions on the property’s title including easements, covenants, zoning, or planning overlays and how these might affect use, renovation, or resale potential. Validity and completeness of building permits, owner-builder insurance, occupancy certificates, and any environmental risks like contamination or flood zones. Summarize all key risks under legal, financial, zoning, and property condition categories with risk levels and practical actions a buyer should take before signing, such as obtaining further certificates or legal advice. Provide a plain-English summary and flag any missing or incomplete disclosures that could allow contract rescission or impact buyer decision-making."
            },
            {
                "role": "user",
                "content": content[:12000]
            }
        ]

        models_to_try = ["gpt-4", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
        response = None
        last_exception = None

        for model_name in models_to_try:
            try:
                response = client.chat.completions.create(
                    model=model_name,
                    messages=messages
                )
                # success
                break
            except Exception as e:
                # keep the last exception for error reporting and continue trying fallbacks
                last_exception = e

        if response is None:
            # No model worked; return a 502 with the last OpenAI error message for debugging
            raise HTTPException(status_code=502, detail=f"OpenAI model error: {str(last_exception)}")

        # Extract summary text from successful response
        summary = response.choices[0].message.content

        return {"summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



class ShareEmailRequest(BaseModel):
    to: str
    subject: str
    body: str

@app.post("/share-email")
def share_email(req: ShareEmailRequest):
    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    if not (smtp_user and smtp_pass):
        raise HTTPException(status_code=500, detail="SMTP not configured on server")

    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = req.to
    msg["Subject"] = req.subject
    msg.set_content(req.body)

    with smtplib.SMTP(smtp_host, smtp_port) as s:
        s.starttls()
        s.login(smtp_user, smtp_pass)
        s.send_message(msg)

    return {"status": "sent"}



class AskRequest(BaseModel):
    question: str
    context: str

@app.post("/ask")
def ask(req: AskRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY not set")
    if OpenAI is None:
        raise HTTPException(status_code=500, detail="openai sdk not installed on server")

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = OpenAI(api_key=api_key)

    prompt = (
        "You are a contract assistant. Answer briefly and concretely.\n\n"
        "CONTEXT (summary JSON or text):\n" + req.context + "\n\n"
        "QUESTION: " + req.question
    )

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        answer = resp.choices[0].message.content
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
