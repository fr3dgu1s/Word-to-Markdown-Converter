"""
MSAL device-code authentication for Microsoft Graph.

Token cache is persisted to %LOCALAPPDATA%\WordToMD\token_cache.json so the
user authenticates once and the session survives app restarts.

Usage:
  Set the GRAPH_CLIENT_ID environment variable to your Azure AD app's client ID.
  Register the app as a mobile/desktop app with redirect URI:
    https://login.microsoftonline.com/common/oauth2/nativeclient

  auth = get_auth_client()
  token = auth.get_token()
"""

import os
import threading
from pathlib import Path
from typing import Optional

try:
    import msal  # type: ignore
except ImportError:
    msal = None

SCOPES = [
    "https://graph.microsoft.com/Files.ReadWrite.All",
    "https://graph.microsoft.com/Sites.ReadWrite.All",
]

_CACHE_DIR = (
    Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    / "WordToMD"
)
_CACHE_PATH = _CACHE_DIR / "token_cache.json"


class GraphAuthClient:
    def __init__(self) -> None:
        if msal is None:
            raise RuntimeError(
                "msal is not installed. Run `pip install msal` to enable cloud mode."
            )

        client_id = os.environ.get("GRAPH_CLIENT_ID", "").strip()
        if not client_id:
            raise RuntimeError(
                "GRAPH_CLIENT_ID environment variable is not set. "
                "Register an Azure AD app (mobile/desktop platform) and export the client ID. "
                "See README for step-by-step instructions."
            )

        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

        self._cache = msal.SerializableTokenCache()
        if _CACHE_PATH.exists():
            try:
                self._cache.deserialize(_CACHE_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass

        self._app = msal.PublicClientApplication(
            client_id=client_id,
            authority="https://login.microsoftonline.com/organizations",
            token_cache=self._cache,
        )
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _save_cache(self) -> None:
        if self._cache.has_state_changed:
            try:
                _CACHE_PATH.write_text(self._cache.serialize(), encoding="utf-8")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        return bool(self._app.get_accounts())

    def get_account(self) -> Optional[str]:
        accounts = self._app.get_accounts()
        return accounts[0].get("username") if accounts else None

    def get_token(self) -> str:
        """Return a valid access token via silent refresh. Raises if not signed in."""
        with self._lock:
            accounts = self._app.get_accounts()
            if not accounts:
                raise RuntimeError(
                    "Not signed in. Use /auth/login to authenticate first."
                )
            result = self._app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._save_cache()
                return result["access_token"]
            raise RuntimeError(
                "Token refresh failed. Please sign in again via /auth/login. "
                f"MSAL error: {result.get('error_description', 'unknown') if result else 'no result'}"
            )

    def start_device_code_flow(self) -> dict:
        """Initiate device code flow. Returns the flow dict (contains user_code + verification_uri)."""
        flow = self._app.initiate_device_flow(SCOPES)
        if "user_code" not in flow:
            raise RuntimeError(
                "Failed to start device code flow. "
                f"Error: {flow.get('error_description', flow.get('error', 'unknown'))}"
            )
        return flow

    def complete_device_code_flow(self, flow: dict) -> dict:
        """Poll until the user completes sign-in. Blocking — run in a thread."""
        result = self._app.acquire_token_by_device_flow(flow)
        if "access_token" in result:
            self._save_cache()
            return result
        raise RuntimeError(
            "Authentication failed or timed out. "
            f"Error: {result.get('error_description', result.get('error', 'unknown'))}"
        )

    def logout(self) -> None:
        with self._lock:
            for account in self._app.get_accounts():
                self._app.remove_account(account)
            self._save_cache()


# ---------------------------------------------------------------------------
# Lazy singleton — does not crash the server if GRAPH_CLIENT_ID is absent
# ---------------------------------------------------------------------------

_client: Optional[GraphAuthClient] = None
_client_lock = threading.Lock()


def get_auth_client() -> GraphAuthClient:
    global _client
    with _client_lock:
        if _client is None:
            _client = GraphAuthClient()
        return _client
