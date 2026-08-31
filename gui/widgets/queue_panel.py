"""Queue panel — left-hand sidebar showing the batch processing queue.

Each item displays filename, dimensions, size, and processing status.
Supports selection, removal, and reordering.
"""

import os
from enum import Enum, auto
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import customtkinter as ctk

from gui.utils.image_utils import (
    format_file_size,
    format_dimensions,
    get_image_info,
    is_image_file,
    is_video_file,
)
from gui.utils.video_utils import format_duration, get_video_info


class ItemStatus(Enum):
    QUEUED = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    ERROR = auto()


@dataclass
class QueueItem:
    """Represents a single file in the processing queue."""
    path: str
    filename: str = ""
    width: int = 0
    height: int = 0
    size_bytes: int = 0
    is_video: bool = False
    fps: float = 0
    duration_s: float = 0
    status: ItemStatus = ItemStatus.QUEUED
    progress: float = 0  # 0-100 for processing
    output_path: Optional[str] = None
    error: Optional[str] = None

    def __post_init__(self):
        self.filename = os.path.basename(self.path)


class QueuePanel(ctk.CTkFrame):
    """Left sidebar showing the file queue.

    Parameters
    ----------
    on_item_selected : callable
        ``(QueueItem) -> None`` when user clicks an item.
    on_add_files : callable
        ``() -> None`` to trigger file browser.
    """

    def __init__(
        self,
        master,
        on_item_selected: Optional[Callable] = None,
        on_add_files: Optional[Callable] = None,
        **kwargs,
    ):
        super().__init__(master, width=220, **kwargs)
        self.configure(fg_color="#1e1e1e")

        self._items: List[QueueItem] = []
        self._selected_idx: int = -1
        self._on_item_selected = on_item_selected
        self._on_add_files = on_add_files

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent", height=36)
        header.pack(fill="x", padx=8, pady=(8, 4))
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="Queue",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(side="left")
        self._count_label = ctk.CTkLabel(
            header,
            text="0 files",
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
        )
        self._count_label.pack(side="right")

        # Scrollable list
        self._list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self._list_frame.pack(fill="both", expand=True, padx=4, pady=4)

        # Bottom buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(4, 8))

        ctk.CTkButton(
            btn_frame,
            text="+ Add Files",
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="#2b2b2b",
            hover_color="#3b3b3b",
            command=self._on_add_click,
        ).pack(fill="x", pady=(0, 4))

        self._process_all_btn = ctk.CTkButton(
            btn_frame,
            text="▸ Process All",
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="#2563eb",
            hover_color="#1d4ed8",
        )
        self._process_all_btn.pack(fill="x", pady=(0, 4))

        ctk.CTkButton(
            btn_frame,
            text="✕ Clear All",
            height=30,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#a0a0a0",
            command=self.clear,
        ).pack(fill="x")

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    def add_files(self, paths: List[str]) -> None:
        """Add files to the queue, collecting metadata."""
        for p in paths:
            if any(item.path == p for item in self._items):
                continue  # skip duplicates

            item = QueueItem(path=p)

            if is_image_file(p):
                info = get_image_info(p)
                item.width = info.get("width", 0)
                item.height = info.get("height", 0)
                item.size_bytes = info.get("size_bytes", 0)
            elif is_video_file(p):
                item.is_video = True
                vinfo = get_video_info(p)
                item.width = vinfo.get("width", 0)
                item.height = vinfo.get("height", 0)
                item.fps = vinfo.get("fps", 0)
                item.duration_s = vinfo.get("duration_s", 0)
                item.size_bytes = Path(p).stat().st_size
            else:
                continue  # unsupported

            self._items.append(item)

        self._rebuild_list()

        # Auto-select first item if none selected
        if self._selected_idx < 0 and self._items:
            self.select(0)

    def clear(self) -> None:
        """Remove all items from the queue."""
        self._items.clear()
        self._selected_idx = -1
        self._rebuild_list()

    def remove(self, idx: int) -> None:
        """Remove item at index."""
        if 0 <= idx < len(self._items):
            self._items.pop(idx)
            if self._selected_idx >= len(self._items):
                self._selected_idx = len(self._items) - 1
            self._rebuild_list()

    def select(self, idx: int) -> None:
        """Select and highlight item at index."""
        if 0 <= idx < len(self._items):
            self._selected_idx = idx
            self._rebuild_list()
            if self._on_item_selected:
                self._on_item_selected(self._items[idx])

    def update_item_status(
        self, idx: int, status: ItemStatus, progress: float = 0, output_path: str = ""
    ) -> None:
        """Update the status of a queue item."""
        if 0 <= idx < len(self._items):
            self._items[idx].status = status
            self._items[idx].progress = progress
            if output_path:
                self._items[idx].output_path = output_path
            self._rebuild_list()

    def get_items(self) -> List[QueueItem]:
        """Return all queue items."""
        return list(self._items)

    def get_selected(self) -> Optional[QueueItem]:
        """Return the currently selected item."""
        if 0 <= self._selected_idx < len(self._items):
            return self._items[self._selected_idx]
        return None

    def get_selected_index(self) -> int:
        return self._selected_idx

    def set_process_all_command(self, command: Callable) -> None:
        """Set the callback for the 'Process All' button."""
        self._process_all_btn.configure(command=command)

    @property
    def count(self) -> int:
        return len(self._items)

    # ------------------------------------------------------------------ #
    #  Internal                                                           #
    # ------------------------------------------------------------------ #

    def _rebuild_list(self) -> None:
        """Rebuild the visual list of queue items."""
        # Clear existing widgets
        for w in self._list_frame.winfo_children():
            w.destroy()

        self._count_label.configure(text=f"{len(self._items)} file{'s' if len(self._items) != 1 else ''}")

        for i, item in enumerate(self._items):
            selected = i == self._selected_idx
            self._create_item_widget(i, item, selected)

    def _create_item_widget(self, idx: int, item: QueueItem, selected: bool) -> None:
        """Create a single queue item card."""
        fg = "#2a2d35" if selected else "transparent"
        card = ctk.CTkFrame(self._list_frame, fg_color=fg, corner_radius=6, height=56)
        card.pack(fill="x", pady=2, padx=2)
        card.pack_propagate(False)
        card.bind("<Button-1>", lambda e, i=idx: self.select(i))

        # Icon + filename
        icon = "🎬" if item.is_video else "🖼"
        name_label = ctk.CTkLabel(
            card,
            text=f"{icon}  {item.filename}",
            font=ctk.CTkFont(size=12, weight="bold" if selected else "normal"),
            anchor="w",
        )
        name_label.pack(anchor="w", padx=8, pady=(6, 0))
        name_label.bind("<Button-1>", lambda e, i=idx: self.select(i))

        # Metadata line
        if item.is_video:
            meta = f"{format_dimensions(item.width, item.height)} · {item.fps:.0f}fps · {format_duration(item.duration_s)}"
        else:
            meta = f"{format_dimensions(item.width, item.height)} · {format_file_size(item.size_bytes)}"

        # Status
        status_map = {
            ItemStatus.QUEUED: ("○ Queued", "#808080"),
            ItemStatus.PROCESSING: (f"◐ Processing… {int(item.progress)}%", "#3b82f6"),
            ItemStatus.COMPLETED: ("● Done ✓", "#4ade80"),
            ItemStatus.ERROR: ("● Error ✗", "#ef4444"),
        }
        status_text, status_color = status_map.get(
            item.status, ("○ Queued", "#808080")
        )

        info_text = f"{meta}  ·  {status_text}"
        info_label = ctk.CTkLabel(
            card,
            text=info_text,
            font=ctk.CTkFont(size=10),
            text_color=status_color,
            anchor="w",
        )
        info_label.pack(anchor="w", padx=8, pady=(0, 4))
        info_label.bind("<Button-1>", lambda e, i=idx: self.select(i))

    def _on_add_click(self) -> None:
        if self._on_add_files:
            self._on_add_files()
