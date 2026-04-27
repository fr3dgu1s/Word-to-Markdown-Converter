"""
Microsoft Graph authentication via the Azure CLI.

Calls `az account get-access-token` via subprocess.  The CLI owns all token
acquisition and refresh — no MSAL, no client ID, no cache file needed here.

Prerequisites:
  az login           — sign in once
  az account set -s  — select the right subscription when you have multiple
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
from typing import Optional

logger = logging.getLogger("wordtomd.auth")


class GraphAuthClient:

    @staticmethod
    def _get_az_cmd() -> str:
        candidates = [
            shutil.which("az"),
            shutil.which("az.cmd"),
            r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
            r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                return c
        raise RuntimeError(
            "Azure CLI not found. Install from https://aka.ms/installazurecli"
        )

    @staticmethod
    def _extended_env() -> dict:
        return {
            **os.environ,
            "PATH": os.environ.get("PATH", "")
            + r";C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin"
            + r";C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin",
        }

    async def get_token_async(self) -> str:
        cmd = self._get_az_cmd()
        env = self._extended_env()
        proc = await asyncio.create_subprocess_exec(
            cmd, "account", "get-access-token",
            "--resource", "https://graph.microsoft.com",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except Exception:
                pass
            raise RuntimeError(
                "az account get-access-token timed out after 30s. "
                "Try running 'az login' again in your terminal."
            )

        if proc.returncode != 0:
            raise RuntimeError(
                f"Token acquisition failed (returncode {proc.returncode}): "
                f"{stderr.decode(errors='replace').strip()}"
            )

        data = json.loads(stdout.decode(errors="replace"))
        return data["accessToken"]

    async def get_account_async(self) -> Optional[str]:
        try:
            cmd = self._get_az_cmd()
        except Exception:
            return None
        env = self._extended_env()
        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, "account", "show",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode != 0:
                return None
            data = json.loads(stdout.decode(errors="replace"))
            return data.get("user", {}).get("name")
        except Exception:
            return None

    async def is_authenticated_async(self) -> bool:
        try:
            await self.get_token_async()
            return True
        except Exception:
            return False

    def get_token(self) -> str:
        logger.debug("subprocess: az account get-access-token --resource https://graph.microsoft.com")
        result = subprocess.run(
            ["az", "account", "get-access-token",
             "--resource", "https://graph.microsoft.com"],
            capture_output=True,
            text=True,
        )
        logger.debug(f"returncode: {result.returncode}")
        if result.stderr:
            logger.warning(f"stderr: {result.stderr.strip()}")
        if result.returncode != 0:
            raise RuntimeError(
                "Azure CLI token acquisition failed. "
                f"Please run 'az login' and try again.\n{result.stderr.strip()}"
            )
        data = json.loads(result.stdout)
        return data["accessToken"]

    def get_account(self) -> Optional[str]:
        logger.debug("subprocess: az account show")
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True,
            text=True,
        )
        logger.debug(f"returncode: {result.returncode}")
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        return data.get("user", {}).get("name")

    def is_authenticated(self) -> bool:
        try:
            self.get_token()
            return True
        except Exception:
            return False


def get_auth_client() -> GraphAuthClient:
    return GraphAuthClient()
