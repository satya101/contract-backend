from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os
import docx
import fitz  # PyMuPDF
from dotenv import load_dotenv

# Load env vars
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("Missing OPENAI_API_KEY in .env")

client = OpenAI(api_key=OPENAI_API_KEY)

app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def extract_text_from_pdf(file_bytes):
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def extract_text_from_docx(file):
    doc = docx.Document(file)
    return "\n".join([para.text for para in doc.paragraphs])

@app.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()

        if file.filename.endswith(".pdf"):
            content = extract_text_from_pdf(file_bytes)
        elif file.filename.endswith(".docx"):
            with open("temp.docx", "wb") as f:
                f.write(file_bytes)
            content = extract_text_from_docx("temp.docx")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format")

        if not content.strip():
            raise HTTPException(status_code=400, detail="No text extracted")

        # Send to OpenAI
        response = client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": "You are a contract lawyer assistant. Extract important details from the provided contract, including parties, title info, mortgages, zoning, rates, insurance, notices, and any missing documents."
                },
                {
                    "role": "user",
                    "content": content[:12000]  # keep within context limits
                }
            ]
        )

        summary = response.choices[0].message.content
        return {"summary": summary}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
