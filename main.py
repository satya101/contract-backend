# main.py
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, UploadFile, File
from openai import OpenAI
import os
import fitz  # PyMuPDF
import docx2txt
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

app = FastAPI()

@app.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    ext = file.filename.split('.')[-1]
    contents = await file.read()

    if ext == "pdf":
        with open("temp.pdf", "wb") as f:
            f.write(contents)
        doc = fitz.open("temp.pdf")
        text = "\n".join([page.get_text() for page in doc])
    elif ext == "docx":
        with open("temp.docx", "wb") as f:
            f.write(contents)
        text = docx2txt.process("temp.docx")
    else:
        return {"error": "Unsupported file type"}

    # Send to GPT for summarization
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Extract parties, clauses, dates, and terms   from this contract."},
            {"role": "user", "content": text[:12000]}
        ]
    )
    summary = response.choices[0].message.content
    return {"summary": summary}
