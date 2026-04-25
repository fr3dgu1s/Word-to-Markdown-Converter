"""
Word COM dispatch pipeline for DLP/IRM-protected .docx batch conversion.

Architecture:
  - Word is spawned once as a hidden background process via Dispatch.
  - Producer (the dedicated COM thread that called start_word) opens each file,
    SaveAs2 a clean unprotected copy to a per-file mkdtemp, closes the doc,
    and puts (temp_path, output_md_path) on a queue.Queue.
  - Consumer pool (ThreadPoolExecutor) picks pairs off the queue, runs Docling,
    writes Markdown, then deletes the temp file and folder unconditionally.
  - A bounded queue provides backpressure so the producer cannot accumulate more
    than ~2x max_workers unprocessed temp files on disk.
  - Word is quit and COM uninitialized exactly once in a finally block after the
    entire batch — never per file.
"""

import logging
import os
import queue
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
except ImportError:
    pythoncom = None
    win32com = None

logger = logging.getLogger(__name__)

WD_FORMAT_XML_DOCUMENT = 16
WD_ALERTS_NONE = 0

_thread_local = threading.local()


def _get_thread_converter():
    """Return a thread-local DocumentConverter, creating it on first use."""
    if not hasattr(_thread_local, "converter"):
        from docling.document_converter import DocumentConverter  # noqa: PLC0415
        _thread_local.converter = DocumentConverter()
    return _thread_local.converter


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def start_word() -> any:
    """
    Initialize COM on the calling thread and spawn a hidden Word instance.

    The calling thread becomes the COM apartment owner — every subsequent Word
    COM call for this batch must happen on this same thread.
    Raises RuntimeError if COM initialization or Word launch fails.
    """
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "pywin32 is not installed. Install with `pip install pywin32`."
        )

    try:
        pythoncom.CoInitialize()
    except Exception as exc:
        raise RuntimeError(f"COM initialization failed: {exc}") from exc

    try:
        word = win32com.client.Dispatch("Word.Application")
    except Exception as exc:
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        raise RuntimeError(
            "Failed to start Microsoft Word via COM automation. "
            "Ensure Word is installed and accessible under the current user account. "
            f"Underlying error: {exc}"
        ) from exc

    try:
        word.Visible = False
        word.DisplayAlerts = WD_ALERTS_NONE
    except Exception as exc:
        try:
            word.Quit()
        except Exception:
            pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
        raise RuntimeError(
            f"Word started but could not be configured for silent automation: {exc}"
        ) from exc

    return word


def save_clean_copy(word_app: any, protected_path: str) -> str:
    """
    Open the protected .docx in the authenticated Word session, save a clean
    unprotected copy to a fresh mkdtemp folder, and close the document
    immediately — fully releasing the file lock before Docling touches it.

    Returns the path to the clean temp .docx.
    Raises RuntimeError with the original exception chained on any failure.
    The temp directory is deleted by the caller (convert_and_cleanup).
    """
    source_str = str(Path(protected_path).expanduser().resolve())
    doc = None
    temp_dir: Optional[str] = None

    try:
        doc = word_app.Documents.Open(
            source_str,
            ReadOnly=False,
            ConfirmConversions=False,
            AddToRecentFiles=False,
            Visible=False,
        )
    except Exception as exc:
        raise RuntimeError(
            f"Word could not open '{Path(protected_path).name}'. "
            "Ensure your M365 account has rights to this file and Word is authenticated. "
            f"Underlying error: {exc}"
        ) from exc

    try:
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, uuid4().hex + ".docx")

        try:
            doc.SaveAs2(temp_path, FileFormat=WD_FORMAT_XML_DOCUMENT)
        except Exception as exc:
            raise RuntimeError(
                f"Word opened '{Path(protected_path).name}' but could not save a clean copy. "
                "Your account may lack export/save rights for this sensitivity label. "
                f"Underlying error: {exc}"
            ) from exc

        return temp_path

    except Exception:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise

    finally:
        # Always close the document — the lock must be released before Docling runs.
        if doc is not None:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass


