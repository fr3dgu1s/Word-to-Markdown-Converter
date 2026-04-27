import asyncio
import io
import json
import os
import queue
import shutil
import subprocess
import tempfile
import time
import re
import threading
import zipfile
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse

from logging_config import setup_logging
from protected_file_access import (
    convert_docx_with_docling_fallback,
    ProtectedFileAccessError,
    run_protected_access_diagnostics,
    test_protected_file_access,
)
from word_dispatch_pipeline import batch_convert as word_dispatch_batch_convert
from graph_auth import get_auth_client, GraphAuthClient
from cloud_converter import batch_convert_cloud
from mip_helper_client import (
    inspect_file as mip_inspect_file,
    unprotect_file as mip_unprotect_file,
    reapply_protection as mip_reapply_protection,
    cleanup_paths as mip_cleanup_paths,
    MipAccessDeniedError,
    MipReapplyFailedError,
    MipHelperError,
)

logger = setup_logging()

app = FastAPI()


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    import traceback
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "traceback": traceback.format_exc(),
            "path": str(request.url),
        },
    )

# ---------------------------------------------------------------------------
# Docling is loaded lazily in a background thread so the HTTP server is
# reachable within ~1 second of launch.
# ---------------------------------------------------------------------------
_converter_ready = threading.Event()
_converter = None
_converter_error = None


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
    """Block until converter is ready then return it (or raise on init failure)."""
    _converter_ready.wait(timeout=120)
    if _converter_error:
        raise RuntimeError(f"Document converter failed to initialise: {_converter_error}")
    if _converter is None:
        raise RuntimeError("Document converter is not available.")
    return _converter


# ---------------------------------------------------------------------------
# Directory config
# ---------------------------------------------------------------------------

OUTPUTS_ROOT = Path(__file__).resolve().parent / "Outputs"
GLOBAL_IMAGES_DIR = OUTPUTS_ROOT / "Images"
LOGS_DIR = Path(__file__).resolve().parent / "logs"

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
) -> dict:
    original_name = Path(upload_file.filename or "document").stem
    safe_name = get_unique_safe_name(original_name)
    spec_image_folder = GLOBAL_IMAGES_DIR / safe_name
    spec_image_folder.mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    logger.info(f"[CONVERT] start | file={upload_file.filename} | mode=local")

    tmp_path: Optional[Path] = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            shutil.copyfileobj(upload_file.file, tmp)
            tmp_path = Path(tmp.name)

        from docling_core.types.doc import PictureItem  # noqa: PLC0415

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
        return {"file": filename, **result}
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


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
    return {"status": "opened"}


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
    content = data.get("markdown")
    file_path = OUTPUTS_ROOT / f"{doc_name}.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    return {"status": "saved"}


# ---------------------------------------------------------------------------
# Local conversion endpoints
# ---------------------------------------------------------------------------

