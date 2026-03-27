import os
import shutil
import tempfile
import re
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# --- STABLE DOCLING IMPORTS ---
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import PictureItem

# 1. DIRECTORY CONFIG
BASE_DIR = Path("C:/temp/Word-to-MD-App")
OUTPUTS_ROOT = BASE_DIR / "Outputs"
GLOBAL_IMAGES_DIR = OUTPUTS_ROOT / "Images"
LOGS_DIR = BASE_DIR / "Logs"

OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
GLOBAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# 2. LOGGING CONFIGURATION
log_file = LOGS_DIR / "app.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(log_file, maxBytes=5000000, backupCount=3),
        logging.StreamHandler() # Also prints to your terminal
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()

def sanitize_name(name: str) -> str:
    clean = name.lower()
    clean = re.sub(r'[^a-z0-9]', '-', clean)
    clean = re.sub(r'-+', '-', clean)
    return clean.strip('-')

# --- SAFE TABLE CLEANUP LOGIC ---
def clean_markdown_tables(md_text: str) -> str:
    if not md_text:
        return md_text
        
    try:
        lines = md_text.split('\n')
        output = []
        i = 0
        
        while i < len(lines):
            line = lines[i]
            stripped = line.strip()
            
            if stripped.startswith('|'):
                parts = [p.strip() for p in stripped.split('|')]
                cells = [c for c in parts if c != ""]
                
                # 1. Detect repetitive merged header
                if len(cells) > 1 and all(c == cells[0] for c in cells):
                    output.append(f"| {cells[0]} |")
                    output.append("|---|")
                    output.append("") # Blank line to separate tables
                    
                    # Skip the broken alignment row right below the title
                    if i + 1 < len(lines) and '---' in lines[i+1]:
                        i += 1
                    i += 1
                    continue
                
                # 2. Fix data rows (Safely check if it has enough columns and the 3rd is empty)
                if len(parts) >= 6 and parts[3] == "":
                    output.append(f"| {parts[1]} | {parts[2]} | {parts[4]} | {parts[5]} |")
                
                # 3. Fix alignment rows to always be 4 columns if we are inside a fixed table
                elif '---' in stripped and len(parts) >= 6:
                    output.append("|---|---|---|---|")
                
                else:
                    output.append(stripped)
            else:
                # Keep original formatting for non-table text
                output.append(line) 
            
            i += 1
            
        return '\n'.join(output)
        
    except Exception as e:
        # If anything goes wrong, log the exact error and return the raw markdown so the app doesn't crash
        logger.error(f"Failed to clean tables: {str(e)}", exc_info=True)
        return md_text


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.images_scale = 2.0

logger.info("Initializing DocumentConverter...")
converter = DocumentConverter()
logger.info("DocumentConverter ready.")

@app.get("/")
async def serve_index():
    return FileResponse('index.html')

app.mount("/Outputs", StaticFiles(directory=str(OUTPUTS_ROOT)), name="Outputs")

@app.get("/api/open-folder")
async def open_folder():
    os.startfile(OUTPUTS_ROOT)
    return {"status": "opened"}

@app.post("/api/save-changes")
async def save_changes(data: dict = Body(...)):
    doc_name = data.get("doc_name")
    content = data.get("markdown")
    file_path = OUTPUTS_ROOT / f"{doc_name}.md"
    
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info(f"Successfully saved edits to {file_path}")
        return {"status": "saved"}
    except Exception as e:
        logger.error(f"Failed to save {doc_name}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to save file.")

@app.post("/api/convert")
async def convert_document(file: UploadFile = File(...)):
    original_name = Path(file.filename).stem
    safe_name = sanitize_name(original_name)
    spec_image_folder = GLOBAL_IMAGES_DIR / safe_name
    spec_image_folder.mkdir(parents=True, exist_ok=True)

    logger.info(f"--- Starting conversion for: {file.filename} ---")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        logger.info("Extracting document contents...")
        conv_res = converter.convert(tmp_path)

        # 1. Extract images
        picture_counter = 0
        for element, _level in conv_res.document.iterate_items():
            if isinstance(element, PictureItem):
                picture_counter += 1
                img_name = f"image_{picture_counter}.png"
                img_path = spec_image_folder / img_name
                with img_path.open("wb") as fp:
                    element.get_image(conv_res.document).save(fp, "PNG")
        
        logger.info(f"Extracted {picture_counter} images.")

        # 2. Export raw markdown
        raw_markdown = conv_res.document.export_to_markdown(image_placeholder="IMAGE_TOKEN")

        # 3. Replace image tokens
        final_markdown = raw_markdown
        for i in range(1, picture_counter + 1):
            tag = f"![image](/Outputs/Images/{safe_name}/image_{i}.png)"
            final_markdown = final_markdown.replace("IMAGE_TOKEN", tag, 1)

        # 4. Clean up tables safely
        logger.info("Applying table cleanup logic...")
        final_markdown = clean_markdown_tables(final_markdown)

        # 5. Save to disk
        md_file_path = OUTPUTS_ROOT / f"{safe_name}.md"
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        os.unlink(tmp_path)
        logger.info(f"Conversion successful! Saved to {md_file_path}")
        
        return {"markdown": final_markdown, "doc_name": safe_name, "folder_created": str(OUTPUTS_ROOT)}
        
    except Exception as e:
        logger.error(f"Conversion failed for {file.filename}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    logger.info("Starting FastAPI server on http://127.0.0.1:8000")
    uvicorn.run(app, host="127.0.0.1", port=8000)