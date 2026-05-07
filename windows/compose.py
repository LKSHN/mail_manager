# ─── COMPOSE WINDOW ───────────────────────────────────────────────────────────
# Allows drafting and sending an email (new message or reply).

import base64
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


class ComposeWindow(tk.Toplevel):
    """
    Email composition window.

    Parameters
    ----------
    parent      : parent window (GmailApp)
    service     : authenticated Gmail API service
    to          : recipient address (pre-filled for replies)
    subject     : subject line (pre-filled for replies, prefixed with "Re: ")
    body        : message body (optional)
    reply_to    : ID of the thread to reply to (None for a new message)
    """

    def __init__(self, parent, service, to="", subject="", body="", reply_to=None):
        super().__init__(parent)
        self.service   = service
        self.reply_to  = reply_to

        self.title("New message")
        self.geometry("640x500")
        self.configure(bg="#1e1e2e")

        self._build_ui(to, subject, body)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self, to, subject, body):
        f = ttk.Frame(self, padding=12)
        f.pack(fill="both", expand=True)

        # To and Subject fields
        for label_text, default in [("To:", to), ("Subject:", subject)]:
            row = ttk.Frame(f)
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=label_text, width=8).pack(side="left")
            var = tk.StringVar(value=default)
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)
            if label_text == "To:":
                self.to_var   = var
            else:
                self.subj_var = var

        # Message body input
        ttk.Label(f, text="Message:").pack(anchor="w", pady=(6, 2))
        self.body_text = scrolledtext.ScrolledText(
            f, height=15, bg="#313244", fg="#cdd6f4",
            font=("Segoe UI", 10), relief="flat"
        )
        self.body_text.pack(fill="both", expand=True)
        if body:
            self.body_text.insert("end", body)

        # Send / Cancel buttons
        btn_frame = ttk.Frame(f)
        btn_frame.pack(fill="x", pady=(8, 0))
        ttk.Button(btn_frame, text="📤 Send", command=self._send,
                   style="Accent.TButton").pack(side="right")
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side="right", padx=4)

    # ── SEND ──────────────────────────────────────────────────────────────────

    def _send(self):
        """Encodes the message in base64 and sends it via the Gmail API."""
        to      = self.to_var.get()
        subject = self.subj_var.get()
        body    = self.body_text.get("1.0", "end")

        try:
            msg            = MIMEMultipart()
            msg["to"]      = to
            msg["subject"] = subject
            msg.attach(MIMEText(body, "plain"))
            raw     = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            payload = {"raw": raw}

            # If replying, attach to the existing thread
            if self.reply_to:
                payload["threadId"] = self.reply_to

            self.service.users().messages().send(userId="me", body=payload).execute()
            messagebox.showinfo("Sent", "Message sent successfully!")
            self.destroy()
        except Exception as e:
            messagebox.showerror("Send error", str(e))
