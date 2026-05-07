# ─── AUTHENTICATION ───────────────────────────────────────────────────────────
# Handles the OAuth 2.0 flow and returns a ready-to-use Gmail service.
#
# HTTP transport: uses google-auth's AuthorizedSession (requests-based) instead
# of httplib2. This fixes [SSL: WRONG_VERSION_NUMBER] errors caused by antivirus
# SSL inspection, corporate proxies, or httplib2 quirks on Python 3.14.

import os

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request, AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from config import SCOPES, CREDENTIALS_FILE, TOKEN_FILE


class _RequestsHttp:
    """
    Thin adapter that makes AuthorizedSession (requests-based) look like
    httplib2.Http so googleapiclient can use it transparently.

    googleapiclient calls:  http.request(uri, method, body, headers)
    and expects:            (response_with_.status, bytes_content)
    """

    def __init__(self, session: AuthorizedSession):
        self._session = session

    def request(self, uri, method="GET", body=None, headers=None,
                redirections=5, connection_type=None, **_):
        resp = self._session.request(
            method  = method,
            url     = uri,
            data    = body,
            headers = headers or {},
            timeout = 60,
            allow_redirects = redirections > 0,
        )
        resp.status = resp.status_code   # alias expected by googleapiclient
        return resp, resp.content


def _delete_token():
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)


def _run_flow():
    flow  = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)
    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())
    return creds


def get_service():
    """
    Returns an authenticated Gmail service backed by requests (not httplib2).
    Auto-refreshes or re-authenticates expired / revoked tokens.
    """
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except RefreshError:
                _delete_token()
                creds = _run_flow()
        else:
            creds = _run_flow()

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    http = _RequestsHttp(AuthorizedSession(creds))
    return build("gmail", "v1", http=http)