def convert_and_cleanup(temp_docx_path: str, output_md_path: str) -> None:
    """
    Pass the clean temp .docx to the thread-local Docling pipeline and write
    Markdown to output_md_path. The temp file and its parent mkdtemp folder
    are deleted unconditionally in the finally block — no unprotected copy
    survives regardless of conversion outcome.
    """
    try:
        conv_res = _get_thread_converter().convert(Path(temp_docx_path))
        markdown = conv_res.document.export_to_markdown()
        out = Path(output_md_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    finally:
        try:
            Path(temp_docx_path).unlink(missing_ok=True)
        except Exception:
            pass
        try:
            shutil.rmtree(str(Path(temp_docx_path).parent), ignore_errors=True)
        except Exception:
            pass


def batch_convert(
    input_folder: str,
    output_folder: str,
    max_workers: int = 4,
    progress_callback: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """
    Batch-convert all .docx files in input_folder to Markdown in output_folder.

    Calls start_word() to initialize COM and spawn Word on this thread.
    Word is quit and COM is uninitialized exactly once in a finally block.
    Per-file failures on either the save or convert side do not stop the batch.

    Returns {"succeeded": [filenames], "failed": {"filename": "error message"}}.
    Logs per file to stdout: filename, status, stage that failed (if any), elapsed ms,
    and running total count.
    """
    input_path = Path(input_folder).expanduser().resolve()
    output_path = Path(output_folder).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    docx_files = sorted(input_path.glob("*.docx"))
    if not docx_files:
        return {"succeeded": [], "failed": {}}

    total = len(docx_files)
    word_app = None

    try:
        word_app = start_word()

        succeeded: List[str] = []
        failed: Dict[str, str] = {}
        state_lock = threading.Lock()
        running_total = [0]  # mutable counter shared across threads

        # Bounded queue — producer blocks when consumers are more than
        # max_workers * 2 items behind, preventing temp-file accumulation.
        task_queue: "queue.Queue[Optional[tuple]]" = queue.Queue(
            maxsize=max_workers * 2
        )

        def _consumer() -> None:
            while True:
                item = task_queue.get()
                try:
                    if item is None:  # sentinel — this consumer exits
                        return
                    temp_path, out_md, filename, save_ms = item
                    t0 = time.perf_counter()
                    err: Optional[str] = None
                    try:
                        convert_and_cleanup(temp_path, out_md)
                    except Exception as exc:
                        err = str(exc)

                    elapsed_ms = int((time.perf_counter() - t0) * 1000) + save_ms
                    status = "failed" if err else "success"
                    stage = " (docling)" if err else ""

                    with state_lock:
                        running_total[0] += 1
                        n = running_total[0]
                        if err:
                            failed[filename] = err
                        else:
                            succeeded.append(filename)

                    print(
                        f"[{n}/{total}] {filename} {status}{stage} {elapsed_ms}ms"
                        + (f" — {err}" if err else "")
                    )

                    event: Dict = {
                        "file": filename,
                        "status": status,
                        "elapsed_ms": elapsed_ms,
                    }
                    if err:
                        event["error"] = err
                    if progress_callback:
                        progress_callback(event)

                finally:
                    task_queue.task_done()

        with ThreadPoolExecutor(
            max_workers=max_workers, thread_name_prefix="docling"
        ) as executor:
            consumer_futures = [executor.submit(_consumer) for _ in range(max_workers)]

            # Producer: sequential Word COM on this thread only.
            for docx_file in docx_files:
                filename = docx_file.name
                out_md = str(output_path / f"{docx_file.stem}.md")
                t0 = time.perf_counter()
                try:
                    temp_path = save_clean_copy(word_app, str(docx_file))
                    save_ms = int((time.perf_counter() - t0) * 1000)
                    # Blocks here when consumers are lagging — limits disk use.
                    task_queue.put((temp_path, out_md, filename, save_ms))
                except Exception as exc:
                    elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    with state_lock:
                        running_total[0] += 1
                        n = running_total[0]
                        failed[filename] = str(exc)

                    print(
                        f"[{n}/{total}] {filename} failed (save) {elapsed_ms}ms — {exc}"
                    )
                    event = {
                        "file": filename,
                        "status": "failed",
                        "error": str(exc),
                        "elapsed_ms": elapsed_ms,
                    }
                    if progress_callback:
                        progress_callback(event)

            # One sentinel per consumer — each worker exits on its sentinel.
            for _ in range(max_workers):
                task_queue.put(None)

            # Wait for all Docling jobs to drain.
            task_queue.join()

            # Propagate any unexpected consumer crash (not per-file errors).
            for f in consumer_futures:
                f.result()

        return {"succeeded": succeeded, "failed": failed}

    finally:
        if word_app is not None:
            try:
                word_app.Quit()
            except Exception:
                pass
        try:
            pythoncom.CoUninitialize()
        except Exception:
            pass
