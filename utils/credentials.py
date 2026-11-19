"""
PRIVACY68 Credential Vault.
Manages secure Windows Credential Manager tokens, personal access tokens (PATs),
and fallback environment authentication for developer tools.
"""

import logging
import os
from typing import Any, Dict, Optional
import requests

import config

logger = logging.getLogger("PRIVACY68.Credentials")

_CREDENTIAL_TARGET = "PRIVACY68/GitHubToken"


def _credential_manager():
    try:
        import win32cred
        return win32cred
    except ImportError as exc:
        raise RuntimeError("Windows Credential Manager is unavailable; install pywin32.") from exc


def get_github_token() -> Optional[str]:
    """Retrieves GitHub PAT from Windows Credential Manager, config, or environment."""
    # 1. Primary: Windows Credential Manager
    try:
        win32cred = _credential_manager()
        credential = win32cred.CredRead(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC)
        secret = credential.get("CredentialBlob")
        if isinstance(secret, str):
            return secret
        if isinstance(secret, (bytes, bytearray)):
            for enc in ("utf-16-le", "utf-8", "latin1"):
                try:
                    decoded = secret.decode(enc).strip()
                    if decoded:
                        return decoded
                except (UnicodeDecodeError, ValueError):
                    continue
            return secret.decode("utf-8", errors="ignore").strip()
    except Exception as exc:
        if getattr(exc, "winerror", None) != 1168:  # 1168 = ERROR_NOT_FOUND
            logger.debug("Windows Credential Manager read failed: %s", exc)

    # 2. Secondary fallback: .env / runtime config
    env_token = getattr(config, "GITHUB_TOKEN", "") or os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
    return env_token.strip() if env_token else None


def set_github_token(token: str, user_login: str = "User") -> bool:
    """Stores GitHub token in Windows Credential Manager and .env."""
    cleaned = token.strip()
    if not cleaned:
        return False

    try:
        win32cred = _credential_manager()
        for persist in (
            getattr(win32cred, "CRED_PERSIST_LOCAL_MACHINE", 2),
            getattr(win32cred, "CRED_PERSIST_ENTERPRISE", 3),
            getattr(win32cred, "CRED_PERSIST_SESSION", 1),
        ):
            try:
                win32cred.CredWrite({
                    "Type": win32cred.CRED_TYPE_GENERIC,
                    "TargetName": _CREDENTIAL_TARGET,
                    "UserName": user_login or "User",
                    "CredentialBlob": cleaned,
                    "Persist": persist,
                }, 0)
                break
            except TypeError:
                win32cred.CredWrite({
                    "Type": win32cred.CRED_TYPE_GENERIC,
                    "TargetName": _CREDENTIAL_TARGET,
                    "UserName": user_login or "User",
                    "CredentialBlob": cleaned.encode("utf-8"),
                    "Persist": persist,
                }, 0)
                break
    except Exception as exc:
        logger.warning("Could not persist GitHub token to Windows Credential Manager: %s", exc)

    try:
        config.update_dotenv_var("GITHUB_TOKEN", cleaned)
        config.update_dotenv_var("GH_TOKEN", cleaned)
    except Exception as exc:
        logger.debug("Could not persist GITHUB_TOKEN to .env: %s", exc)

    return True


def delete_github_token() -> bool:
    """Removes GitHub token from Windows Credential Manager and .env."""
    try:
        win32cred = _credential_manager()
        win32cred.CredDelete(_CREDENTIAL_TARGET, win32cred.CRED_TYPE_GENERIC, 0)
    except Exception as exc:
        if getattr(exc, "winerror", None) != 1168:
            logger.debug("Windows Credential Manager could not remove token: %s", exc)

    try:
        config.update_dotenv_var("GITHUB_TOKEN", "")
        config.update_dotenv_var("GH_TOKEN", "")
    except Exception:
        pass

    return True


def get_github_connection_status() -> Dict[str, Any]:
    """Validates GitHub token against the GitHub API and returns profile info."""
    token = get_github_token()
    if not token:
        return {"connected": False, "login": ""}
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=8,
        )
        if resp.status_code == 200:
            user = resp.json()
            return {"connected": True, "login": user.get("login", ""), "name": user.get("name", "")}
        return {"connected": False, "login": "", "error": f"HTTP {resp.status_code}"}
    except Exception as e:
        return {"connected": False, "login": "", "error": str(e)}


def connect_github(token: str) -> Dict[str, Any]:
    """Tests and saves a GitHub token."""
    cleaned = token.strip()
    if not cleaned:
        return {"success": False, "message": "GitHub Personal Access Token cannot be empty."}
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {cleaned}", "Accept": "application/vnd.github+json"},
            timeout=10,
        )
        if resp.status_code == 200:
            user = resp.json()
            login = user.get("login", "User")
            set_github_token(cleaned, user_login=login)
            return {"success": True, "message": f"Successfully connected GitHub account @{login}!", "login": login}
        return {"success": False, "message": f"GitHub authentication failed (HTTP {resp.status_code}). Check your token."}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {e}"}


def disconnect_github() -> Dict[str, Any]:
    """Disconnects GitHub account."""
    delete_github_token()
    return {"success": True, "message": "Disconnected GitHub account."}