@app.post("/api/convert")
async def convert_document(file: UploadFile = File(...)):
    try:
        single_result = convert_file_to_markdown(file, include_markdown=True)
        return {
            "markdown": single_result["markdown"],
            "doc_name": single_result["doc_name"],
            "folder_created": str(OUTPUTS_ROOT),
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

    converted = []
    skipped = []
    failed = []

    for upload_file in files:
        filename = upload_file.filename or ""
        if not filename.lower().endswith(".docx"):
            skipped.append({"file": filename, "reason": "Only .docx files are supported for batch conversion."})
            continue
        try:
            item = convert_file_to_markdown(upload_file, include_markdown=False)
            converted.append({"file": filename, "doc_name": item["doc_name"], "output_file": item["output_file"]})
        except Exception as exc:
            logger.exception(f"Unhandled error in /api/convert-batch for {filename}: {exc}")
            failed.append({"file": filename, "error": str(exc)})

    if not converted and not skipped and failed:
        raise HTTPException(status_code=500, detail={"message": "Batch conversion failed for all eligible files.", "failed": failed})

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
    """Batch-convert DLP/IRM-protected .docx files via Word COM + Docling (SSE)."""
    input_folder = (data or {}).get("input_folder")
    output_folder = (data or {}).get("output_folder")
    max_workers = int((data or {}).get("max_workers", 4))

    if not input_folder:
        raise HTTPException(status_code=400, detail="input_folder is required.")
    if not output_folder:
        raise HTTPException(status_code=400, detail="output_folder is required.")
    if max_workers < 1:
        raise HTTPException(status_code=400, detail="max_workers must be >= 1.")

    logger.info(f"[CONVERT] start | mode=batch-local | input={input_folder} | workers={max_workers}")

    event_queue: "queue.Queue[dict | None]" = queue.Queue()

    def _emit(event: dict) -> None:
        if event.get("status") == "done":
            logger.info(f"[CONVERT] done  | file={event.get('file')} | elapsed={event.get('elapsed_ms')}ms | mode=batch-local")
        elif event.get("status") == "failed":
            logger.error(f"[CONVERT] fail  | file={event.get('file')} | error={event.get('error')} | mode=batch-local")
        event_queue.put(event)

    def _run_batch() -> None:
        try:
            summary = word_dispatch_batch_convert(
                input_folder=input_folder,
                output_folder=output_folder,
                max_workers=max_workers,
                progress_callback=_emit,
            )
            event_queue.put(summary)
        except Exception as exc:
            logger.exception(f"Unhandled error in /batch-convert: {exc}")
            event_queue.put({"status": "failed", "error": str(exc)})
        finally:
            event_queue.put(None)

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
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Cloud mode — protection check
# ---------------------------------------------------------------------------

@app.post("/check-protection")
async def check_protection(file: UploadFile = File(...)):
    raw = await file.read()
    protected = not zipfile.is_zipfile(io.BytesIO(raw))
    return {"filename": file.filename, "protected": protected}


# ---------------------------------------------------------------------------
# Cloud mode — auth endpoints
# ---------------------------------------------------------------------------

@app.get("/auth/debug")
def auth_debug():
    import shutil, os, subprocess, traceback
    try:
        return {
            "az_which": shutil.which("az"),
            "az_cmd_which": shutil.which("az.cmd"),
            "PATH": os.environ.get("PATH", ""),
            "cwd": os.getcwd(),
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/auth/status")
def auth_status():
    import shutil, subprocess, json, os, traceback
    try:
        # Resolve az — check PATH and known Windows install locations
        cmd = (
            shutil.which("az")
            or shutil.which("az.cmd")
            or (r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" if os.path.exists(r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd") else None)
            or (r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" if os.path.exists(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd") else None)
        )
        if not cmd:
            return {
                "authenticated": False,
                "account": None,
                "error": "az_not_found",
            }

        # Pass extended PATH so subprocess can find az dependencies
        env = {
            **os.environ,
            "PATH": os.environ.get("PATH", "")
            + r";C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin"
            + r";C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin",
        }

        result = subprocess.run(
            [cmd, "account", "show"],
            capture_output=True,
            text=True,
            timeout=15,
            env=env,
        )

        if result.returncode != 0:
            return {
                "authenticated": False,
                "account": None,
                "error": "not_logged_in",
                "stderr": result.stderr.strip(),
            }

        data = json.loads(result.stdout)
        return {
            "authenticated": True,
            "account": data.get("user", {}).get("name"),
            "error": None,
        }

    except Exception as e:
        return {
            "authenticated": False,
            "account": None,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }


