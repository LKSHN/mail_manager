# ─── EMAIL UTILITIES ──────────────────────────────────────────────────────────
# Decoding and content extraction functions for Gmail messages.

import base64
import html


def _extract_parts(payload, plain_parts, html_parts):
    """
    Recursively walks the MIME payload to collect text/plain and text/html
    parts, including from nested multipart structures
    (multipart/mixed, multipart/alternative, etc.).
    """
    mime = payload.get("mimeType", "")

    if mime == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            plain_parts.append(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))

    elif mime == "text/html":
        data = payload.get("body", {}).get("data", "")
        if data:
            html_parts.append(base64.urlsafe_b64decode(data).decode("utf-8", errors="replace"))

    for part in payload.get("parts", []):
        _extract_parts(part, plain_parts, html_parts)


def decode_body(payload):
    """
    Extracts the body of a Gmail message and returns it as HTML.

    Priority:
      1. Native HTML (text/html) — rendered as-is by HtmlFrame.
      2. Plain text (text/plain) — wrapped in a <pre> to preserve formatting.
      3. Empty placeholder if no part is found.

    Returns a tuple (html_str, True).
    """
    plain_parts, html_parts = [], []
    _extract_parts(payload, plain_parts, html_parts)

    if html_parts:
        return "\n".join(html_parts), True

    if plain_parts:
        escaped = html.escape("\n".join(plain_parts))
        return f"<pre style='font-family:sans-serif;white-space:pre-wrap'>{escaped}</pre>", True

    return "<p><em>(Empty body or unsupported format)</em></p>", True


def get_header(headers, name):
    """
    Looks up a header by name (case-insensitive) in a Gmail message header list.
    Returns the value if found, or an empty string if absent.
    """
    for h in headers:
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""
