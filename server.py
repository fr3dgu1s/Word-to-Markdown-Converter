import asyncio
import json
import os
import queue
import shutil
import tempfile
import re
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse

from protected_file_access import (
    convert_docx_with_docling_fallback,
    ProtectedFileAccessError,
    run_protected_access_diagnostics,
    test_protected_file_access,
)
from word_dispatch_pipeline import batch_convert as word_dispatch_batch_convert

app = FastAPI()

# ---------------------------------------------------------------------------
# Docling is loaded lazily in a background thread so the HTTP server is
# reachable within ~1 second of launch. Conversion endpoints wait if the
# converter is not yet ready (usually it finishes before a user can upload).
# ---------------------------------------------------------------------------
_converter_ready = threading.Event()
_converter = None          # set by _init_converter()
_converter_error = None    # set if import/init fails


def _init_converter() -> None:
    global _converter, _converter_error
    try:
        from docling.document_converter import DocumentConverter  # noqa: PLC0415
        from docling.datamodel.pipeline_options import PdfPipelineOptions  # noqa: PLC0415
        opts = PdfPipelineOptions()
        opts.generate_picture_images = True
        opts.images_scale = 2.0
        _converter = DocumentConverter()
    except Exception as exc:
        _converter_error = str(exc)
    finally:
        _converter_ready.set()


threading.Thread(target=_init_converter, daemon=True, name="docling-init").start()


def _get_converter():
    """Block until converter is ready then return it (or raise on init failure)."""
    _converter_ready.wait(timeout=120)
    if _converter_error:
        raise RuntimeError(f"Document converter failed to initialise: {_converter_error}")
    if _converter is None:
        raise RuntimeError("Document converter is not available.")
    return _converter

# 1. DIRECTORY CONFIG  — paths relative to this script's location
OUTPUTS_ROOT = Path(__file__).resolve().parent / "Outputs"
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
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            tmp_path = Path(tmp.name)

        from docling_core.types.doc import PictureItem  # noqa: PLC0415  (lazy after init)

        def _docling_to_markdown(path: str) -> str:
            conv_res = _get_converter().convert(Path(path))

            picture_counter = 0
            for element, _level in conv_res.document.iterate_items():
                if isinstance(element, PictureItem):
                    picture_counter += 1
                    img_name = f"image_{picture_counter}.png"
                    img_path = spec_image_folder / img_name
                    with img_path.open("wb") as fp:
                        element.get_image(conv_res.document).save(fp, "PNG")

            raw_markdown = conv_res.document.export_to_markdown(image_placeholder="IMAGE_TOKEN")
            final_md = raw_markdown
            for i in range(1, picture_counter + 1):
                tag = f"![spec-image](Images/{safe_name}/image_{i}.png)"
                final_md = final_md.replace("IMAGE_TOKEN", tag, 1)
            return final_md

        final_markdown = convert_docx_with_docling_fallback(str(tmp_path), _docling_to_markdown)

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
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

@app.get("/health")
async def health_check():
    """Lightweight liveness probe used by the launcher."""
    return {"ok": True}


@app.get("/api/status")
async def converter_status():
    """Lets the UI show when the document engine is still warming up."""
    ready = _converter_ready.is_set() and _converter is not None
    return {
        "converter_ready": ready,
        "error": _converter_error,
    }


@app.get("/api/protected-access-check")
async def protected_access_check():
    return run_protected_access_diagnostics()


@app.post("/api/protected-file-check")
async def protected_file_check(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported for this check.")

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = Path(tmp.name)

        result = test_protected_file_access(tmp_path)
        return {
            "file": filename,
            **result,
        }
    finally:
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
    except HTTPException:
        raise
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

    if not converted and not skipped and failed:
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


@app.post("/batch-convert")
async def batch_convert_sse(data: dict = Body(...)):
    """
    Batch-convert DLP/IRM-protected .docx files to Markdown.

    Spawns a hidden Word instance once to handle RMS decryption, saves clean
    temp copies, then converts them in parallel with Docling.
    Streams Server-Sent Events: one per file, then a final summary object.

    Body: { "input_folder": "...", "output_folder": "...", "max_workers": 4 }
    """
    input_folder = (data or {}).get("input_folder")
    output_folder = (data or {}).get("output_folder")
    max_workers = int((data or {}).get("max_workers", 4))

    if not input_folder:
        raise HTTPException(status_code=400, detail="input_folder is required.")
    if not output_folder:
        raise HTTPException(status_code=400, detail="output_folder is required.")
    if max_workers < 1:
        raise HTTPException(status_code=400, detail="max_workers must be >= 1.")

    event_queue: "queue.Queue[dict | None]" = queue.Queue()

    def _emit(event: dict) -> None:
        event_queue.put(event)

    def _run_batch() -> None:
        # Word COM must run on the thread that called CoInitialize — batch_convert
        # handles start_word() and CoUninitialize internally, so this thread owns
        # the COM apartment for the entire batch.
        try:
            summary = word_dispatch_batch_convert(
                input_folder=input_folder,
                output_folder=output_folder,
                max_workers=max_workers,
                progress_callback=_emit,
            )
            event_queue.put(summary)
        except Exception as exc:
            event_queue.put({"status": "failed", "error": str(exc)})
        finally:
            event_queue.put(None)  # sentinel — terminates the SSE stream

    threading.Thread(target=_run_batch, daemon=True, name="batch-convert-sse").start()

    async def _stream_events():
        while True:
            item = await asyncio.to_thread(event_queue.get)
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        _stream_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)