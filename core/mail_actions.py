# ─── MIXIN: MESSAGE ACTIONS ───────────────────────────────────────────────────
# Archive, star, mark as read, delete, apply label, context menu.

from tkinter import messagebox, simpledialog


class MailActionsMixin:
    """Groups all actions that modify the state of Gmail messages."""

    # ── SELECTION ─────────────────────────────────────────────────────────────

    def _get_selected_ids(self):
        """Returns the list of IDs of messages selected in the Treeview."""
        return list(self.tree.selection())

    # ── QUICK ACTIONS ─────────────────────────────────────────────────────────

    def _archive_selected(self):
        """Removes the INBOX label from selected messages (archiving)."""
        for mid in self._get_selected_ids():
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["INBOX"]}
            ).execute()
        self._refresh()

    def _star_selected(self):
        """Adds the STARRED label to selected messages."""
        for mid in self._get_selected_ids():
            self.service.users().messages().modify(
                userId="me", id=mid, body={"addLabelIds": ["STARRED"]}
            ).execute()
        self._refresh()

    def _mark_read(self):
        """Removes the UNREAD label from selected messages."""
        for mid in self._get_selected_ids():
            self.service.users().messages().modify(
                userId="me", id=mid, body={"removeLabelIds": ["UNREAD"]}
            ).execute()
        self._refresh()

    def _trash_selected(self):
        """Moves selected messages to trash after confirmation."""
        if not messagebox.askyesno("Confirm", "Move selected messages to trash?"):
            return
        for mid in self._get_selected_ids():
            self.service.users().messages().trash(userId="me", id=mid).execute()
        self._refresh()

    # ── LABEL ─────────────────────────────────────────────────────────────────

    def _apply_label_dialog(self):
        """Prompts the user to choose a label and applies it to selected messages."""
        names      = sorted(n for n in self.labels_map.values() if not n.startswith("CATEGORY_"))
        label_name = simpledialog.askstring(
            "Label",
            f"Available labels:\n{', '.join(names)}\n\nLabel name to apply:"
        )
        if not label_name:
            return
        label_id = next((k for k, v in self.labels_map.items() if v == label_name), None)
        if not label_id:
            messagebox.showerror("Error", f"Label '{label_name}' not found.")
            return
        for mid in self._get_selected_ids():
            self.service.users().messages().modify(
                userId="me", id=mid, body={"addLabelIds": [label_id]}
            ).execute()
        self._refresh()

    # ── CONTEXT MENU ──────────────────────────────────────────────────────────

    def _context_menu(self, event):
        """Displays the context menu on right-click over a message."""
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.ctx_menu.tk_popup(event.x_root, event.y_root)
