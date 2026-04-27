"""
Cloud (SharePoint / OneDrive) conversion pipeline.

Downloads .docx files via Microsoft Graph, converts with Docling,
and optionally uploads Markdown back to SharePoint and/or saves locally.

All functions are stateless with respect to auth — callers pass the token.
"""

import io
import logging
import shutil
import tempfile
import threading
import time
import zipfile
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("wordtomd.converter")

from graph_client import (
    download_file_bytes,
    list_folder_docx,
    resolve_output_folder,
    resolve_url,
    upload_markdown,
)

_thread_local = threading.local()


def _get_converter():
    if not hasattr(_thread_local, "converter"):
        from docling.document_converter import DocumentConverter  # noqa: PLC0415
        _thread_local.converter = DocumentConverter()
    return _thread_local.converter


# ---------------------------------------------------------------------------
# Protection check
# ---------------------------------------------------------------------------


def is_protected(file_bytes: bytes) -> bool:
    """
    Return True if the bytes do NOT look like a valid ZIP/DOCX.

    A standard .docx is a ZIP archive starting with PK\x03\x04.
    DLP/IRM-protected files are a different format (OLE compound document)
    and will fail the zipfile check.
    """
    return not zipfile.is_zipfile(io.BytesIO(file_bytes))


# ---------------------------------------------------------------------------
# Single-file conversion
# ---------------------------------------------------------------------------


def _docx_bytes_to_markdown(file_bytes: bytes) -> str:
    """Write bytes to a temp .docx, run Docling, return Markdown string."""
    tmp_dir = tempfile.mkdtemp(prefix="cloud_conv_")
    try:
        tmp_path = Path(tmp_dir) / "input.docx"
        tmp_path.write_bytes(file_bytes)
        conv_res = _get_converter().convert(tmp_path)
        return conv_res.document.export_to_markdown()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def convert_cloud_file(
    *,
    drive_id: str,
    item_id: str,
    filename: str,
    token: str,
    dest_drive_id: Optional[str] = None,
    dest_folder_id: Optional[str] = None,
    local_output_dir: Optional[str] = None,
) -> dict:
    """
    Download one .docx from Graph, convert it, and deliver the result.

    At least one of dest_folder_id or local_output_dir must be supplied.
    Returns:
        {
          "filename": str,
          "protected": bool,
          "sharepoint_url": str | None,
          "local_path": str | None,
          "elapsed_ms": int,
        }
    Raises RuntimeError on conversion failure.
    """
    if dest_folder_id is None and local_output_dir is None:
        raise ValueError("Supply at least one of dest_folder_id or local_output_dir.")

    t0 = time.perf_counter()
    logger.info(f"[CONVERT] start | file={filename} | mode=cloud")
    file_bytes = download_file_bytes(drive_id, item_id, token)
    protected = is_protected(file_bytes)

    if protected:
        logger.error(f"[CONVERT] fail  | file={filename} | mode=cloud | error=DLP/IRM protected")
        raise RuntimeError(
            f"{filename} appears to be DLP/IRM-protected and cannot be converted "
            "without a local Word session. Use the Batch (Local) mode instead."
        )

    stem = Path(filename).stem
    md_filename = f"{stem}.md"
    markdown = _docx_bytes_to_markdown(file_bytes)

    sharepoint_url: Optional[str] = None
    local_path: Optional[str] = None

    if dest_folder_id and dest_drive_id:
        sharepoint_url = upload_markdown(dest_drive_id, dest_folder_id, md_filename, markdown, token)

    if local_output_dir:
        out = Path(local_output_dir) / md_filename
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
        local_path = str(out)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    logger.info(f"[CONVERT] done  | file={filename} | elapsed={elapsed_ms}ms | mode=cloud")
    return {
        "filename": filename,
        "protected": protected,
        "sharepoint_url": sharepoint_url,
        "local_path": local_path,
        "elapsed_ms": elapsed_ms,
    }


# ---------------------------------------------------------------------------
# Batch conversion
# ---------------------------------------------------------------------------


def batch_convert_cloud(
    source_folder_url: str,
    token: str,
    *,
    dest_sharepoint_url: Optional[str] = None,
    local_output_dir: Optional[str] = None,
    max_workers: int = 4,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    """
    Convert all .docx files in a SharePoint/OneDrive folder.

    Emits progress events via progress_callback:
      {"type": "start", "total": N}
      {"type": "file", "file": name, "status": "success"|"failed", "elapsed_ms": int, ...}
      {"type": "summary", "succeeded": [...], "failed": {...}}

    Returns {"succeeded": [...], "failed": {...}}.
    """
    if dest_sharepoint_url is None and local_output_dir is None:
        raise ValueError("Supply at least one of dest_sharepoint_url or local_output_dir.")

    def emit(event: dict) -> None:
        if progress_callback:
            progress_callback(event)

    # Resolve source folder
    src_drive_id, src_folder_id = resolve_url(source_folder_url, token)
    items = list_folder_docx(src_drive_id, src_folder_id, token)

    # Resolve destination folder (SharePoint) once up front
    dest_drive_id: Optional[str] = None
    dest_folder_id: Optional[str] = None
    if dest_sharepoint_url:
        dest_drive_id, dest_folder_id = resolve_output_folder(dest_sharepoint_url, token)

    if local_output_dir:
        Path(local_output_dir).mkdir(parents=True, exist_ok=True)

    total = len(items)
    emit({"type": "start", "total": total})

    if total == 0:
        summary = {"type": "summary", "succeeded": [], "failed": {}}
        emit(summary)
        return {"succeeded": [], "failed": {}}

    succeeded: list[str] = []
    failed: dict[str, str] = {}
    lock = threading.Lock()

    import queue
    from concurrent.futures import ThreadPoolExecutor

    task_queue: "queue.Queue[Optional[dict]]" = queue.Queue()
    for item in items:
        task_queue.put(item)
    for _ in range(max_workers):
        task_queue.put(None)  # sentinels

    def worker() -> None:
        while True:
            item = task_queue.get()
            try:
                if item is None:
                    return
                filename = item["name"]
                try:
                    result = convert_cloud_file(
                        drive_id=item["drive_id"],
                        item_id=item["item_id"],
                        filename=filename,
                        token=token,
                        dest_drive_id=dest_drive_id,
                        dest_folder_id=dest_folder_id,
                        local_output_dir=local_output_dir,
                    )
                    with lock:
                        succeeded.append(filename)
                    emit({
                        "type": "file",
                        "file": filename,
                        "status": "success",
                        "elapsed_ms": result["elapsed_ms"],
                        "sharepoint_url": result["sharepoint_url"],
                        "local_path": result["local_path"],
                    })
                except Exception as exc:
                    with lock:
                        failed[filename] = str(exc)
                    emit({
                        "type": "file",
                        "file": filename,
                        "status": "failed",
                        "error": str(exc),
                    })
            finally:
                task_queue.task_done()

    with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="cloud-conv") as executor:
        futures = [executor.submit(worker) for _ in range(max_workers)]
        task_queue.join()
        for f in futures:
            f.result()

    summary = {"type": "summary", "succeeded": succeeded, "failed": failed}
    emit(summary)
    return {"succeeded": succeeded, "failed": failed}
