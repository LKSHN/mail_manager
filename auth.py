# ─── AUTHENTICATION ───────────────────────────────────────────────────────────
# Handles the OAuth 2.0 flow and returns a ready-to-use Gmail service.

import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE


def _delete_token():
    """Deletes the token file if it exists."""
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def _run_flow():
    """Opens the browser for authentication and saves the new token."""
    flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    return creds


def get_service():
    """
    Loads or refreshes OAuth credentials and returns the Gmail service.

    - If a valid token exists in TOKEN_FILE, it is reused.
    - If the token is expired but refreshable, it is refreshed automatically.
    - If the refresh fails (invalid_grant / revoked token), the token is deleted
      and the browser opens for a new authentication.
    - Otherwise, opens the browser for the initial authentication.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                # Invalid or revoked token — restart from scratch
                _delete_token()
                creds = _run_flow()
        else:
            creds = _run_flow()

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)
