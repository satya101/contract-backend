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
                "content": "You are a contract lawyer assistant. Extract important details from the provided contract, including parties, title info, mortgages, zoning, rates, insurance, notices, and any missing documents."
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
