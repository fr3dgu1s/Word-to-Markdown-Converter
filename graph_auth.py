"""
Microsoft Graph authentication via the Azure CLI.

Delegates token acquisition to `az account get-access-token` so no app
registration, client ID, or MSAL token cache is needed.  The CLI handles
login, refresh, and multi-subscription selection automatically.

Prerequisites:
  az login           — sign in once
  az account set -s  — select a subscription when you have multiple
"""

import json
import subprocess
from typing import Optional

GRAPH_RESOURCE = "https://graph.microsoft.com"


def _run_az(*args: str, timeout: int = 30) -> dict:
    """Run an `az` subcommand and return the parsed JSON output."""
    try:
        result = subprocess.run(
            ["az", *args, "--output", "json"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "Azure CLI ('az') not found. "
            "Install it from https://aka.ms/installazurecli and run 'az login'."
        )
    if result.returncode != 0:
        raise RuntimeError(
            "Azure CLI sign-in required. "
            f"Please run 'az login' in your terminal and try again.\n"
            f"Detail: {result.stderr.strip()}"
        )
    return json.loads(result.stdout)


class GraphAuthClient:
    def get_token(self) -> str:
        """Return a valid Graph access token from the active CLI session."""
        data = _run_az("account", "get-access-token", "--resource", GRAPH_RESOURCE)
        return data["accessToken"]

    def get_account(self) -> Optional[str]:
        try:
            data = _run_az("account", "show")
            return data.get("user", {}).get("name")
        except Exception:
            return None

    def is_authenticated(self) -> bool:
        try:
            self.get_token()
            return True
        except Exception:
            return False


def get_auth_client() -> GraphAuthClient:
    """Return a GraphAuthClient. Stateless — no singleton needed."""
    return GraphAuthClient()
