import os
import shutil
import tempfile
import re
import threading
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# --- STABLE DOCLING IMPORTS ---
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import PictureItem

app = FastAPI()

# 1. DIRECTORY CONFIG
BASE_DIR = Path("C:/temp/Word-to-MD-App")
OUTPUTS_ROOT = BASE_DIR / "Outputs"
GLOBAL_IMAGES_DIR = OUTPUTS_ROOT / "Images"

OUTPUTS_ROOT.mkdir(parents=True, exist_ok=True)
GLOBAL_IMAGES_DIR.mkdir(parents=True, exist_ok=True)

def sanitize_name(name: str) -> str:
    clean = name.lower()
    clean = re.sub(r"[^a-z0-9]", "-", clean)
    clean = re.sub(r"-+", "-", clean)
    return clean.strip("-")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

pipeline_options = PdfPipelineOptions()
pipeline_options.generate_picture_images = True
pipeline_options.images_scale = 2.0
converter = DocumentConverter()

@app.get("/")
async def serve_index():
    return FileResponse("index.html")

app.mount("/Outputs", StaticFiles(directory=str(OUTPUTS_ROOT)), name="Outputs")

@app.get("/api/open-folder")
async def open_folder():
    os.startfile(OUTPUTS_ROOT)
    return {"status": "opened"}

@app.post("/api/shutdown")
async def shutdown_app():
    print("Shutdown requested by local user.")

    def stop_server():
        import time
        time.sleep(1)  # gives time for the response to return
        os._exit(0)

    threading.Thread(target=stop_server, daemon=True).start()
    return {"status": "shutting_down"}

@app.post("/api/save-changes")
async def save_changes(data: dict = Body(...)):
    doc_name = data.get("doc_name")
    content = data.get("markdown")

    file_path = OUTPUTS_ROOT / f"{doc_name}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return {"status": "saved"}

@app.post("/api/convert")
async def convert_document(file: UploadFile = File(...)):
    original_name = Path(file.filename).stem
    safe_name = sanitize_name(original_name)
    spec_image_folder = GLOBAL_IMAGES_DIR / safe_name
    spec_image_folder.mkdir(parents=True, exist_ok=True)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        conv_res = converter.convert(tmp_path)

        # 1. Physical Extraction
        picture_counter = 0
        for element, _level in conv_res.document.iterate_items():
            if isinstance(element, PictureItem):
                picture_counter += 1
                img_name = f"image_{picture_counter}.png"
                img_path = spec_image_folder / img_name
                with img_path.open("wb") as fp:
                    element.get_image(conv_res.document).save(fp, "PNG")

        # 2. Original Conversion Logic
        raw_markdown = conv_res.document.export_to_markdown(image_placeholder="IMAGE_TOKEN")

        # 3. Precise Token Swap
        final_markdown = raw_markdown
        for i in range(1, picture_counter + 1):
            tag = f"![spec-image](Images/{safe_name}/image_{i}.png)"
            final_markdown = final_markdown.replace("IMAGE_TOKEN", tag, 1)

        # Save to drive
        md_file_path = OUTPUTS_ROOT / f"{safe_name}.md"
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        os.unlink(tmp_path)

        return {
            "markdown": final_markdown,
            "doc_name": safe_name,
            "folder_created": str(OUTPUTS_ROOT)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)