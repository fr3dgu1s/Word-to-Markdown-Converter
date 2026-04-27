"""
Python orchestrator around the C# MipHelper.exe binary.

Three subcommands are expected on the helper binary:

    MipHelper.exe inspect   --input <path>  --metadata <out.json>
    MipHelper.exe unprotect --input <path>  --output <working.docx> --metadata <metadata.json> --user <upn>
    MipHelper.exe protect   --input <path>  --output <final.docx>   --metadata <metadata.json> --user <upn>

Exit codes:
    0   success
    10  file is not protected (inspect only)
    20  access denied by Purview policy
    30  protection could not be reapplied
    99  generic helper failure (see stderr)

Configuration (env vars):
    MIP_HELPER_PATH   Absolute path to MipHelper.exe (preferred)
    MIP_HELPER_DIR    Folder containing MipHelper.exe (alternative)
    MIP_USER_UPN      The signed-in user's UPN, used by the helper for delegated MIP actions

This module is intentionally pure-Python and contains NO MIP SDK calls — all
MIP work happens inside the C# helper, which owns app onboarding, token
acquisition, and label re-application logic.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from paths import MIP_HELPER_PATH, MIP_HELPER_ROOT, TEMP_PROTECTED


logger = logging.getLogger("wordtomd.mip")


class MipAccessDeniedError(Exception):
    """Raised when MIP/Purview denies decrypt or label re-apply for the user."""


class MipReapplyFailedError(Exception):
    """Raised when reapplying the original sensitivity label/protection fails."""


class MipHelperError(Exception):
    """Raised for any other helper failure (missing binary, generic exit, etc.)."""


@dataclass
class MipMetadata:
    metadata_path: Path
    label_id: Optional[str]
    label_name: Optional[str]
    is_protected: bool


def _resolve_helper_path() -> str:
    """Locate MipHelper.exe.

    Resolution order:
      1. MIP_HELPER_PATH (env / .env, default ``C:/temp/W2MD/MipHelper/MipHelper.exe``).
      2. ``MIP_HELPER_ROOT/MipHelper.exe`` (default ``C:/temp/W2MD/MipHelper``).
      3. Repo-relative published helper:
         ``MipHelper/bin/Release/net8.0/win-x64/publish/MipHelper.exe`` (or non-RID variant).
      4. If only the repo-relative helper exists, copy it to MIP_HELPER_ROOT so
         subsequent calls find it via step 1/2 — keeps everything portable.
    """
    if MIP_HELPER_PATH.exists():
        return str(MIP_HELPER_PATH)

    central = MIP_HELPER_ROOT / "MipHelper.exe"
    if central.exists():
        return str(central)

    repo_root = Path(__file__).resolve().parent
    repo_candidates = [
        repo_root / "MipHelper" / "bin" / "Release" / "net8.0" / "win-x64" / "publish" / "MipHelper.exe",
        repo_root / "MipHelper" / "bin" / "Release" / "net8.0" / "publish" / "MipHelper.exe",
        repo_root / "MipHelper" / "bin" / "Release" / "net8.0" / "MipHelper.exe",
        repo_root / "MipHelper" / "bin" / "Debug" / "net8.0" / "MipHelper.exe",
    ]
    for candidate in repo_candidates:
        if candidate.exists():
            try:
                MIP_HELPER_ROOT.mkdir(parents=True, exist_ok=True)
                shutil.copy2(candidate, central)
                logger.info(f"[MIP] copied helper to {central}")
                return str(central)
            except Exception as exc:
                logger.warning(f"[MIP] could not copy helper to {central}: {exc}")
                return str(candidate)

    raise MipHelperError(
        "MipHelper.exe was not found. Run scripts/setup-windows.ps1 or "
        "publish the helper and copy it to "
        f"{(MIP_HELPER_ROOT / 'MipHelper.exe').as_posix()}."
    )


def _run_helper(args: list[str], *, timeout: int = 120) -> tuple[int, str, str]:
    helper = _resolve_helper_path()
    cmd = [helper, *args]
    logger.info(f"[MIP] exec | {' '.join(args)}")
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    logger.debug(f"[MIP] returncode={proc.returncode}")
    if proc.stdout:
        logger.debug(f"[MIP] stdout: {proc.stdout.strip()}")
    if proc.stderr:
        logger.debug(f"[MIP] stderr: {proc.stderr.strip()}")
    return proc.returncode, proc.stdout, proc.stderr


def inspect_file(input_path: str | Path) -> MipMetadata:
    """Run MipHelper.exe inspect and return parsed metadata.

    The helper writes the metadata.json with at least the following shape:
        { "is_protected": bool, "label_id": str|null, "label_name": str|null,
          "tenant_id": str|null, "owner": str|null, "rights": [..] }
    """
    src = Path(input_path)
    if not src.exists():
        raise MipHelperError(f"Input file not found: {src}")

    metadata_path = TEMP_PROTECTED / f"mip-meta-{uuid.uuid4().hex}.json"
    rc, _stdout, stderr = _run_helper(
        ["inspect", "--input", str(src), "--metadata", str(metadata_path)]
    )

    if rc not in (0, 10):
        raise MipHelperError(f"MipHelper inspect failed (rc={rc}): {stderr.strip()}")

    if not metadata_path.exists():
        raise MipHelperError("MipHelper inspect produced no metadata file.")

    try:
        with metadata_path.open("r", encoding="utf-8") as fp:
            data = json.load(fp)
    except Exception as exc:
        raise MipHelperError(f"Could not parse MIP metadata JSON: {exc}") from exc

    return MipMetadata(
        metadata_path=metadata_path,
        label_id=data.get("label_id"),
        label_name=data.get("label_name"),
        is_protected=bool(data.get("is_protected", rc == 0)),
    )


def unprotect_file(
    input_path: str | Path,
    metadata_path: str | Path,
    user_upn: Optional[str] = None,
) -> Path:
    """Decrypt a protected file via MipHelper.exe and return path to working copy.

    Raises:
        MipAccessDeniedError when Purview denies access.
        MipHelperError for any other helper failure.
    """
    src = Path(input_path)
    meta = Path(metadata_path)
    upn = user_upn or os.environ.get("MIP_USER_UPN", "")

    work_dir = Path(tempfile.mkdtemp(prefix="mip-work-", dir=str(TEMP_PROTECTED)))
    output_path = work_dir / f"{src.stem}-working.docx"

    args = [
        "unprotect",
        "--input", str(src),
        "--output", str(output_path),
        "--metadata", str(meta),
    ]
    if upn:
        args += ["--user", upn]

    rc, _stdout, stderr = _run_helper(args, timeout=180)

    if rc == 20:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipAccessDeniedError(
            "Microsoft Purview denied decrypt for the current user. "
            "You do not have rights to view or extract this file."
        )

    if rc != 0 or not output_path.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipHelperError(f"MipHelper unprotect failed (rc={rc}): {stderr.strip()}")

    return output_path


def fetch_and_unprotect_url(
    source_url: str,
    user_upn: Optional[str] = None,
    *,
    timeout: int = 110,
) -> Path:
    """Ask the MIP helper to fetch a protected SharePoint/OneDrive URL with the
    current user's Microsoft 365 credentials and produce a decrypted working
    copy locally.

    Used as a fallback when Microsoft Graph returns 403 / access denied on a
    file that the signed-in user can still open via Word + MIP.

    Returns:
        Path to the decrypted working .docx in a private mip-fetch-* tempdir.

    Raises:
        MipAccessDeniedError when MIP/Purview denies access to the user.
        MipHelperError for any other helper failure.
    """
    upn = user_upn or os.environ.get("MIP_USER_UPN", "")

    work_dir = Path(tempfile.mkdtemp(prefix="mip-fetch-", dir=str(TEMP_PROTECTED)))
    output_path = work_dir / "fetched-working.docx"

    args = [
        "fetch-unprotect",
        "--url", source_url,
        "--output", str(output_path),
    ]
    if upn:
        args += ["--user", upn]

    rc, _stdout, stderr = _run_helper(args, timeout=timeout)

    if rc == 20:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipAccessDeniedError(
            "Microsoft Purview denied access for the current user. "
            "You do not have rights to view, edit, or export this file."
        )

    if rc != 0 or not output_path.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipHelperError(
            f"MipHelper fetch-unprotect failed (rc={rc}): {stderr.strip() or '<no stderr>'}"
        )

    return output_path


def reapply_protection(
    input_path: str | Path,
    metadata_path: str | Path,
    user_upn: Optional[str] = None,
) -> Path:
    """Reapply the originally captured sensitivity label / protection.

    Raises:
        MipAccessDeniedError when the user lacks rights to reapply.
        MipReapplyFailedError when the helper cannot reapply for any reason.
        MipHelperError for any other helper failure.
    """
    src = Path(input_path)
    meta = Path(metadata_path)
    upn = user_upn or os.environ.get("MIP_USER_UPN", "")

    work_dir = Path(tempfile.mkdtemp(prefix="mip-final-", dir=str(TEMP_PROTECTED)))
    output_path = work_dir / f"{src.stem}-protected.docx"

    args = [
        "protect",
        "--input", str(src),
        "--output", str(output_path),
        "--metadata", str(meta),
    ]
    if upn:
        args += ["--user", upn]

    rc, _stdout, stderr = _run_helper(args, timeout=180)

    if rc == 20:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipAccessDeniedError(
            "Microsoft Purview denied label re-application for the current user."
        )

    if rc == 30:
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipReapplyFailedError(
            "MIP could not reapply the original sensitivity label / protection."
        )

    if rc != 0 or not output_path.exists():
        shutil.rmtree(work_dir, ignore_errors=True)
        raise MipHelperError(f"MipHelper protect failed (rc={rc}): {stderr.strip()}")

    return output_path


def cleanup_paths(*paths: str | Path | None) -> None:
    """Best-effort delete of decrypted temp files and their parent work dirs."""
    for p in paths:
        if not p:
            continue
        path = Path(p)
        try:
            if path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)

            parent = path.parent
            if parent.exists() and parent.name.startswith(("mip-work-", "mip-final-", "mip-fetch-", "mip-src-")):
                shutil.rmtree(parent, ignore_errors=True)
        except Exception as exc:
            logger.warning(f"[MIP] cleanup failed for {path}: {exc}")
