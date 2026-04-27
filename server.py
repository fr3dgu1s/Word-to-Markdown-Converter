"""
Word-to-Markdown Converter — local FastAPI server.

Endpoints:
    GET  /                         Static index.html
    GET  /health                   Liveness probe
    GET  /api/status               Docling readiness
    POST /api/convert              Single-file conversion
    POST /api/convert-batch        Batch conversion
    POST /api/save-changes         Persist edited Markdown
    GET  /api/open-folder          Open the Outputs folder in Explorer
    POST /api/shutdown             Stop the server
    GET  /logs/latest              Tail app.log
    DELETE /logs/latest            Truncate app.log
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from logging_config import setup_logging
from paths import (
    OUTPUTS_ROOT,
    SINGLE_OUTPUT_ROOT,
    BATCH_OUTPUT_ROOT,
    IMAGES_ROOT,
    TEMP_ROOT,
    LOGS_ROOT,
)

logger = setup_logging()

app = FastAPI(title="Word-to-Markdown Converter")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    logger.exception(f"Unhandled error in {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "path": str(request.url),
        },
    )


# ---------------------------------------------------------------------------
# Docling lazy initialisation
# ---------------------------------------------------------------------------
_converter_ready = threading.Event()
_converter = None
_converter_error: Optional[str] = None


def _init_converter() -> None:
    global _converter, _converter_error
    logger.info("[INIT] Starting Docling converter initialisation")
    try:
        from docling.document_converter import DocumentConverter  # noqa: PLC0415
        from docling.datamodel.pipeline_options import PdfPipelineOptions  # noqa: PLC0415
        opts = PdfPipelineOptions()
        opts.generate_picture_images = True
        opts.images_scale = 2.0
        _converter = DocumentConverter()
        logger.info("[INIT] Docling converter ready")
    except Exception as exc:
        _converter_error = str(exc)
        logger.error(f"[INIT] Docling converter failed: {exc}")
    finally:
        _converter_ready.set()


threading.Thread(target=_init_converter, daemon=True, name="docling-init").start()


def _get_converter():
    """Block until the converter is ready then return it (or raise on failure)."""
    _converter_ready.wait(timeout=120)
    if _converter_error:
        raise RuntimeError(f"Document converter failed to initialise: {_converter_error}")
    if _converter is None:
        raise RuntimeError("Document converter is not available.")
    return _converter


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

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
    while (
        (SINGLE_OUTPUT_ROOT / f"{safe_name}.md").exists()
        or (BATCH_OUTPUT_ROOT / f"{safe_name}.md").exists()
        or (IMAGES_ROOT / safe_name).exists()
    ):
        safe_name = f"{safe_base}-{counter}"
        counter += 1
    return safe_name


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    elapsed = round((time.time() - start) * 1000)
    logger.info(f"← {request.method} {request.url.path} {response.status_code} ({elapsed}ms)")
    return response


# ---------------------------------------------------------------------------
# Core conversion helper
# ---------------------------------------------------------------------------

def convert_file_to_markdown(
    upload_file: UploadFile,
    *,
    include_markdown: bool = True,
    output_dir: Path = SINGLE_OUTPUT_ROOT,
) -> dict:
    """Convert one uploaded ``.docx`` file to Markdown using Docling."""
    original_name = Path(upload_file.filename or "document").stem
    safe_name = get_unique_safe_name(original_name)
    image_folder = IMAGES_ROOT / safe_name
    image_folder.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    logger.info(f"[CONVERT] start | file={upload_file.filename}")

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", dir=str(TEMP_ROOT)) as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            tmp_path = Path(tmp.name)

        from docling_core.types.doc import PictureItem  # noqa: PLC0415

        conv_res = _get_converter().convert(tmp_path)

        picture_counter = 0
        for element, _level in conv_res.document.iterate_items():
            if isinstance(element, PictureItem):
                picture_counter += 1
                img_name = f"image_{picture_counter}.png"
                with (image_folder / img_name).open("wb") as fp:
                    element.get_image(conv_res.document).save(fp, "PNG")

        raw_markdown = conv_res.document.export_to_markdown(image_placeholder="IMAGE_TOKEN")
        final_markdown = raw_markdown
        for i in range(1, picture_counter + 1):
            tag = f"![spec-image](Images/{safe_name}/image_{i}.png)"
            final_markdown = final_markdown.replace("IMAGE_TOKEN", tag, 1)

        md_file_path = output_dir / f"{safe_name}.md"
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(f"[CONVERT] done  | file={upload_file.filename} | elapsed={elapsed_ms}ms")

        result = {"doc_name": safe_name, "output_file": str(md_file_path)}
        if include_markdown:
            result["markdown"] = final_markdown
        return result

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.error(f"[CONVERT] fail  | file={upload_file.filename} | elapsed={elapsed_ms}ms | error={exc}")
        raise
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Health / status
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"ok": True}


@app.get("/api/status")
async def converter_status():
    ready = _converter_ready.is_set() and _converter is not None
    return {"converter_ready": ready, "error": _converter_error}


# ---------------------------------------------------------------------------
# Static / utility
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_index():
    return FileResponse("index.html")


app.mount("/Outputs", StaticFiles(directory=str(OUTPUTS_ROOT)), name="Outputs")


@app.get("/api/open-folder")
async def open_folder():
    os.startfile(OUTPUTS_ROOT)
    return {"status": "opened", "folder": str(OUTPUTS_ROOT)}


@app.post("/api/shutdown")
async def shutdown_app():
    logger.info("[SHUTDOWN] Shutdown requested by local user")

    def stop_server():
        time.sleep(1)
        os._exit(0)

    threading.Thread(target=stop_server, daemon=True).start()
    return {"status": "shutting_down"}


@app.post("/api/save-changes")
async def save_changes(data: dict = Body(...)):
    doc_name = data.get("doc_name")
    content = data.get("markdown", "")
    if not doc_name:
        raise HTTPException(status_code=400, detail="doc_name is required.")
    file_path = SINGLE_OUTPUT_ROOT / f"{doc_name}.md"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "saved", "path": str(file_path)}


# ---------------------------------------------------------------------------
# Local conversion endpoints
# ---------------------------------------------------------------------------

@app.post("/api/convert")
async def convert_document(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")
    try:
        result = convert_file_to_markdown(file, include_markdown=True)
        return {
            "markdown": result["markdown"],
            "doc_name": result["doc_name"],
            "output_file": result["output_file"],
            "folder_created": str(SINGLE_OUTPUT_ROOT),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unhandled error in /api/convert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/convert-batch")
async def convert_documents_batch(files: List[UploadFile] = File(...)):
    if not files:
        raise HTTPException(status_code=400, detail="No files were provided.")

    converted: list[dict] = []
    skipped: list[dict] = []
    failed: list[dict] = []

    for upload_file in files:
        filename = upload_file.filename or ""
        if not filename.lower().endswith(".docx"):
            skipped.append({"file": filename, "reason": "Only .docx files are supported for batch conversion."})
            continue
        try:
            item = convert_file_to_markdown(
                upload_file,
                include_markdown=False,
                output_dir=BATCH_OUTPUT_ROOT,
            )
            converted.append({
                "file": filename,
                "doc_name": item["doc_name"],
                "output_file": item["output_file"],
            })
        except Exception as exc:
            logger.exception(f"Unhandled error in /api/convert-batch for {filename}: {exc}")
            failed.append({"file": filename, "error": str(exc)})

    if not converted and not skipped and failed:
        raise HTTPException(
            status_code=500,
            detail={"message": "Batch conversion failed for all eligible files.", "failed": failed},
        )

    return {
        "folder_created": str(BATCH_OUTPUT_ROOT),
        "converted_count": len(converted),
        "skipped_count": len(skipped),
        "failed_count": len(failed),
        "converted": converted,
        "skipped": skipped,
        "failed": failed,
    }


# ---------------------------------------------------------------------------
# Log viewer endpoints
# ---------------------------------------------------------------------------

@app.get("/logs/latest")
def logs_latest(lines: int = 100):
    lines = min(max(lines, 1), 500)
    log_path = LOGS_ROOT / "app.log"
    if not log_path.exists():
        return {"lines": []}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": [ln.rstrip("\n") for ln in all_lines[-lines:]]}


@app.delete("/logs/latest")
def logs_clear():
    log_path = LOGS_ROOT / "app.log"
    if log_path.exists():
        open(log_path, "w").close()
    logger.info("[LOGS] Log file cleared by user")
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
