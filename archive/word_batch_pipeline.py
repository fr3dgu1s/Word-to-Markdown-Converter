"""
Word COM-based batch pipeline for DLP/IRM-protected .docx conversion.

Strategy:
  - Word is already running and authenticated on the user's machine.
  - For each protected file the producer thread (main thread of the batch):
      1. Checks whether the file is already open in Word (pre-authenticated).
      2. If not, opens it — Word handles RMS/IRM decryption transparently.
      3. SaveAs2 to a randomly named temp .docx (local save strips the label).
      4. doc.Close() immediately — releases the file lock before Docling touches it.
  - Consumer threads (ThreadPoolExecutor) pick temp-file paths off a queue,
    run the provided docling_convert callable, write Markdown, then delete the
    temp file and its parent directory unconditionally.
  - A bounded queue provides backpressure so the producer never accumulates more
    than max_workers * 2 unprocessed temp files on disk.
  - All COM calls are on the producer thread which owns the CoInitialize context.
"""

import logging
import queue
import shutil
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore
except ImportError:
    pythoncom = None
    win32com = None

logger = logging.getLogger(__name__)

WD_FORMAT_XML_DOCUMENT = 16
WD_ALERTS_NONE = 0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_word_instance() -> Any:
    """
    Attach to the running, authenticated Word instance via COM.

    The calling thread must have already called CoInitialize().
    Raises RuntimeError with a user-facing message if Word is not running.
    """
    if win32com is None:
        raise RuntimeError(
            "pywin32 is not installed. Install with `pip install pywin32`."
        )
    try:
        return win32com.client.GetActiveObject("Word.Application")
    except Exception:
        raise RuntimeError(
            "Please open Microsoft Word and sign in to your M365 account "
            "before running batch conversion."
        )


def save_clean_copy(word_app: Any, protected_path: str) -> str:
    """
    Open the protected .docx in the authenticated Word session, save a clean
    unprotected local copy via SaveAs2, then close it — unless the user already
    had the file open, in which case we leave it open.

    Returns the path to the clean temp .docx (inside a fresh mkdtemp folder).
    Raises RuntimeError with the original exception chained on any failure.
    """
    source_path = Path(protected_path).expanduser().resolve()

    # Check whether the file is already open so we don't reopen or close it.
    doc: Optional[Any] = None
    was_preopen = False
    try:
        for i in range(1, int(word_app.Documents.Count) + 1):
            try:
                candidate = word_app.Documents.Item(i)
                if Path(candidate.FullName).resolve() == source_path:
                    doc = candidate
                    was_preopen = True
                    break
            except Exception:
                continue
    except Exception:
        pass

    if doc is None:
        try:
            doc = word_app.Documents.Open(
                str(source_path),
                ReadOnly=False,
                ConfirmConversions=False,
                AddToRecentFiles=False,
            )
        except Exception as exc:
            raise RuntimeError(
                f"Word could not open '{source_path.name}'. "
                "Ensure your M365 account has rights to this file and Word is signed in. "
                f"Underlying error: {exc}"
            ) from exc

    temp_dir = tempfile.mkdtemp(prefix="word_clean_")
    temp_path = Path(temp_dir) / f"{source_path.stem}_clean.docx"

    try:
        doc.SaveAs2(str(temp_path), FileFormat=WD_FORMAT_XML_DOCUMENT)
    except Exception as exc:
        if not was_preopen:
            try:
                doc.Close(SaveChanges=False)
            except Exception:
                pass
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(
            f"Word opened '{source_path.name}' but could not save a clean copy. "
            "Your account may lack export rights for this sensitivity label. "
            f"Underlying error: {exc}"
        ) from exc

    # Never close a document the user had open themselves.
    if not was_preopen:
        try:
            doc.Close(SaveChanges=False)
        except Exception:
            pass

    return str(temp_path)