@app.post("/auth/login")
async def auth_login():
    import shutil, subprocess, json, os, asyncio, traceback
    try:
        cmd = (
            shutil.which("az")
            or shutil.which("az.cmd")
            or (r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" if os.path.exists(r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd") else None)
            or (r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" if os.path.exists(r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd") else None)
        )
        if not cmd:
            raise HTTPException(status_code=500, detail="Azure CLI not found")

        env = {
            **os.environ,
            "PATH": os.environ.get("PATH", "")
            + r";C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin"
            + r";C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin",
        }

        def run_login():
            result = subprocess.run(
                [cmd, "login"],
                capture_output=True,
                text=True,
                env=env,
            )
            return result.returncode == 0

        success = await asyncio.get_event_loop().run_in_executor(None, run_login)
        if not success:
            raise HTTPException(status_code=401, detail="Login failed or was cancelled")

        result = subprocess.run(
            [cmd, "account", "show"],
            capture_output=True,
            text=True,
            env=env,
        )
        data = json.loads(result.stdout)
        return {
            "authenticated": True,
            "account": data.get("user", {}).get("name"),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{str(e)}\n{traceback.format_exc()}")


@app.post("/auth/logout")
async def auth_logout():
    cmd = shutil.which("az") or shutil.which("az.cmd")
    if cmd:
        logger.debug(f"subprocess: {cmd} logout")
        result = subprocess.run([cmd, "logout"], capture_output=True, text=True)
        logger.debug(f"returncode: {result.returncode}")
        if result.stderr:
            logger.warning(f"stderr: {result.stderr.strip()}")
    logger.info("[AUTH] logged out")
    return {"authenticated": False, "account": None}


# ---------------------------------------------------------------------------
# Cloud mode — single file convert
# ---------------------------------------------------------------------------

@app.post("/cloud/convert")
async def cloud_convert(data: dict = Body(...)):
    import traceback
    import urllib.parse

    source_url = (data or {}).get("source_url", "").strip()
    dest_sp_url = (data or {}).get("dest_sharepoint_url") or None
    local_dir = (data or {}).get("local_output_dir") or None

    if not source_url:
        raise HTTPException(status_code=400, detail="source_url is required.")
    if not dest_sp_url and not local_dir:
        raise HTTPException(status_code=400, detail="Supply at least one of dest_sharepoint_url or local_output_dir.")

    start = time.time()
    logger.info(f"[CONVERT] start | source={source_url}")

    try:
        # Step 1 — Get token (hard timeout)
        auth = GraphAuthClient()
        try:
            token = await auth.get_token_async()
            logger.info("[CONVERT] token acquired")
        except Exception as e:
            logger.error(f"[CONVERT] token failed | {e}")
            raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

        from graph_client import resolve_url, resolve_output_folder, download_file_bytes, upload_markdown  # noqa: PLC0415
        from cloud_converter import _docx_bytes_to_markdown, is_protected  # noqa: PLC0415

        # Step 2 — Resolve source URL
        try:
            drive_id, item_id = await asyncio.to_thread(resolve_url, source_url, token)
            logger.info(f"[CONVERT] resolved source | drive={drive_id} item={item_id}")
        except Exception as e:
            logger.error(f"[CONVERT] resolve failed | {e}")
            raise HTTPException(status_code=400, detail=f"Could not resolve source URL: {str(e)}")

        # Step 3 — Download
        try:
            file_bytes = await asyncio.to_thread(download_file_bytes, drive_id, item_id, token)
            logger.info(f"[CONVERT] downloaded | {len(file_bytes)} bytes")
        except Exception as e:
            logger.error(f"[CONVERT] download failed | {e}")
            raise HTTPException(status_code=400, detail=f"Download failed: {str(e)}")

        if is_protected(file_bytes):
            logger.info(f"[CONVERT] protected detected | {source_url}")
            tmp_dir = Path(tempfile.mkdtemp(prefix="mip-src-"))
            tmp_input = tmp_dir / "source.docx"
            tmp_input.write_bytes(file_bytes)

            meta = None
            working = None
            final = None
            try:
                # MIP step 1 — capture label/protection metadata.
                try:
                    meta = await asyncio.to_thread(mip_inspect_file, tmp_input)
                    logger.info(
                        f"[MIP] inspected | label={meta.label_name} id={meta.label_id} protected={meta.is_protected}"
                    )
                except MipHelperError as e:
                    logger.error(f"[MIP] inspect failed | {e}")
                    raise HTTPException(status_code=500, detail=f"MIP inspect failed: {e}")

                # MIP step 2 — request a decrypted working copy.
                try:
                    working = await asyncio.to_thread(
                        mip_unprotect_file, tmp_input, meta.metadata_path,
                        os.environ.get("MIP_USER_UPN"),
                    )
                    logger.info(f"[MIP] decrypt allowed | working={working.name}")
                except MipAccessDeniedError as e:
                    logger.warning(f"[MIP] denied | {e}")
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Access denied by Microsoft Purview policy. "
                            "Your account does not have rights to view, edit, or export this file."
                        ),
                    )
                except MipHelperError as e:
                    logger.error(f"[MIP] unprotect failed | {e}")
                    raise HTTPException(status_code=500, detail=f"MIP unprotect failed: {e}")

                # MIP step 3 — convert the decrypted working copy.
                try:
                    working_bytes = working.read_bytes()
                    markdown = await asyncio.to_thread(_docx_bytes_to_markdown, working_bytes)
                    logger.info(f"[CONVERT] edit completed | {len(markdown)} chars")
                except Exception as e:
                    logger.error(f"[CONVERT] protected conversion failed | {e}\n{traceback.format_exc()}")
                    raise HTTPException(status_code=422, detail=f"Conversion failed: {str(e)}")

                # MIP step 4 — write outputs. If uploading the .docx form back
                # to SharePoint, we MUST reapply the original protection first.
                raw_name = urllib.parse.unquote(source_url.rstrip("/").split("/")[-1])
                stem = raw_name[:-5] if raw_name.lower().endswith(".docx") else raw_name
                md_filename = f"{stem}.md"
                results: dict = {
                    "filename": md_filename,
                    "sharepoint_url": None,
                    "local_path": None,
                    "protected": True,
                    "label_name": meta.label_name,
                }

                if dest_sp_url:
                    # The current pipeline uploads Markdown (an unprotected
                    # text artifact) — we refuse this for protected sources to
                    # avoid creating an unlabeled copy of confidential content.
                    logger.warning("[MIP] refusing to upload markdown of a protected file")
                    raise HTTPException(
                        status_code=422,
                        detail=(
                            "Protected files cannot be exported to SharePoint as Markdown. "
                            "Save locally instead, or extend the pipeline to upload an edited "
                            ".docx with reapplied protection."
                        ),
                    )

                if local_dir:
                    try:
                        out = Path(local_dir) / md_filename
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text(markdown, encoding="utf-8")
                        results["local_path"] = str(out)
                        logger.info(f"[CONVERT] saved locally | {out}")
                    except Exception as e:
                        logger.error(f"[CONVERT] local save failed | {e}")
                        raise HTTPException(status_code=500, detail=f"Local save failed: {str(e)}")

                elapsed = round((time.time() - start) * 1000)
                logger.info(f"[CONVERT] done (protected) | {md_filename} | {elapsed}ms")
                return {**results, "elapsed_ms": elapsed, "markdown": markdown}

            finally:
                try:
                    paths = [tmp_input, tmp_dir]
                    if working is not None:
                        paths.append(working)
                    if final is not None:
                        paths.append(final)
                    if meta is not None:
                        paths.append(meta.metadata_path)
                    mip_cleanup_paths(*paths)
                    logger.info("[MIP] cleanup done")
                except Exception as e:
                    logger.warning(f"[MIP] cleanup error | {e}")

        # Step 4 — Convert
        try:
            markdown = await asyncio.to_thread(_docx_bytes_to_markdown, file_bytes)
            logger.info(f"[CONVERT] converted | {len(markdown)} chars")
        except Exception as e:
            logger.error(f"[CONVERT] conversion failed | {e}\n{traceback.format_exc()}")
            raise HTTPException(status_code=422, detail=f"Conversion failed: {str(e)}")

        # Step 5 — Save outputs
        raw_name = urllib.parse.unquote(source_url.rstrip("/").split("/")[-1])
        stem = raw_name[:-5] if raw_name.lower().endswith(".docx") else raw_name
        md_filename = f"{stem}.md"
        results: dict = {"filename": md_filename, "sharepoint_url": None, "local_path": None}

        if dest_sp_url:
            try:
                dest_drive_id, dest_folder_id = await asyncio.to_thread(resolve_output_folder, dest_sp_url, token)
                sp_url = await asyncio.to_thread(
                    upload_markdown, dest_drive_id, dest_folder_id, md_filename, markdown, token
                )
                results["sharepoint_url"] = sp_url
                logger.info(f"[CONVERT] uploaded to SharePoint | {sp_url}")
            except Exception as e:
                logger.error(f"[CONVERT] SharePoint upload failed | {e}")
                raise HTTPException(status_code=500, detail=f"SharePoint upload failed: {str(e)}")

        if local_dir:
            try:
                out = Path(local_dir) / md_filename
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(markdown, encoding="utf-8")
                results["local_path"] = str(out)
                logger.info(f"[CONVERT] saved locally | {out}")
            except Exception as e:
                logger.error(f"[CONVERT] local save failed | {e}")
                raise HTTPException(status_code=500, detail=f"Local save failed: {str(e)}")

        elapsed = round((time.time() - start) * 1000)
        logger.info(f"[CONVERT] done | {md_filename} | {elapsed}ms")
        return {**results, "elapsed_ms": elapsed, "markdown": markdown}

    except HTTPException:
        raise
    except Exception as e:
        elapsed = round((time.time() - start) * 1000)
        logger.exception(f"[CONVERT] unhandled error | {elapsed}ms | {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error: {str(e)}\n{traceback.format_exc()}",
        )


