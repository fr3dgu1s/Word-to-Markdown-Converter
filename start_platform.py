import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

APP_URL = "http://127.0.0.1:8000"
HEALTH_URL = f"{APP_URL}/health"
HEALTH_TIMEOUT_SECONDS = 45   # generous ceiling; server typically responds in 1-3 s
_PROBE_CONNECT_TIMEOUT = 0.4  # keep each probe short so we detect readiness fast
_POLL_INTERVAL = 0.2          # check every 200 ms


def _can_reach_server() -> bool:
    try:
        with urlopen(HEALTH_URL, timeout=_PROBE_CONNECT_TIMEOUT) as response:
            return 200 <= response.status < 500
    except URLError:
        return False
    except Exception:
        return False


def _pythonw_executable() -> str:
    current = Path(sys.executable)
    pythonw = current.with_name("pythonw.exe")
    if pythonw.exists():
        return str(pythonw)
    return sys.executable


def _start_server_process(repo_root: Path) -> None:
    server_script = repo_root / "server.py"
    creation_flags = 0
    if sys.platform.startswith("win"):
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP
            | subprocess.DETACHED_PROCESS
            | subprocess.CREATE_NO_WINDOW
        )

    subprocess.Popen(
        [_pythonw_executable(), str(server_script)],
        cwd=str(repo_root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
        creationflags=creation_flags,
    )


def _wait_until_ready(timeout_seconds: int) -> bool:
    started_at = time.time()
    while time.time() - started_at < timeout_seconds:
        if _can_reach_server():
            return True
        time.sleep(_POLL_INTERVAL)
    return False


def main() -> None:
    repo_root = Path(__file__).resolve().parent

    already_up = _can_reach_server()
    if not already_up:
        _start_server_process(repo_root)
        already_up = _wait_until_ready(HEALTH_TIMEOUT_SECONDS)

    # Open the browser as soon as the HTTP server is up.
    # Docling continues warming up in the background while the user
    # navigates to the upload page — by the time they select a file it is ready.
    if already_up:
        webbrowser.open(APP_URL)


if __name__ == "__main__":
    main()
