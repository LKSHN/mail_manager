# ─── MIXIN: SECONDARY WINDOWS ─────────────────────────────────────────────────
# Each method opens a Toplevel window delegated to the windows/ folder.

from windows.compose import ComposeWindow
from windows.labels  import LabelsWindow
from windows.filters import FiltersWindow
from windows.cleanup import CleanupWindow


class WindowsOpenerMixin:
    """Opens the application's secondary windows."""

    def _reply(self):
        """Opens ComposeWindow pre-filled to reply to the selected message."""
        sel = self.tree.selection()
        if not sel:
            return
        mid      = sel[0]
        msg_data = next((m for m in self.messages if m["id"] == mid), None)
        if msg_data:
            ComposeWindow(self, self.service,
                          to=msg_data["from"],
                          subject="Re: " + msg_data["subject"],
                          reply_to=mid)

    def _open_compose(self):
        """Opens ComposeWindow for a new message."""
        ComposeWindow(self, self.service)

    def _open_labels(self):
        """Opens LabelsWindow to manage labels."""
        LabelsWindow(self, self.service, self.labels_map, on_labels_changed=self._load_labels)

    def _open_cleanup(self):
        """Opens CleanupWindow for bulk cleanup."""
        CleanupWindow(self, self.service, on_done=self._refresh)

    def _open_filters(self):
        """Opens FiltersWindow to manage filters and blocked addresses."""
        FiltersWindow(self, self.service, self.labels_map)
