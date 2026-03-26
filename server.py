from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse # <-- NEED THIS
from docling.document_converter import DocumentConverter
import tempfile
import os

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Loading Docling AI Models... (This might take a moment on startup)")
converter = DocumentConverter()
print("Docling is ready!")

# <-- THIS IS WHAT FIXES YOUR 404 ERROR -->
@app.get("/")
async def serve_interface():
    return FileResponse("index.html")

@app.post("/api/convert")
async def convert_document(file: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_file.write(await file.read())
        temp_path = temp_file.name

    try:
        result = converter.convert(temp_path)
        markdown_text = result.document.export_to_markdown()
        return {"markdown": markdown_text}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.remove(temp_path)