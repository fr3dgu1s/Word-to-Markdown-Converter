import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

APP_URL = "http://127.0.0.1:8000"
HEALTH_TIMEOUT_SECONDS = 20


def _can_reach_server() -> bool:
    try:
        with urlopen(APP_URL, timeout=1.5) as response:
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
        time.sleep(0.5)
    return False


def main() -> None:
    repo_root = Path(__file__).resolve().parent

    if not _can_reach_server():
        _start_server_process(repo_root)
        _wait_until_ready(HEALTH_TIMEOUT_SECONDS)

    if _can_reach_server():
        webbrowser.open(APP_URL)


if __name__ == "__main__":
    main()