def convert_protected_to_md(
    word_app: Any,
    protected_path: str,
    output_md_path: str,
    docling_convert: Callable[[str], str],
) -> None:
    """
    Convert one protected .docx to Markdown.

    Word decrypts; docling_convert handles the actual conversion.
    The temp copy is always deleted in the finally block.
    """
    temp_path: Optional[str] = None
    try:
        temp_path = save_clean_copy(word_app, protected_path)
        markdown = docling_convert(temp_path)
        out = Path(output_md_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(markdown, encoding="utf-8")
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except Exception:
                pass
            try:
                shutil.rmtree(str(Path(temp_path).parent), ignore_errors=True)
            except Exception:
                pass


def batch_convert(
    input_folder: str,
    output_folder: str,
    docling_convert: Callable[[str], str],
    max_workers: int = 4,
    progress_callback: Optional[Callable[[Dict], None]] = None,
) -> Dict:
    """
    Batch-convert all .docx files in input_folder to Markdown in output_folder.

    Word COM operations run sequentially on the calling thread (COM is apartment-
    threaded and cannot be called from multiple threads concurrently).
    Docling conversions run in parallel inside a ThreadPoolExecutor.
    A bounded queue decouples the two so Word-save of file N+1 overlaps
    Docling conversion of file N.

    Returns {"succeeded": [filenames], "failed": {"filename": "error message"}}.
    Each completed file is also reported via progress_callback if provided.
    """
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "pywin32 is required for Word COM batch conversion. "
            "Install with `pip install pywin32`."
        )

    input_path = Path(input_folder).expanduser().resolve()
    output_path = Path(output_folder).expanduser().resolve()
    output_path.mkdir(parents=True, exist_ok=True)

    docx_files = sorted(input_path.glob("*.docx"))
    if not docx_files:
        return {"succeeded": [], "failed": {}}

    com_initialized = False
    try:
        pythoncom.CoInitialize()
        com_initialized = True

        word_app = get_word_instance()
        word_app.DisplayAlerts = WD_ALERTS_NONE

        succeeded: List[str] = []
        failed: Dict[str, str] = {}
        results_lock = threading.Lock()

        # Bounded queue provides backpressure: producer blocks when consumers
        # are more than max_workers * 2 items behind, capping temp-file accumulation.
        work_queue: "queue.Queue[Optional[tuple]]" = queue.Queue(
            maxsize=max_workers * 2
        )

        def _consumer() -> None:
            while True:
                item = work_queue.get()
                try:
                    if item is None:  # sentinel — this consumer is done
                        return
                    temp_path, out_md, filename, save_ms = item
                    t0 = time.perf_counter()
                    err: Optional[str] = None
                    try:
                        markdown = docling_convert(temp_path)
                        out = Path(out_md)
                        out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_text(markdown, encoding="utf-8")
                    except Exception as exc:
                        err = str(exc)
                    finally:
                        try:
                            Path(temp_path).unlink(missing_ok=True)
                        except Exception:
                            pass
                        try:
                            shutil.rmtree(
                                str(Path(temp_path).parent), ignore_errors=True
                            )
                        except Exception:
                            pass

                    elapsed_ms = int((time.perf_counter() - t0) * 1000) + save_ms
                    event: Dict = {
                        "file": filename,
                        "status": "failed" if err else "success",
                        "elapsed_ms": elapsed_ms,
                    }
                    if err:
                        event["error"] = err

                    with results_lock:
                        if err:
                            failed[filename] = err
                        else:
                            succeeded.append(filename)

                    if progress_callback:
                        progress_callback(event)

                    logger.info(
                        "%s | %s | %d ms", filename, event["status"], elapsed_ms
                    )
                finally:
                    work_queue.task_done()

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
                    # Blocks here when consumers are lagging — prevents temp-file pile-up.
                    work_queue.put((temp_path, out_md, filename, save_ms))
                except Exception as exc:
                    elapsed_ms = int((time.perf_counter() - t0) * 1000)
                    event = {
                        "file": filename,
                        "status": "failed",
                        "error": str(exc),
                        "elapsed_ms": elapsed_ms,
                    }
                    with results_lock:
                        failed[filename] = str(exc)
                    if progress_callback:
                        progress_callback(event)
                    logger.error("save_clean_copy failed for %s: %s", filename, exc)

            # Send one sentinel per consumer to shut them down cleanly.
            for _ in range(max_workers):
                work_queue.put(None)

            # Re-raise any unexpected consumer crash (not per-file errors, which are caught above).
            for f in consumer_futures:
                f.result()

        return {"succeeded": succeeded, "failed": failed}

    finally:
        if com_initialized:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
