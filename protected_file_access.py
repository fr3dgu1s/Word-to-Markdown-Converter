import json
import os
import subprocess
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import win32com.client  # type: ignore
except ImportError:
    win32com = None


class ProtectedFileAccessError(Exception):
    pass


def _import_requests():
    try:
        import requests  # type: ignore
        return requests
    except ImportError as exc:
        raise ProtectedFileAccessError(
            "Missing dependency 'requests'. Install requirements to use protected-file access."
        ) from exc


def _import_msal():
    try:
        import msal  # type: ignore
        return msal
    except ImportError as exc:
        raise ProtectedFileAccessError(
            "Missing dependency 'msal'. Install requirements to use protected-file access."
        ) from exc


def _get_graph_token_from_azure_cli() -> Optional[str]:
    """Reuse the user's existing az login session for Graph when available."""
    try:
        result = subprocess.run(
            [
                "az",
                "account",
                "get-access-token",
                "--resource-type",
                "ms-graph",
                "--query",
                "accessToken",
                "-o",
                "tsv",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    if result.returncode != 0:
        return None

    token = (result.stdout or "").strip()
    return token or None


def _build_token_cache(cache_path: Path) -> Any:
    msal = _import_msal()
    cache = msal.SerializableTokenCache()
    if cache_path.exists():
        cache.deserialize(cache_path.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: Any, cache_path: Path) -> None:
    if cache.has_state_changed:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(cache.serialize(), encoding="utf-8")


def is_file_dlp_protected(file_path: Path) -> bool:
    """Best-effort protection detection for Office documents."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Encrypted Office packages are often not readable as a regular .docx zip.
    if not zipfile.is_zipfile(file_path):
        return True

    with zipfile.ZipFile(file_path, "r") as zf:
        names = {name.lower() for name in zf.namelist()}

    if "encryptioninfo" in names or "encryptedpackage" in names:
        return True

    return False


def get_current_identity() -> Dict[str, str]:
    """Acquire delegated token for the current user and return basic identity details."""
    requests = _import_requests()

    # First, try Azure CLI token from current signed-in identity.
    cli_token = _get_graph_token_from_azure_cli()
    if cli_token:
        headers = {"Authorization": f"Bearer {cli_token}"}
        me = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=20)
        if me.status_code == 200:
            profile = me.json()
            return {
                "display_name": profile.get("displayName", ""),
                "upn": profile.get("userPrincipalName", ""),
                "oid": profile.get("id", ""),
                "tenant": "azure-cli",
                "scopes": json.dumps(["User.Read"]),
            }

    # Fallback: local MSAL public client flow.
    client_id = os.getenv("MSAL_CLIENT_ID")
    tenant_id = os.getenv("MSAL_TENANT_ID", "organizations")
    scope_csv = os.getenv("MSAL_SCOPES", "User.Read")
    scopes = [s.strip() for s in scope_csv.split(",") if s.strip()]

    if not client_id:
        raise ProtectedFileAccessError(
            "Protected file access requires a delegated identity token. "
            "Sign in via `az login` or configure MSAL_CLIENT_ID for interactive login."
        )

    base_cache = Path(os.getenv("MSAL_CACHE_DIR", tempfile.gettempdir()))
    cache_path = base_cache / "word_to_md_msal_cache.json"
    token_cache = _build_token_cache(cache_path)

    authority = f"https://login.microsoftonline.com/{tenant_id}"
    msal = _import_msal()
    app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=token_cache,
    )

    result: Optional[Dict] = None
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(scopes=scopes, account=accounts[0])

    if not result:
        # Interactive login ensures we bind to the current executing user's identity.
        result = app.acquire_token_interactive(scopes=scopes, prompt="select_account")

    _save_token_cache(token_cache, cache_path)

    if not result or "access_token" not in result:
        detail = ""
        if result:
            detail = result.get("error_description") or result.get("error") or ""
        raise ProtectedFileAccessError(f"MSAL sign-in failed. {detail}".strip())

    headers = {"Authorization": f"Bearer {result['access_token']}"}
    me = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=20)
    if me.status_code != 200:
        raise ProtectedFileAccessError(
            "Could not validate signed-in identity with Microsoft Graph /me. "
            f"Status: {me.status_code}."
        )

    profile = me.json()
    identity = {
        "display_name": profile.get("displayName", ""),
        "upn": profile.get("userPrincipalName", ""),
        "oid": profile.get("id", ""),
        "tenant": tenant_id,
        "scopes": json.dumps(scopes),
    }
    return identity


def export_accessible_copy_via_word(file_path: Path) -> Path:
    """Open a protected doc with Word under current user context and re-save as docx."""
    if win32com is None:
        raise ProtectedFileAccessError(
            "pywin32 is required to process protected files on Windows. Install pywin32."
        )

    output_path = Path(tempfile.gettempdir()) / f"{file_path.stem}-accessible-{uuid.uuid4().hex}.docx"

    word = None
    doc = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0

        doc = word.Documents.Open(
            str(file_path),
            ReadOnly=True,
            AddToRecentFiles=False,
        )

        # 16 = wdFormatXMLDocument (.docx)
        doc.SaveAs2(str(output_path), FileFormat=16)
    except Exception as exc:
        raise ProtectedFileAccessError(
            "Protected file could not be opened with current user permissions. "
            f"{exc}"
        ) from exc
    finally:
        if doc is not None:
            doc.Close(False)
        if word is not None:
            word.Quit()

    if not output_path.exists() or not zipfile.is_zipfile(output_path):
        raise ProtectedFileAccessError(
            "Could not create an accessible .docx copy from the protected file."
        )

    return output_path


def ensure_accessible_docx(file_path: Path) -> Tuple[Path, Dict[str, str], bool]:
    """
    Returns:
      - Path to input or generated accessible copy
      - Current identity dictionary (only populated for protected files)
      - Whether the returned path is a temporary generated copy
    """
    if not is_file_dlp_protected(file_path):
        return file_path, {}, False

    identity = get_current_identity()
    accessible_copy = export_accessible_copy_via_word(file_path)
    return accessible_copy, identity, True
