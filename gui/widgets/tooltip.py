"""Lightweight hover tooltips for GUI widgets, including thumbnail previews."""

import os
import tkinter as tk
from pathlib import Path
from typing import Callable, List, Optional, Union
from PIL import Image, ImageTk

from gui.utils.image_utils import format_dimensions, format_file_size, generate_thumbnail, is_image_file


class ToolTip:
    """Lightweight hover tooltip for widgets with customizable delay and theme."""

    def __init__(
        self,
        widget: tk.Widget,
        text: Union[str, Callable[[], str]] = "",
        delay_ms: int = 350,
        bg_color: str = "#22252c",
        fg_color: str = "#ffffff",
        border_color: str = "#3b82f6",
    ):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.border_color = border_color
        self.tip_window: Optional[tk.Toplevel] = None
        self._after_id: Optional[str] = None
        self._bound_widgets: List[tk.Widget] = []

        self.bind_widget(self.widget)

    def bind_widget(self, w: tk.Widget) -> None:
        """Attach enter/leave/click handlers to an additional child widget."""
        if w not in self._bound_widgets:
            self._bound_widgets.append(w)
            w.bind("<Enter>", self._on_enter, add="+")
            w.bind("<Leave>", self._on_leave, add="+")
            w.bind("<Button-1>", self._on_click, add="+")
            w.bind("<Button-3>", self._on_click, add="+")
            w.bind("<Destroy>", self._on_destroy, add="+")

    def _get_text(self) -> str:
        if callable(self.text):
            return self.text()
        return str(self.text)

    def _on_enter(self, event=None) -> None:
        self._cancel_timer()
        if self.tip_window:
            return
        self._after_id = self.widget.after(self.delay_ms, self.show_tip)

    def _on_leave(self, event=None) -> None:
        self._cancel_timer()
        self.hide_tip()

    def _on_click(self, event=None) -> None:
        self._cancel_timer()
        self.hide_tip()

    def _on_destroy(self, event=None) -> None:
        self._cancel_timer()
        self.hide_tip()

    def _cancel_timer(self) -> None:
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def show_tip(self, event=None) -> None:
        """Display the tooltip popup."""
        if self.tip_window:
            return

        text = self._get_text()
        if not text:
            return

        try:
            x, y = self._calculate_position()
            tw = tk.Toplevel(self.widget)
            self.tip_window = tw
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)

            border_frame = tk.Frame(
                tw,
                background=self.border_color,
                highlightthickness=0,
                bd=1,
            )
            border_frame.pack(fill="both", expand=True)

            inner_frame = tk.Frame(
                border_frame,
                background=self.bg_color,
                padx=8,
                pady=5,
            )
            inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

            lbl = tk.Label(
                inner_frame,
                text=text,
                justify=tk.LEFT,
                background=self.bg_color,
                foreground=self.fg_color,
                font=("Segoe UI", 9),
            )
            lbl.pack()
        except Exception:
            self.hide_tip()

    def _calculate_position(self) -> tuple[int, int]:
        try:
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 8
            y = self.widget.winfo_rooty()
            screen_w = self.widget.winfo_screenwidth()
            if x + 250 > screen_w:
                x = max(10, self.widget.winfo_rootx() - 260)
            return int(x), int(y)
        except Exception:
            return 100, 100

    def hide_tip(self, event=None) -> None:
        """Hide and destroy the tooltip popup."""
        self._cancel_timer()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None

    def destroy(self) -> None:
        """Permanently clean up bindings and destroy any active window."""
        self.hide_tip()
        for w in self._bound_widgets:
            try:
                w.unbind("<Enter>")
                w.unbind("<Leave>")
            except Exception:
                pass
        self._bound_widgets.clear()


class ThumbnailToolTip(ToolTip):
    """Hover tooltip that previews an image thumbnail with metadata or error information."""

    def __init__(
        self,
        widget: tk.Widget,
        image_path: Union[str, Path, Callable[[], Optional[str]]],
        title: str = "Preview",
        details: str = "",
        error: Optional[str] = None,
        max_size: int = 150,
        delay_ms: int = 350,
    ):
        super().__init__(widget, text="", delay_ms=delay_ms, border_color="#3b82f6")
        self.image_path_getter = image_path
        self.title = title
        self.details = details
        self.error = error
        self.max_size = max_size
        self._cached_photo: Optional[ImageTk.PhotoImage] = None
        self._cached_path: Optional[str] = None

    def _get_path(self) -> Optional[str]:
        if callable(self.image_path_getter):
            p = self.image_path_getter()
        else:
            p = str(self.image_path_getter) if self.image_path_getter else None
        return p if p and os.path.exists(p) else None

    def show_tip(self, event=None) -> None:
        """Display rich preview popup with thumbnail and metadata."""
        if self.tip_window:
            return

        path = self._get_path()
        has_error = bool(self.error)

        if not path and not has_error:
            return

        try:
            x, y = self._calculate_position()
            tw = tk.Toplevel(self.widget)
            self.tip_window = tw
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)

            border_color = "#ef4444" if has_error else "#3b82f6"
            border_frame = tk.Frame(
                tw,
                background=border_color,
                highlightthickness=0,
                bd=1,
            )
            border_frame.pack(fill="both", expand=True)

            card_frame = tk.Frame(
                border_frame,
                background="#1e2025",
                padx=8,
                pady=6,
            )
            card_frame.pack(fill="both", expand=True, padx=1, pady=1)

            # Header title
            header_color = "#f87171" if has_error else "#60a5fa"
            title_lbl = tk.Label(
                card_frame,
                text=self.title,
                font=("Segoe UI", 9, "bold"),
                foreground=header_color,
                background="#1e2025",
                anchor="w",
            )
            title_lbl.pack(fill="x", pady=(0, 4))

            # Thumbnail image if available
            if path and is_image_file(path):
                if self._cached_photo is None or self._cached_path != path:
                    pil_thumb = generate_thumbnail(path, max_size=self.max_size)
                    if pil_thumb:
                        self._cached_photo = ImageTk.PhotoImage(pil_thumb)
                        self._cached_path = path

                if self._cached_photo:
                    img_container = tk.Frame(card_frame, background="#111215", padx=2, pady=2)
                    img_container.pack(pady=(0, 6))

                    img_lbl = tk.Label(
                        img_container,
                        image=self._cached_photo,
                        background="#111215",
                    )
                    img_lbl.image = self._cached_photo  # Keep reference
                    img_lbl.pack()

            # Metadata details or error message
            if has_error:
                err_lbl = tk.Label(
                    card_frame,
                    text=f"Error: {self.error}",
                    font=("Segoe UI", 8),
                    foreground="#fca5a5",
                    background="#1e2025",
                    wraplength=240,
                    justify=tk.LEFT,
                )
                err_lbl.pack(fill="x")
            elif self.details:
                det_lbl = tk.Label(
                    card_frame,
                    text=self.details,
                    font=("Segoe UI", 8),
                    foreground="#9ca3af",
                    background="#1e2025",
                    anchor="w",
                )
                det_lbl.pack(fill="x")

        except Exception:
            self.hide_tip()
