"""
Word-to-Markdown Converter — local FastAPI server.

Endpoints:
    GET    /                       Static index.html
    GET    /health                 Liveness probe
    GET    /api/status             Docling readiness
    POST   /api/convert            Single-file conversion
    POST   /api/convert-batch      Batch conversion (uploaded files)
    POST   /api/convert-folder     Scan a local folder and convert all .docx
    POST   /api/save-changes       Persist edited Markdown
    GET    /api/open-folder        Open the Outputs folder in Explorer
    POST   /api/shutdown           Stop the server
    GET    /logs/latest            Tail app.log
    DELETE /logs/latest            Truncate app.log
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Optional

BASE_DIR = Path(__file__).resolve().parent
PS_BRIDGE = BASE_DIR / "tools" / "export_unprotected_docx.ps1"

PROTECTED_DOC_USER_MESSAGE = (
    "This document appears to be Microsoft Purview-protected. The converter "
    "tried to open it through Word using the current signed-in user, but Word "
    "could not export an unprotected temporary copy. Confirm that Word is "
    "installed, the user is signed in, and the user has permission to open "
    "the document."
)

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from logging_config import setup_logging
from paths import OUTPUTS_ROOT, IMAGES_ROOT, TEMP_ROOT, LOGS_ROOT

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
# Purview-protected document fallback (Word COM via PowerShell bridge)
# ---------------------------------------------------------------------------

# Heuristic substrings indicating the file is likely Purview/IRM-protected
# or otherwise blocked from direct read by Docling.
_PROTECTED_SIGNALS = (
    "encrypted",
    "password",
    "permission",
    "protected",
    "irm",
    "rights management",
    "cannot open",
    "access denied",
    "sensitivity",
    "purview",
    "package not found",  # zipfile error when Docling sees an OLE-encrypted blob
    "bad zip",
    "not a zip file",
    "compdoc",
)


def _should_try_protected_bridge(error: Exception) -> bool:
    message = str(error).lower()
    return any(signal in message for signal in _PROTECTED_SIGNALS)


def _get_powershell_executable() -> str:
    return shutil.which("pwsh") or shutil.which("powershell.exe") or "powershell.exe"


def _export_unprotected_docx_with_powershell(input_path: Path, output_path: Path) -> None:
    """Invoke the Word-COM PowerShell bridge to export an unprotected DOCX copy.

    Relies on the current signed-in Windows/Office identity to decrypt the file.
    Raises ``RuntimeError`` if the bridge fails or does not produce the file.
    """
    if not PS_BRIDGE.exists():
        raise FileNotFoundError(f"PowerShell bridge script not found: {PS_BRIDGE}")

    completed = subprocess.run(
        [
            _get_powershell_executable(),
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", str(PS_BRIDGE),
            "-InputPath", str(input_path),
            "-OutputPath", str(output_path),
        ],
        capture_output=True,
        text=True,
        timeout=300,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "PowerShell decrypt/export bridge failed.\n\n"
            f"STDOUT:\n{completed.stdout}\n\n"
            f"STDERR:\n{completed.stderr}"
        )


def _convert_docx_with_protected_fallback(input_path: Path):
    """Run Docling on ``input_path``; on a likely-protected error, retry via Word COM.

    Returns the Docling ``ConversionResult`` (matching ``converter.convert(...)``
    so callers can keep iterating ``document.iterate_items()`` etc.).

    The temporary unprotected DOCX is created inside a ``TemporaryDirectory`` and
    is removed when this function returns, regardless of success or failure.
    """
    converter = _get_converter()
    input_path = Path(input_path)

    try:
        return converter.convert(input_path)
    except Exception as direct_error:
        if not _should_try_protected_bridge(direct_error):
            raise

        logger.info(
            f"[PROTECTED] Docling failed on {input_path.name}; "
            f"attempting Word COM decrypt bridge"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_docx = Path(temp_dir) / f"{input_path.stem}.unprotected.docx"
            try:
                _export_unprotected_docx_with_powershell(
                    input_path=input_path,
                    output_path=temp_docx,
                )
            except Exception as bridge_error:
                logger.error(f"[PROTECTED] Bridge failed: {bridge_error}")
                raise RuntimeError(PROTECTED_DOC_USER_MESSAGE) from bridge_error

            if not temp_docx.exists():
                raise RuntimeError(
                    "PowerShell bridge completed, but the temporary unprotected "
                    "DOCX was not created."
                )

            logger.info(f"[PROTECTED] Bridge succeeded; re-running Docling")
            return converter.convert(temp_docx)


# ---------------------------------------------------------------------------
# Naming helpers
# ---------------------------------------------------------------------------

_WINDOWS_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_md_basename(stem: str) -> str:
    """Sanitise a filename stem to be safe on Windows while preserving spaces/dots."""
    cleaned = _WINDOWS_FORBIDDEN.sub("", stem).strip().rstrip(".")
    return cleaned or "document"


def safe_image_dir(stem: str) -> str:
    """Lowercase, hyphen-separated stem used as the per-document image folder name."""
    clean = re.sub(r"[^a-zA-Z0-9]+", "-", stem).strip("-").lower()
    return clean or "document"


def batch_output_name(filename: str) -> str:
    """Return the batch output filename for an input .docx (preserves original stem)."""
    stem = Path(filename).stem
    return f"{safe_md_basename(stem)}-BATCH.md"


def single_output_name(filename: str) -> str:
    stem = Path(filename).stem
    return f"{safe_md_basename(stem)}.md"


def _unique_path(folder: Path, filename: str) -> Path:
    """If ``folder/filename`` already exists, append ``-2``, ``-3``, … to the stem."""
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 2
    while True:
        candidate = folder / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _unique_image_dir(stem_slug: str) -> Path:
    folder = IMAGES_ROOT / stem_slug
    if not folder.exists():
        return folder
    counter = 2
    while True:
        candidate = IMAGES_ROOT / f"{stem_slug}-{counter}"
        if not candidate.exists():
            return candidate
        counter += 1


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

def _convert_docx_path_to_markdown(
    src_path: Path,
    *,
    display_name: str,
    output_filename: str,
    include_markdown: bool = True,
) -> dict:
    """Run Docling on a local ``.docx`` file and write Markdown + images.

    Writes the resulting ``.md`` directly under :data:`OUTPUTS_ROOT` using
    ``output_filename``. Extracted images go to ``OUTPUTS_ROOT/Images/<slug>/``.
    ``display_name`` is only used for logging / image-folder naming.
    """
    original_stem = Path(display_name).stem
    image_slug = safe_image_dir(original_stem)
    image_folder = _unique_image_dir(image_slug)
    image_folder.mkdir(parents=True, exist_ok=True)

    md_file_path = _unique_path(OUTPUTS_ROOT, output_filename)

    t0 = time.perf_counter()
    logger.info(f"[CONVERT] start | file={display_name} -> {md_file_path.name}")

    try:
        from docling_core.types.doc import PictureItem  # noqa: PLC0415

        conv_res = _convert_docx_with_protected_fallback(src_path)

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
            tag = f"![spec-image](Images/{image_folder.name}/image_{i}.png)"
            final_markdown = final_markdown.replace("IMAGE_TOKEN", tag, 1)

        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(final_markdown)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.info(f"[CONVERT] done  | file={display_name} | elapsed={elapsed_ms}ms")

        result = {
            "doc_name": md_file_path.stem,
            "output_file": str(md_file_path),
            "image_dir": image_folder.name,
        }
        if include_markdown:
            result["markdown"] = final_markdown
        return result

    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        logger.error(f"[CONVERT] fail  | file={display_name} | elapsed={elapsed_ms}ms | error={exc}")
        raise


def convert_file_to_markdown(
    upload_file: UploadFile,
    *,
    output_filename: str,
    include_markdown: bool = True,
) -> dict:
    """Convert one uploaded ``.docx`` file to Markdown using Docling.

    Spools the upload to a temp file, then delegates to
    :func:`_convert_docx_path_to_markdown`.
    """
    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx", dir=str(TEMP_ROOT)) as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            tmp_path = Path(tmp.name)

        return _convert_docx_path_to_markdown(
            tmp_path,
            display_name=upload_file.filename or "document",
            output_filename=output_filename,
            include_markdown=include_markdown,
        )
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
    output_file = data.get("output_file")
    doc_name = data.get("doc_name")
    content = data.get("markdown", "")

    if output_file:
        target = Path(output_file)
        # Pin the write inside OUTPUTS_ROOT to prevent path traversal.
        try:
            target.resolve().relative_to(OUTPUTS_ROOT.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="output_file must be inside Outputs.")
    elif doc_name:
        target = OUTPUTS_ROOT / f"{safe_md_basename(doc_name)}.md"
    else:
        raise HTTPException(status_code=400, detail="output_file or doc_name is required.")

    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "saved", "path": str(target)}


# ---------------------------------------------------------------------------
# Local conversion endpoints
# ---------------------------------------------------------------------------

@app.post("/api/convert")
async def convert_document(file: UploadFile = File(...)):
    filename = file.filename or ""
    if not filename.lower().endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported.")
    try:
        result = convert_file_to_markdown(
            file,
            output_filename=single_output_name(filename),
            include_markdown=True,
        )
        return {
            "markdown": result["markdown"],
            "doc_name": result["doc_name"],
            "output_file": result["output_file"],
            "output_dir": str(OUTPUTS_ROOT),
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

    converted_files: list[dict] = []
    failed_files: list[dict] = []

    for upload_file in files:
        filename = upload_file.filename or ""
        if not filename.lower().endswith(".docx"):
            failed_files.append({
                "input": filename,
                "error": "Unsupported file type (only .docx is accepted)",
            })
            continue
        try:
            item = convert_file_to_markdown(
                upload_file,
                output_filename=batch_output_name(filename),
                include_markdown=False,
            )
            converted_files.append({
                "input": filename,
                "output": item["output_file"],
            })
        except Exception as exc:
            logger.exception(f"Unhandled error in /api/convert-batch for {filename}: {exc}")
            failed_files.append({
                "input": filename,
                "error": str(exc) or "Document could not be read",
            })

    return {
        "output_dir": str(OUTPUTS_ROOT),
        "converted_count": len(converted_files),
        "failed_count": len(failed_files),
        "converted_files": converted_files,
        "failed_files": failed_files,
    }


@app.post("/api/convert-folder")
async def convert_documents_in_folder(data: dict = Body(...)):
    """Scan a local folder for ``.docx`` files and convert each one.

    Body: ``{"folder_path": "C:/path/to/folder", "recursive": true}``
    The server reads files directly from disk (no upload) — only safe in
    this app because it binds to ``127.0.0.1``.
    """
    raw_path = (data.get("folder_path") or "").strip().strip('"').strip("'")
    if not raw_path:
        raise HTTPException(status_code=400, detail="folder_path is required.")
    recursive = bool(data.get("recursive", True))

    try:
        folder = Path(raw_path).expanduser().resolve()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid folder path: {exc}")

    if not folder.exists() or not folder.is_dir():
        raise HTTPException(status_code=400, detail=f"Folder does not exist: {folder}")

    pattern = "**/*.docx" if recursive else "*.docx"
    # Collect, dedupe (case-insensitive on Windows), skip Word lock files (~$*.docx).
    seen: set[str] = set()
    docx_files: list[Path] = []
    for p in folder.glob(pattern):
        if not p.is_file():
            continue
        if p.name.startswith("~$"):
            continue
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        docx_files.append(p)

    docx_files.sort()
    logger.info(f"[FOLDER-SCAN] folder={folder} recursive={recursive} found={len(docx_files)}")

    if not docx_files:
        return {
            "output_dir": str(OUTPUTS_ROOT),
            "scanned_folder": str(folder),
            "scanned_count": 0,
            "converted_count": 0,
            "failed_count": 0,
            "converted_files": [],
            "failed_files": [],
        }

    converted_files: list[dict] = []
    failed_files: list[dict] = []

    for src in docx_files:
        try:
            item = _convert_docx_path_to_markdown(
                src,
                display_name=src.name,
                output_filename=batch_output_name(src.name),
                include_markdown=False,
            )
            converted_files.append({"input": str(src), "output": item["output_file"]})
        except Exception as exc:
            logger.exception(f"Unhandled error in /api/convert-folder for {src}: {exc}")
            failed_files.append({
                "input": str(src),
                "error": str(exc) or "Document could not be read",
            })

    return {
        "output_dir": str(OUTPUTS_ROOT),
        "scanned_folder": str(folder),
        "scanned_count": len(docx_files),
        "converted_count": len(converted_files),
        "failed_count": len(failed_files),
        "converted_files": converted_files,
        "failed_files": failed_files,
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
