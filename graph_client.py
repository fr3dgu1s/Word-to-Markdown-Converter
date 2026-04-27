"""
Microsoft Graph API operations for OneDrive and SharePoint.

All functions take an explicit `token` string (Bearer) so they are stateless
and can be called from any thread without sharing auth state.
"""

import base64
import logging
import re
import time
import urllib.parse
from typing import Optional
from urllib.parse import urlparse

import requests

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
logger = logging.getLogger("wordtomd.graph")


# ---------------------------------------------------------------------------
# HTTP primitives
# ---------------------------------------------------------------------------


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _get(url: str, token: str, **kwargs) -> dict:
    logger.debug(f"[GRAPH] GET {url}")
    t0 = time.perf_counter()
    r = requests.get(url, headers=_headers(token), timeout=60, **kwargs)
    elapsed = int((time.perf_counter() - t0) * 1000)
    logger.debug(f"[GRAPH] response {r.status_code} ({elapsed}ms)")
    _raise_for_status(r)
    return r.json()


def _put(url: str, token: str, data: bytes, content_type: str = "application/octet-stream") -> dict:
    logger.debug(f"[GRAPH] PUT {url}")
    t0 = time.perf_counter()
    headers = _headers(token)
    headers["Content-Type"] = content_type
    r = requests.put(url, headers=headers, data=data, timeout=120)
    elapsed = int((time.perf_counter() - t0) * 1000)
    logger.debug(f"[GRAPH] response {r.status_code} ({elapsed}ms)")
    _raise_for_status(r)
    return r.json()


def _post(url: str, token: str, json_body: dict) -> dict:
    logger.debug(f"[GRAPH] POST {url}")
    t0 = time.perf_counter()
    headers = _headers(token)
    headers["Content-Type"] = "application/json"
    r = requests.post(url, headers=headers, json=json_body, timeout=60)
    elapsed = int((time.perf_counter() - t0) * 1000)
    logger.debug(f"[GRAPH] response {r.status_code} ({elapsed}ms)")
    _raise_for_status(r)
    return r.json()


def _raise_for_status(r: requests.Response) -> None:
    if r.status_code == 401:
        logger.error(f"[GRAPH] failed 401 | {r.url}")
        raise PermissionError("Graph API returned 401 Unauthorized. Token may be expired — sign in again.")
    if r.status_code == 403:
        logger.error(f"[GRAPH] failed 403 | {r.url}")
        raise PermissionError(
            f"Graph API returned 403 Forbidden for {r.url}. "
            "Your account may lack the required permissions."
        )
    if r.status_code == 404:
        logger.error(f"[GRAPH] failed 404 | {r.url}")
        raise FileNotFoundError(f"Graph API returned 404 Not Found for {r.url}.")
    if not r.ok:
        logger.error(f"[GRAPH] failed {r.status_code} | {r.url} | {r.text[:300]}")
    r.raise_for_status()


# ---------------------------------------------------------------------------
# URL resolver
# ---------------------------------------------------------------------------

# Matches:
#   https://<tenant>.sharepoint.com/sites/<site>/...
#   https://<tenant>.sharepoint.com/personal/<upn>/...
#   https://onedrive.live.com/...     (consumer OneDrive — not supported)
#   https://1drv.ms/...               (short link — not supported)
_SP_SITE_RE = re.compile(
    r"https://(?P<host>[^/]+\.sharepoint\.com)"
    r"(?P<site_part>/sites/[^/?#]+|/personal/[^/?#]+)"
    r"(?P<rest>.*)",
    re.IGNORECASE,
)

_ONEDRIVE_ME_RE = re.compile(
    r"https://(?P<host>[^/]+\.sharepoint\.com)"
    r"(?P<rest>/_layouts/.*|/[^/]+/Documents/.*)?",
    re.IGNORECASE,
)


def _sp_site_root(hostname: str, site_path: str) -> str:
    """Build Graph site URL: /sites/{hostname}:{site_path}"""
    return f"{GRAPH_BASE}/sites/{hostname}:{site_path}"


def _get_drive_for_site(site_id: str, token: str) -> str:
    data = _get(f"{GRAPH_BASE}/sites/{site_id}/drive", token)
    return data["id"]


def _item_by_path(drive_id: str, server_relative_path: str, token: str) -> dict:
    """Resolve a server-relative path inside a drive to an item object."""
    encoded = urllib.parse.quote(server_relative_path.lstrip("/"), safe="/")
    url = f"{GRAPH_BASE}/drives/{drive_id}/root:/{encoded}"
    return _get(url, token)


