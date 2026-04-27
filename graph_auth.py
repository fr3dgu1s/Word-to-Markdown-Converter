"""
Microsoft Graph authentication via the Azure CLI.

Calls `az account get-access-token` via subprocess.  The CLI owns all token
acquisition and refresh — no MSAL, no client ID, no cache file needed here.

Prerequisites:
  az login           — sign in once
  az account set -s  — select the right subscription when you have multiple
"""

import json
import subprocess
from typing import Optional


class GraphAuthClient:

    def get_token(self) -> str:
        result = subprocess.run(
            ["az", "account", "get-access-token",
             "--resource", "https://graph.microsoft.com"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Azure CLI token acquisition failed. "
                f"Please run 'az login' and try again.\n{result.stderr.strip()}"
            )
        data = json.loads(result.stdout)
        return data["accessToken"]

    def get_account(self) -> Optional[str]:
        result = subprocess.run(
            ["az", "account", "show"],
            capture_output=True,
            text=True,
        )
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
