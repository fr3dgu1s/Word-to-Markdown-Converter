import os
import shutil
import tempfile
import re
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# --- STABLE DOCLING IMPORTS ---
from docling.document_converter import DocumentConverter
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling_core.types.doc import PictureItem
from protected_file_access import ensure_accessible_docx, ProtectedFileAccessError

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


def get_unique_safe_name(base_name: str) -> str:
    """Avoid collisions when batch-converting files with the same stem."""
    safe_base = sanitize_name(base_name) or "document"
    safe_name = safe_base
    counter = 2
    while (OUTPUTS_ROOT / f"{safe_name}.md").exists() or (GLOBAL_IMAGES_DIR / safe_name).exists():
        safe_name = f"{safe_base}-{counter}"
        counter += 1
    return safe_name

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


def convert_file_to_markdown(
    upload_file: UploadFile,
    *,
    include_markdown: bool = True,
) -> dict:
    original_name = Path(upload_file.filename or "document").stem
    safe_name = get_unique_safe_name(original_name)
    spec_image_folder = GLOBAL_IMAGES_DIR / safe_name
    spec_image_folder.mkdir(parents=True, exist_ok=True)

    tmp_path: Optional[Path] = None
    accessible_tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            tmp_path = Path(tmp.name)

        source_path, _identity, generated_copy = ensure_accessible_docx(tmp_path)
        if generated_copy:
            accessible_tmp_path = source_path

        conv_res = converter.convert(source_path)

        picture_counter = 0
        for element, _level in conv_res.document.iterate_items():
            if isinstance(element, PictureItem):
                picture_counter += 1
                img_name = f"image_{picture_counter}.png"
                img_path = spec_image_folder / img_name
                with img_path.open("wb") as fp:
                    element.get_image(conv_res.document).save(fp, "PNG")

        raw_markdown = conv_res.document.export_to_markdown(image_placeholder="IMAGE_TOKEN")
        final_markdown = raw_markdown
        for i in range(1, picture_counter + 1):
            tag = f"![spec-image](Images/{safe_name}/image_{i}.png)"
            final_markdown = final_markdown.replace("IMAGE_TOKEN", tag, 1)

        md_file_path = OUTPUTS_ROOT / f"{safe_name}.md"
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        result = {
            "doc_name": safe_name,
            "output_file": str(md_file_path),
        }
        if include_markdown:
            result["markdown"] = final_markdown

        return result
    except ProtectedFileAccessError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    finally:
        if accessible_tmp_path and accessible_tmp_path.exists():
            accessible_tmp_path.unlink(missing_ok=True)
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

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
    try:
        single_result = convert_file_to_markdown(file, include_markdown=True)
        return {
            "markdown": single_result["markdown"],
            "doc_name": single_result["doc_name"],
            "folder_created": str(OUTPUTS_ROOT)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/convert-batch")
async def convert_documents_batch(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided.")

    converted = []
    skipped = []
    failed = []

    for upload_file in files:
        filename = upload_file.filename or ""
        if not filename.lower().endswith(".docx"):
            skipped.append({
                "file": filename,
                "reason": "Only .docx files are supported for batch conversion.",
            })
            continue

        try:
            item = convert_file_to_markdown(upload_file, include_markdown=False)
            converted.append({
                "file": filename,
                "doc_name": item["doc_name"],
                "output_file": item["output_file"],
            })
        except Exception as exc:
            failed.append({
                "file": filename,
                "error": str(exc),
            })

    if not converted and failed:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Batch conversion failed for all eligible files.",
                "failed": failed,
            },
        )

    return {
        "folder_created": str(OUTPUTS_ROOT),
        "converted_count": len(converted),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)