# ---------------------------------------------------------------------------
# Cloud mode — batch convert (SSE)
# ---------------------------------------------------------------------------

@app.post("/cloud/batch-convert")
async def cloud_batch_convert(data: dict = Body(...)):
    source_folder_url = (data or {}).get("source_folder_url", "").strip()
    dest_sp_url = (data or {}).get("dest_sharepoint_url") or None
    local_dir = (data or {}).get("local_output_dir") or None
    max_workers = int((data or {}).get("max_workers", 4))

    if not source_folder_url:
        raise HTTPException(status_code=400, detail="source_folder_url is required.")
    if not dest_sp_url and not local_dir:
        raise HTTPException(status_code=400, detail="Supply at least one of dest_sharepoint_url or local_output_dir.")
    if max_workers < 1:
        raise HTTPException(status_code=400, detail="max_workers must be >= 1.")

    try:
        client = GraphAuthClient()
        token = await client.get_token_async()
    except RuntimeError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {exc}")

    logger.info(f"[CONVERT] start | mode=batch-cloud | source={source_folder_url} | workers={max_workers}")

    event_queue: "queue.Queue[dict | None]" = queue.Queue()

    def _emit(event: dict) -> None:
        if event.get("type") == "file":
            if event.get("status") == "success":
                logger.info(f"[CONVERT] done  | file={event.get('file')} | elapsed={event.get('elapsed_ms')}ms | mode=cloud")
            else:
                logger.error(f"[CONVERT] fail  | file={event.get('file')} | error={event.get('error')} | mode=cloud")
        event_queue.put(event)

    def _run() -> None:
        try:
            batch_convert_cloud(
                source_folder_url=source_folder_url,
                token=token,
                dest_sharepoint_url=dest_sp_url,
                local_output_dir=local_dir,
                max_workers=max_workers,
                progress_callback=_emit,
            )
        except Exception as exc:
            logger.exception(f"Unhandled error in /cloud/batch-convert: {exc}")
            event_queue.put({"type": "error", "message": str(exc)})
        finally:
            event_queue.put(None)

    threading.Thread(target=_run, daemon=True, name="cloud-batch-sse").start()

    async def _stream():
        while True:
            item = await asyncio.to_thread(event_queue.get)
            if item is None:
                break
            yield f"data: {json.dumps(item)}\n\n"

    return StreamingResponse(
        _stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ---------------------------------------------------------------------------
# Log viewer endpoints
# ---------------------------------------------------------------------------

@app.get("/logs/latest")
def logs_latest(lines: int = 100):
    lines = min(max(lines, 1), 500)
    log_path = LOGS_DIR / "app.log"
    if not log_path.exists():
        return {"lines": []}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return {"lines": [ln.rstrip("\n") for ln in all_lines[-lines:]]}


@app.delete("/logs/latest")
def logs_clear():
    log_path = LOGS_DIR / "app.log"
    if log_path.exists():
        open(log_path, "w").close()
    logger.info("[LOGS] Log file cleared by user")
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