def _share_id_from_url(url: str) -> str:
    encoded = base64.urlsafe_b64encode(url.encode("utf-8")).decode("ascii")
    encoded = encoded.rstrip("=")
    return f"u!{encoded}"


def _is_share_link(parsed) -> bool:
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    return host.endswith(".sharepoint.com") and path.startswith("/:") or host == "onedrive.cloud.microsoft"


def _resolve_share_url(url: str, token: str) -> tuple[str, str]:
    share_id = _share_id_from_url(url)
    item = _get(
        f"{GRAPH_BASE}/shares/{share_id}/driveItem",
        token,
        params={"$select": "id,name,parentReference,remoteItem"},
    )

    item_id = item.get("id")
    parent_reference = item.get("parentReference") or {}
    drive_id = parent_reference.get("driveId")

    remote_item = item.get("remoteItem") or {}
    if not item_id and remote_item:
        item_id = remote_item.get("id")
        parent_reference = remote_item.get("parentReference") or parent_reference
        drive_id = parent_reference.get("driveId") or drive_id

    if not item_id or not drive_id:
        raise ValueError(f"Could not resolve shared OneDrive/SharePoint URL: {url!r}")

    return drive_id, item_id


def resolve_url(url: str, token: str) -> tuple[str, str]:
    """
    Resolve a SharePoint or OneDrive URL to (drive_id, item_id).

    Supports:
      - SharePoint document library folder/file URLs
      - OneDrive for Business URLs (/personal/...)
      - Sharing links that redirect to the above

    Raises ValueError for unsupported URL schemes.
    Raises FileNotFoundError if the item does not exist.
    """
    parsed = urlparse(url)
    hostname = parsed.netloc.lower()

    if _is_share_link(parsed):
        return _resolve_share_url(url, token)

    if not hostname.endswith(".sharepoint.com"):
        raise ValueError(
            f"Unsupported URL: {url!r}. Supported URLs include *.sharepoint.com and OneDrive share links."
        )

    m = _SP_SITE_RE.match(url)
    if not m:
        raise ValueError(f"Cannot parse SharePoint URL: {url!r}")

    host = m.group("host")
    site_part = m.group("site_part")   # e.g. /sites/MySite
    rest = m.group("rest") or ""       # everything after the site slug

    # Resolve the site
    site_data = _get(_sp_site_root(host, site_part), token)
    site_id = site_data["id"]

    # Resolve the default drive for that site
    drive_data = _get(f"{GRAPH_BASE}/sites/{site_id}/drive", token)
    drive_id = drive_data["id"]

    # If there's a path component after the site slug try to resolve it.
    # Strip SharePoint navigation suffixes like /Forms/AllItems.aspx, query strings, etc.
    item_path = _strip_sp_navigation(rest)

    if not item_path or item_path == "/":
        # Root of the drive
        root = _get(f"{GRAPH_BASE}/drives/{drive_id}/root", token)
        return drive_id, root["id"]

    item = _item_by_path(drive_id, item_path, token)
    return drive_id, item["id"]


def _strip_sp_navigation(rest: str) -> str:
    """Remove SharePoint navigation suffixes that are not part of the actual path."""
    # Remove query strings and fragments
    rest = rest.split("?")[0].split("#")[0]
    # Remove /Forms/AllItems.aspx and similar tails
    rest = re.sub(r"/Forms/[^/]*$", "", rest, flags=re.IGNORECASE)
    # Collapse // etc.
    rest = re.sub(r"/+", "/", rest)
    return rest.rstrip("/")


# ---------------------------------------------------------------------------
# Folder listing
# ---------------------------------------------------------------------------


def list_folder_docx(drive_id: str, folder_item_id: str, token: str) -> list[dict]:
    """
    Return a list of .docx items directly inside the given folder.

    Each entry: {"name": str, "drive_id": str, "item_id": str, "size": int}
    """
    url = f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_item_id}/children"
    params: dict = {"$select": "id,name,size,file", "$top": "1000"}
    results = []

    while url:
        data = _get(url, token, params=params)
        params = {}  # only on first request
        for item in data.get("value", []):
            if "file" not in item:
                continue
            if not item.get("name", "").lower().endswith(".docx"):
                continue
            results.append({
                "name": item["name"],
                "drive_id": drive_id,
                "item_id": item["id"],
                "size": item.get("size", 0),
            })
        url = data.get("@odata.nextLink")  # type: ignore[assignment]

    return results


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download_file_bytes(drive_id: str, item_id: str, token: str) -> bytes:
    """Download the binary content of a drive item."""
    # Get the download URL first (avoids a redirect dance with the auth header)
    meta = _get(f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}", token,
                params={"$select": "@microsoft.graph.downloadUrl,name"})
    download_url = meta.get("@microsoft.graph.downloadUrl")
    if not download_url:
        raise RuntimeError(f"No downloadUrl for item {item_id} — item may be a folder or have no content.")

    r = requests.get(download_url, timeout=120)
    r.raise_for_status()
    return r.content


