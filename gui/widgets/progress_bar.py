"""Progress bar widget — animated processing indicator with ETA.

Shows determinate progress (0-100%), a status label, and an estimated time
remaining during upscaling operations.
"""

import time
from typing import Optional

import customtkinter as ctk


class ProgressPanel(ctk.CTkFrame):
    """Horizontal progress bar with status text, percentage, and ETA."""

    def __init__(self, master, **kwargs):
        super().__init__(master, height=50, **kwargs)
        self.configure(fg_color="transparent")

        self._start_time: Optional[float] = None
        self._last_percent: float = 0

        # Top row: status text + percentage
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=4)

        self._status_label = ctk.CTkLabel(
            top,
            text="Ready",
            font=ctk.CTkFont(size=12),
            anchor="w",
        )
        self._status_label.pack(side="left")

        self._eta_label = ctk.CTkLabel(
            top,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
            anchor="e",
        )
        self._eta_label.pack(side="right")

        self._pct_label = ctk.CTkLabel(
            top,
            text="",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="e",
        )
        self._pct_label.pack(side="right", padx=(0, 8))

        # Progress bar
        self._bar = ctk.CTkProgressBar(self, height=8, corner_radius=4)
        self._bar.pack(fill="x", padx=4, pady=(4, 4))
        self._bar.set(0)

        # Cancel button (hidden by default)
        self._cancel_btn = ctk.CTkButton(
            self,
            text="⏹ Cancel",
            width=90,
            height=26,
            font=ctk.CTkFont(size=11),
            fg_color="#333333",
            hover_color="#444444",
            command=self._on_cancel,
        )
        self._cancel_callback = None

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def start(self, cancel_callback=None) -> None:
        """Reset and start tracking a new operation."""
        self._start_time = time.time()
        self._last_percent = 0
        self._cancel_callback = cancel_callback
        self._bar.set(0)
        self._pct_label.configure(text="0%")
        self._eta_label.configure(text="")
        self._status_label.configure(text="Starting…")
        if cancel_callback:
            self._cancel_btn.pack(pady=(0, 4))

    def update_progress(self, percent: float, status: str = "") -> None:
        """Update the progress bar, percentage label, and status text.

        Args:
            percent: 0-100 completion.
            status: Short status string (e.g. "Upscaling…", "Saving…").
        """
        clamped = max(0.0, min(100.0, percent))
        self._bar.set(clamped / 100.0)
        self._pct_label.configure(text=f"{int(clamped)}%")
        self._last_percent = clamped

        if status:
            self._status_label.configure(text=status)

        # ETA calculation
        if self._start_time and 0 < clamped < 100:
            elapsed = time.time() - self._start_time
            rate = clamped / elapsed  # percent per second
            remaining = (100 - clamped) / rate if rate > 0 else 0
            self._eta_label.configure(text=f"ETA {self._fmt_time(remaining)}")
        elif clamped >= 100:
            elapsed = time.time() - self._start_time if self._start_time else 0
            self._eta_label.configure(text=f"Done in {self._fmt_time(elapsed)}")

    def update_batch(self, current: int, total: int, filename: str = "") -> None:
        """Update for batch mode: 'Image 3 of 12 — photo.jpg'."""
        text = f"Image {current} of {total}"
        if filename:
            text += f"  —  {filename}"
        self._status_label.configure(text=text)

    def finish(self, message: str = "Done") -> None:
        """Mark the operation as complete."""
        self._bar.set(1.0)
        self._pct_label.configure(text="100%")
        self._status_label.configure(text=message)
        self._cancel_btn.pack_forget()
        self._cancel_callback = None

    def reset(self) -> None:
        """Reset to idle state."""
        self._bar.set(0)
        self._pct_label.configure(text="")
        self._eta_label.configure(text="")
        self._status_label.configure(text="Ready")
        self._cancel_btn.pack_forget()
        self._start_time = None
        self._cancel_callback = None

    def set_error(self, message: str) -> None:
        """Show an error state."""
        self._status_label.configure(text=f"❌ {message}")
        self._bar.configure(progress_color="#ef4444")
        self._cancel_btn.pack_forget()

    # ------------------------------------------------------------------ #
    #  Internal                                                           #
    # ------------------------------------------------------------------ #

    def _on_cancel(self) -> None:
        if self._cancel_callback:
            self._cancel_callback()
        self._status_label.configure(text="Cancelling…")
        self._cancel_btn.configure(state="disabled")

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        """Format seconds into a human-readable string."""
        s = int(seconds)
        if s < 60:
            return f"{s}s"
        m = s // 60
        s = s % 60
        return f"{m}m {s}s"
