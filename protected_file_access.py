import json
import os
import shutil
import subprocess
import tempfile
import time
import uuid
import zipfile
import base64
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

try:
    import win32com.client  # type: ignore
except ImportError:
    win32com = None


class ProtectedFileAccessError(Exception):
    pass


_IDENTITY_CACHE_SECONDS = 600
_identity_cache: Optional[Dict[str, str]] = None
_identity_cache_ts = 0.0


def _az_command_candidates() -> list[list[str]]:
    candidates: list[list[str]] = []

    # 1) PATH-based lookup.
    for exe_name in ("az", "az.cmd"):
        resolved = shutil.which(exe_name)
        if resolved:
            candidates.append([resolved])

    # 2) Common Windows install paths.
    common_paths = [
        r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
    ]
    for full_path in common_paths:
        if os.path.exists(full_path):
            candidates.append([full_path])

    # 3) Last chance: rely on shell resolution.
    candidates.append(["az"])
    candidates.append(["az.cmd"])
    return candidates


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
    commands_to_try = [
        [
            "account",
            "get-access-token",
            "--resource-type",
            "ms-graph",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        [
            "account",
            "get-access-token",
            "--resource",
            "https://graph.microsoft.com/",
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
    ]

    for az_exe in _az_command_candidates():
        for args in commands_to_try:
            try:
                result = subprocess.run(
                    az_exe + args,
                    capture_output=True,
                    text=True,
                    timeout=25,
                    check=False,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue

            if result.returncode != 0:
                continue

            token = (result.stdout or "").strip()
            if token:
                return token

    return None


def _extract_identity_from_jwt(token: str) -> Optional[Dict[str, str]]:
    """Best-effort extraction of basic identity claims from a JWT access token."""
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None

        payload_b64 = parts[1]
        padding = "=" * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64 + padding).decode("utf-8")
        claims = json.loads(payload_json)

        upn = claims.get("upn") or claims.get("unique_name") or ""
        display_name = claims.get("name") or upn
        oid = claims.get("oid") or ""
        tid = claims.get("tid") or "azure-cli"
        scopes = claims.get("scp") or "User.Read"
        scopes_list = scopes.split() if isinstance(scopes, str) else ["User.Read"]

        return {
            "display_name": display_name,
            "upn": upn,
            "oid": oid,
            "tenant": tid,
            "scopes": json.dumps(scopes_list),
        }
    except Exception:
        return None


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
    global _identity_cache, _identity_cache_ts

    # Fast in-memory cache to avoid repeated auth checks per protected file in batch.
    now = time.time()
    if _identity_cache and (now - _identity_cache_ts) < _IDENTITY_CACHE_SECONDS:
        return _identity_cache

    # First, try Azure CLI token from current signed-in identity.
    cli_token = _get_graph_token_from_azure_cli()
    if cli_token:
        identity = _extract_identity_from_jwt(cli_token)
        if identity:
            _identity_cache = identity
            _identity_cache_ts = now
            return identity

        # Fallback to Graph only if token parsing unexpectedly fails.
        requests = _import_requests()
        headers = {"Authorization": f"Bearer {cli_token}"}
        me = requests.get("https://graph.microsoft.com/v1.0/me", headers=headers, timeout=20)
        if me.status_code == 200:
            profile = me.json()
            identity = {
                "display_name": profile.get("displayName", ""),
                "upn": profile.get("userPrincipalName", ""),
                "oid": profile.get("id", ""),
                "tenant": "azure-cli",
                "scopes": json.dumps(["User.Read"]),
            }
            _identity_cache = identity
            _identity_cache_ts = now
            return identity

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
    requests = _import_requests()
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
    _identity_cache = identity
    _identity_cache_ts = now
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


def check_word_automation() -> Dict[str, str | bool]:
    """Verify that local Word automation is available for protected file export."""
    if win32com is None:
        return {
            "ok": False,
            "message": "pywin32 is not installed; Word automation unavailable.",
        }

    word = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        return {
            "ok": True,
            "message": "Microsoft Word automation is available.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Word automation failed: {exc}",
        }
    finally:
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass


def run_protected_access_diagnostics() -> Dict[str, Any]:
    """Run prerequisites checks used by the UI diagnostics button."""
    checks: Dict[str, Dict[str, Any]] = {}

    cli_token = _get_graph_token_from_azure_cli()
    checks["azure_cli_token"] = {
        "ok": bool(cli_token),
        "message": (
            "Azure CLI delegated Graph token acquired."
            if cli_token
            else "No delegated Graph token from Azure CLI."
        ),
    }

    try:
        identity = get_current_identity()
        checks["identity"] = {
            "ok": True,
            "message": f"Identity validated: {identity.get('upn', '')}",
            "data": identity,
        }
    except Exception as exc:
        checks["identity"] = {
            "ok": False,
            "message": str(exc),
        }

    word_status = check_word_automation()
    checks["word_automation"] = {
        "ok": bool(word_status.get("ok")),
        "message": str(word_status.get("message", "")),
    }

    overall_ok = bool(checks["identity"]["ok"] and checks["word_automation"]["ok"])
    return {
        "ok": overall_ok,
        "checks": checks,
    }


def test_protected_file_access(file_path: Path) -> Dict[str, Any]:
    """Test whether a specific file can be opened/exported for conversion."""
    generated_copy: Optional[Path] = None
    try:
        protected = is_file_dlp_protected(file_path)
        if not protected:
            return {
                "ok": True,
                "protected": False,
                "message": "File is not DLP-protected; protected-file flow is not required.",
            }

        accessible_path, identity, was_generated = ensure_accessible_docx(file_path)
        if was_generated:
            generated_copy = accessible_path

        return {
            "ok": True,
            "protected": True,
            "message": "Protected file access succeeded for current identity.",
            "identity": identity,
        }
    except Exception as exc:
        return {
            "ok": False,
            "protected": True,
            "message": str(exc),
        }
    finally:
        if generated_copy and generated_copy.exists():
            generated_copy.unlink(missing_ok=True)