# ---------------------------------------------------------------------------
# Upload
# ---------------------------------------------------------------------------


def upload_markdown(
    drive_id: str,
    folder_item_id: str,
    filename: str,
    content: str,
    token: str,
) -> str:
    """
    Upload a Markdown string as a file into the given folder via PUT (simple upload).

    Uses the resumable upload session for files > 4 MB, simple PUT otherwise.
    Returns the webUrl of the uploaded item.
    """
    encoded_name = urllib.parse.quote(filename, safe="")
    data = content.encode("utf-8")

    if len(data) > 4 * 1024 * 1024:
        return _upload_large(drive_id, folder_item_id, filename, data, token)

    url = f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_item_id}:/{encoded_name}:/content"
    result = _put(url, token, data, content_type="text/markdown; charset=utf-8")
    return result.get("webUrl", "")


def _upload_large(drive_id: str, folder_item_id: str, filename: str, data: bytes, token: str) -> str:
    """Resumable upload session for files > 4 MB."""
    session_url = (
        f"{GRAPH_BASE}/drives/{drive_id}/items/{folder_item_id}:/{urllib.parse.quote(filename, safe='')}:/createUploadSession"
    )
    session = _post(session_url, token, {
        "item": {
            "@microsoft.graph.conflictBehavior": "replace",
            "name": filename,
        }
    })
    upload_url = session["uploadUrl"]
    chunk_size = 10 * 1024 * 1024  # 10 MB
    total = len(data)
    offset = 0
    result: dict = {}
    while offset < total:
        end = min(offset + chunk_size, total)
        chunk = data[offset:end]
        headers = {
            "Content-Length": str(len(chunk)),
            "Content-Range": f"bytes {offset}-{end - 1}/{total}",
            "Content-Type": "text/markdown; charset=utf-8",
        }
        r = requests.put(upload_url, headers=headers, data=chunk, timeout=120)
        if r.status_code in (200, 201):
            result = r.json()
        elif r.status_code == 202:
            pass  # accepted, continue
        else:
            r.raise_for_status()
        offset = end
    return result.get("webUrl", "")


# ---------------------------------------------------------------------------
# Output folder resolver
# ---------------------------------------------------------------------------


def resolve_output_folder(sharepoint_folder_url: str, token: str) -> tuple[str, str]:
    """
    Resolve a SharePoint folder URL to (drive_id, folder_item_id).

    If the folder does not exist (404), attempt to create it as a child of
    the parent folder that does exist — up to one level deep.

    Returns (drive_id, folder_item_id).
    """
    try:
        return resolve_url(sharepoint_folder_url, token)
    except FileNotFoundError:
        pass

    # Try to create the folder: parse out the last path segment as the new name.
    parsed = urlparse(sharepoint_folder_url)
    path_part = _strip_sp_navigation(parsed.path)
    parent_path, _, new_name = path_part.rstrip("/").rpartition("/")
    if not new_name:
        raise ValueError(f"Cannot determine folder name from URL: {sharepoint_folder_url!r}")

    # Rebuild the parent URL
    parent_url = f"{parsed.scheme}://{parsed.netloc}{parent_path}"
    parent_drive_id, parent_item_id = resolve_url(parent_url, token)

    create_url = f"{GRAPH_BASE}/drives/{parent_drive_id}/items/{parent_item_id}/children"
    headers = _headers(token)
    headers["Content-Type"] = "application/json"
    r = requests.post(
        create_url,
        headers=headers,
        json={
            "name": new_name,
            "folder": {},
            "@microsoft.graph.conflictBehavior": "fail",
        },
        timeout=30,
    )
    if r.status_code == 409:
        # Race: someone else created it; resolve again.
        return resolve_url(sharepoint_folder_url, token)
    _raise_for_status(r)
    item = r.json()
    return parent_drive_id, item["id"]
