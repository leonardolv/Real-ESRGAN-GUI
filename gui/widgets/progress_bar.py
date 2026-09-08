"""Progress bar widget — animated processing indicator with batch ETA.

Shows determinate progress (0-100%), a status label, and an estimated time
remaining (ETA) based on average item processing speed during upscaling operations.
"""

import time
from typing import Callable, List, Optional

import customtkinter as ctk


class ProgressPanel(ctk.CTkFrame):
    """Horizontal progress bar with status text, percentage, and ETA."""

    def __init__(self, master, **kwargs):
        super().__init__(master, height=50, **kwargs)
        self.configure(fg_color="transparent")

        self._start_time: Optional[float] = None
        self._last_percent: float = 0
        self._batch_total: int = 1
        self._batch_current: int = 1
        self._item_start_time: Optional[float] = None
        self._item_durations: List[float] = []
        self._current_filename: str = ""

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
        self._cancel_callback: Optional[Callable[[], None]] = None

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def start(self, cancel_callback=None, batch_total: int = 1) -> None:
        """Reset and start tracking a new operation.

        Args:
            cancel_callback: Optional callable when cancel is clicked.
            batch_total: Total number of items in the job batch (default 1).
        """
        now = time.time()
        self._start_time = now
        self._item_start_time = now
        self._last_percent = 0
        self._batch_total = max(1, int(batch_total))
        self._batch_current = 1
        self._item_durations.clear()
        self._current_filename = ""
        self._cancel_callback = cancel_callback
        self._bar.set(0)
        self._bar.configure(progress_color=("#3a7ebf", "#1f538d"))  # restore default
        self._pct_label.configure(text="0%")
        self._eta_label.configure(text="")
        self._status_label.configure(text="Starting…")
        if cancel_callback:
            self._cancel_btn.pack(pady=(0, 4))

    def update_batch(self, current: int, total: int, filename: str = "") -> None:
        """Update for batch mode: 'Image 3 of 12 — photo.jpg'."""
        self._batch_current = max(1, current)
        self._batch_total = max(1, total)
        self._current_filename = filename
        self._item_start_time = time.time()

        prefix = f"Image {self._batch_current} of {self._batch_total}"
        if filename:
            prefix += f"  —  {filename}"
        self._status_label.configure(text=prefix)

    def item_finished(self) -> None:
        """Record the completion of the current item to calculate average speed."""
        now = time.time()
        if self._item_start_time is not None:
            duration = max(0.001, now - self._item_start_time)
            self._item_durations.append(duration)
        self._item_start_time = now

    def update_progress(self, percent: float, status: str = "") -> None:
        """Update the progress bar, percentage label, and status text.

        Args:
            percent: 0-100 completion for current item or overall.
            status: Short status string (e.g. "Upscaling…", "Saving…").
        """
        item_pct = max(0.0, min(100.0, percent))

        if self._batch_total > 1:
            # Map item progress into overall batch progress
            completed_items = max(0, self._batch_current - 1)
            overall_pct = ((completed_items + (item_pct / 100.0)) / self._batch_total) * 100.0
            display_pct = max(0.0, min(100.0, overall_pct))
        else:
            display_pct = item_pct

        self._bar.set(display_pct / 100.0)
        self._pct_label.configure(text=f"{int(display_pct)}%")
        self._last_percent = display_pct

        if status:
            if self._batch_total > 1:
                prefix = f"[{self._batch_current}/{self._batch_total}] "
                if self._current_filename:
                    prefix += f"{self._current_filename}: "
                self._status_label.configure(text=f"{prefix}{status}")
            else:
                self._status_label.configure(text=status)

        # ETA calculation
        now = time.time()
        if self._batch_total > 1:
            self._update_batch_eta(item_pct, now)
        else:
            self._update_single_eta(item_pct, now)

    def _update_single_eta(self, item_pct: float, now: float) -> None:
        if self._start_time and 0 < item_pct < 100:
            elapsed = now - self._start_time
            rate = item_pct / elapsed if elapsed > 0 else 0  # percent per second
            remaining = (100.0 - item_pct) / rate if rate > 0 else 0
            self._eta_label.configure(text=f"ETA {self._fmt_time(remaining)}")
        elif item_pct >= 100:
            elapsed = now - self._start_time if self._start_time else 0
            self._eta_label.configure(text=f"Done in {self._fmt_time(elapsed)}")

    def _update_batch_eta(self, item_pct: float, now: float) -> None:
        if not self._start_time:
            return

        total_items = self._batch_total
        completed_count = len(self._item_durations)
        remaining_unstarted = max(0, total_items - self._batch_current)

        if completed_count > 0:
            avg_speed = sum(self._item_durations) / completed_count
            current_fraction_left = max(0.0, 1.0 - (item_pct / 100.0))
            current_item_remaining = current_fraction_left * avg_speed
            total_remaining = current_item_remaining + (remaining_unstarted * avg_speed)
            avg_str = f" (~{self._fmt_time(avg_speed)}/item)"
            self._eta_label.configure(text=f"ETA {self._fmt_time(total_remaining)}{avg_str}")
        else:
            # First item in progress
            item_elapsed = (now - self._item_start_time) if self._item_start_time else (now - self._start_time)
            if item_pct > 0 and item_elapsed > 0.3:
                rate = item_pct / item_elapsed
                est_item_time = 100.0 / rate if rate > 0 else 0
                current_rem = max(0.0, (100.0 - item_pct) / rate) if rate > 0 else 0
                total_remaining = current_rem + (remaining_unstarted * est_item_time)
                self._eta_label.configure(text=f"ETA {self._fmt_time(total_remaining)}")

    def finish(self, message: str = "Done") -> None:
        """Mark the operation as complete."""
        self._bar.set(1.0)
        self._pct_label.configure(text="100%")
        self._status_label.configure(text=message)
        self._cancel_btn.pack_forget()
        self._cancel_callback = None
        if self._start_time:
            elapsed = time.time() - self._start_time
            self._eta_label.configure(text=f"Done in {self._fmt_time(elapsed)}")

    def reset(self) -> None:
        """Reset to idle state."""
        self._bar.set(0)
        self._bar.configure(progress_color=("#3a7ebf", "#1f538d"))  # restore default
        self._pct_label.configure(text="")
        self._eta_label.configure(text="")
        self._status_label.configure(text="Ready")
        self._cancel_btn.pack_forget()
        self._start_time = None
        self._item_start_time = None
        self._item_durations.clear()
        self._batch_total = 1
        self._batch_current = 1
        self._current_filename = ""
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
        s = max(0, int(round(seconds)))
        if s < 60:
            return f"{s}s"
        m = s // 60
        s = s % 60
        if m < 60:
            return f"{m}m {s:02d}s" if s > 0 else f"{m}m"
        h = m // 60
        m = m % 60
        return f"{h}h {m:02d}m"
