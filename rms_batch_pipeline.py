import os
import queue
import shutil
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional


DONE_SENTINEL = "###DONE###"


def _escape_ps_single_quoted(value: str) -> str:
    return value.replace("'", "''")


class PowerShellSession:
    """Persistent PowerShell process used for sequential RMS decrypt commands."""

    def __init__(self, command_timeout_seconds: int = 300) -> None:
        self.command_timeout_seconds = command_timeout_seconds
        self.process: Optional[subprocess.Popen[str]] = None
        self._stdout_queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stderr_queue: queue.Queue[Optional[str]] = queue.Queue()
        self._stdout_thread: Optional[threading.Thread] = None
        self._stderr_thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()

    def __enter__(self):
        self.process = subprocess.Popen(
            [
                "powershell.exe",
                "-ExecutionPolicy",
                "Bypass",
                "-NonInteractive",
                "-Command",
                "-",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )

        assert self.process.stdout is not None
        assert self.process.stderr is not None

        self._stdout_thread = threading.Thread(
            target=self._reader_loop,
            args=(self.process.stdout, self._stdout_queue),
            daemon=True,
            name="powershell-stdout-reader",
        )
        self._stderr_thread = threading.Thread(
            target=self._reader_loop,
            args=(self.process.stderr, self._stderr_queue),
            daemon=True,
            name="powershell-stderr-reader",
        )
        self._stdout_thread.start()
        self._stderr_thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.process is None:
            return

        try:
            if self.process.stdin and not self.process.stdin.closed:
                self.process.stdin.write("exit\n")
                self.process.stdin.flush()
                self.process.stdin.close()
        except Exception:
            pass

        try:
            self.process.wait(timeout=10)
        except Exception:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception:
                self.process.kill()

    @staticmethod
    def _reader_loop(stream, sink: "queue.Queue[Optional[str]]") -> None:
        try:
            for raw in iter(stream.readline, ""):
                sink.put(raw.rstrip("\r\n"))
        finally:
            sink.put(None)

    def send_command(self, cmd: str) -> tuple[str, str]:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("PowerShellSession is not started. Use it as a context manager.")

        wrapped = (
            "$Error.Clear();\n"
            f"{cmd}\n"
            f"Write-Output '{DONE_SENTINEL}'\n"
            f"[Console]::Error.WriteLine('{DONE_SENTINEL}')\n"
        )

        with self._send_lock:
            self.process.stdin.write(wrapped)
            self.process.stdin.flush()

            stdout_lines: list[str] = []
            stderr_lines: list[str] = []
            stdout_done = False
            stderr_done = False

            deadline = time.time() + self.command_timeout_seconds
            while not (stdout_done and stderr_done):
                if time.time() > deadline:
                    raise TimeoutError("Timed out waiting for PowerShell command to finish.")

                if not stdout_done:
                    try:
                        out_line = self._stdout_queue.get(timeout=0.05)
                    except queue.Empty:
                        out_line = "__QUEUE_EMPTY__"
                    if out_line is None:
                        raise RuntimeError("PowerShell stdout closed unexpectedly.")
                    if out_line != "__QUEUE_EMPTY__":
                        if out_line.strip() == DONE_SENTINEL:
                            stdout_done = True
                        else:
                            stdout_lines.append(out_line)

                if not stderr_done:
                    try:
                        err_line = self._stderr_queue.get(timeout=0.05)
                    except queue.Empty:
                        err_line = "__QUEUE_EMPTY__"
                    if err_line is None:
                        raise RuntimeError("PowerShell stderr closed unexpectedly.")
                    if err_line != "__QUEUE_EMPTY__":
                        if err_line.strip() == DONE_SENTINEL:
                            stderr_done = True
                        else:
                            stderr_lines.append(err_line)

            return "\n".join(stdout_lines).strip(), "\n".join(stderr_lines).strip()


def check_aip_available() -> bool:
    probe = subprocess.run(
        [
            "powershell.exe",
            "-NonInteractive",
            "-Command",
            "Get-Command Unprotect-RMSFile -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name",
        ],
        capture_output=True,
        text=True,
        timeout=25,
        check=False,
    )

    name = (probe.stdout or "").strip()
    if name.lower() == "unprotect-rmsfile":
        return True

    raise RuntimeError(
        "Unprotect-RMSFile is not available. Install one of the following and retry:\n"
        "- AIP unified labeling client: https://www.microsoft.com/download/details.aspx?id=53018\n"
        "- PowerShell module: Install-Module -Name AIPService"
    )


def unprotect_rms_file(session: PowerShellSession, protected_path: str) -> str:
    source = Path(protected_path).expanduser().resolve()
    if not source.exists():
        raise RuntimeError(f"Protected file not found: {source}")

    output_dir = Path(tempfile.mkdtemp(prefix="rms-unprotected-"))
    escaped_source = _escape_ps_single_quoted(str(source))
    escaped_output = _escape_ps_single_quoted(str(output_dir))

    cmd = (
        f"Unprotect-RMSFile -File '{escaped_source}' -OutputFolder '{escaped_output}' -ErrorAction Stop"
    )

    stdout, stderr = session.send_command(cmd)

    decrypted_candidates = list(output_dir.glob("*.docx"))
    if decrypted_candidates:
        return str(decrypted_candidates[0])

    shutil.rmtree(output_dir, ignore_errors=True)
    details = stderr or stdout or "No output file produced."
    raise RuntimeError(f"RMS decryption failed for {source.name}: {details}")


_thread_local = threading.local()


def _get_thread_converter():
    converter = getattr(_thread_local, "converter", None)
    if converter is not None:
        return converter

    from docling.document_converter import DocumentConverter  # noqa: PLC0415

    converter = DocumentConverter()
    _thread_local.converter = converter
    return converter


def convert_and_cleanup(decrypted_path: str, output_md_path: str) -> None:
    decrypted = Path(decrypted_path)
    out_md = Path(output_md_path)

    try:
        conv_res = _get_thread_converter().convert(decrypted)
        markdown = conv_res.document.export_to_markdown()

        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(markdown, encoding="utf-8")
    finally:
        try:
            if decrypted.exists():
                decrypted.unlink(missing_ok=True)
        finally:
            parent = decrypted.parent
            if parent.exists() and parent.name.startswith("rms-unprotected-"):
                shutil.rmtree(parent, ignore_errors=True)


def _batch_convert_fast_internal(
    input_folder: str,
    output_folder: str,
    max_conversion_workers: int = 4,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    check_aip_available()

    input_dir = Path(input_folder).expanduser().resolve()
    output_dir = Path(output_folder).expanduser().resolve()

    if not input_dir.exists() or not input_dir.is_dir():
        raise RuntimeError(f"Input folder not found or invalid: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() == ".docx"])

    succeeded: list[str] = []
    failed: dict[str, str] = {}
    lock = threading.Lock()
    processed_count = 0
    task_queue: queue.Queue[Optional[tuple[str, str, str, float]]] = queue.Queue(maxsize=max(8, max_conversion_workers * 2))

    def emit(event: dict) -> None:
        if progress_callback:
            progress_callback(event)

    def log_result(filename: str, status: str, elapsed_ms: int, error: Optional[str] = None) -> None:
        nonlocal processed_count
        with lock:
            processed_count += 1
            total = len(files)
        if status == "success":
            print(f"[{processed_count}/{total}] {filename} success in {elapsed_ms} ms")
        else:
            print(f"[{processed_count}/{total}] {filename} failed in {elapsed_ms} ms: {error}")

    def consumer_loop() -> None:
        while True:
            item = task_queue.get()
            if item is None:
                task_queue.task_done()
                break

            filename, decrypted_path, output_md_path, started = item
            try:
                convert_and_cleanup(decrypted_path, output_md_path)
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                with lock:
                    succeeded.append(filename)
                log_result(filename, "success", elapsed_ms)
                emit({"file": filename, "status": "success", "elapsed_ms": elapsed_ms})
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                with lock:
                    failed[filename] = str(exc)
                log_result(filename, "failed", elapsed_ms, str(exc))
                emit({"file": filename, "status": "failed", "elapsed_ms": elapsed_ms})
            finally:
                task_queue.task_done()

    with ThreadPoolExecutor(max_workers=max_conversion_workers) as executor:
        workers = [executor.submit(consumer_loop) for _ in range(max_conversion_workers)]

        with PowerShellSession() as session:
            for file_path in files:
                started = time.perf_counter()
                filename = file_path.name
                output_md_path = str(output_dir / f"{file_path.stem}.md")

                try:
                    decrypted_path = unprotect_rms_file(session, str(file_path))
                    task_queue.put((filename, decrypted_path, output_md_path, started))
                except Exception as exc:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    with lock:
                        failed[filename] = str(exc)
                    log_result(filename, "failed", elapsed_ms, str(exc))
                    emit({"file": filename, "status": "failed", "elapsed_ms": elapsed_ms})

        for _ in range(max_conversion_workers):
            task_queue.put(None)

        task_queue.join()

        for worker in workers:
            worker.result()

    return {"succeeded": succeeded, "failed": failed}


def batch_convert_fast(
    input_folder: str,
    output_folder: str,
    max_conversion_workers: int = 4,
) -> dict:
    return _batch_convert_fast_internal(
        input_folder=input_folder,
        output_folder=output_folder,
        max_conversion_workers=max_conversion_workers,
        progress_callback=None,
    )


def batch_convert_fast_with_progress(
    input_folder: str,
    output_folder: str,
    max_conversion_workers: int = 4,
    progress_callback: Optional[Callable[[dict], None]] = None,
) -> dict:
    return _batch_convert_fast_internal(
        input_folder=input_folder,
        output_folder=output_folder,
        max_conversion_workers=max_conversion_workers,
        progress_callback=progress_callback,
    )
