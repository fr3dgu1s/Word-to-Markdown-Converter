from urllib.request import Request, urlopen

SHUTDOWN_URL = "http://127.0.0.1:8000/api/shutdown"


def main() -> None:
    request = Request(SHUTDOWN_URL, method="POST")
    try:
        urlopen(request, timeout=2)
    except Exception:
        # Silent by design; if server is already down, no user prompt is shown.
        pass


if __name__ == "__main__":
    main()
