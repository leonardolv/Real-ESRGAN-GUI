"""Drop zone widget — drag-and-drop area for file input.

Displays a large, inviting area with a dashed border that accepts image and
video files via drag-and-drop or click-to-browse.
"""

import tkinter as tk
from pathlib import Path
from typing import Callable, List, Optional

import customtkinter as ctk

from gui.utils.image_utils import ALL_EXTENSIONS, IMAGE_EXTENSIONS, VIDEO_EXTENSIONS


class DropZone(ctk.CTkFrame):
    """A drag-and-drop target area that also acts as a browse button.

    Parameters
    ----------
    master : widget
        Parent widget.
    on_files_dropped : callable
        ``(list[str]) -> None`` callback when files are accepted.
    """

    def __init__(
        self,
        master,
        on_files_dropped: Callable[[List[str]], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.on_files_dropped = on_files_dropped

        self.configure(
            corner_radius=12,
            fg_color="#1c1c1c",
            border_width=2,
            border_color="#444444",
        )

        # ---- inner content ---- #
        self._icon_label = ctk.CTkLabel(
            self,
            text="📁",
            font=ctk.CTkFont(size=48),
        )
        self._icon_label.pack(pady=(40, 8))

        self._title_label = ctk.CTkLabel(
            self,
            text="Drop images or video here",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._title_label.pack(pady=(0, 4))

        self._subtitle_label = ctk.CTkLabel(
            self,
            text="or click to browse",
            font=ctk.CTkFont(size=13),
            text_color="#a0a0a0",
        )
        self._subtitle_label.pack(pady=(0, 8))

        # Supported formats hint
        img_exts = ", ".join(sorted(e.lstrip(".").upper() for e in IMAGE_EXTENSIONS))
        vid_exts = ", ".join(sorted(e.lstrip(".").upper() for e in VIDEO_EXTENSIONS))
        self._formats_label = ctk.CTkLabel(
            self,
            text=f"Images: {img_exts}\nVideos: {vid_exts}",
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
            justify="center",
        )
        self._formats_label.pack(pady=(4, 40))

        # Bind click to open file dialog
        self.bind("<Button-1>", self._on_click)
        for child in self.winfo_children():
            child.bind("<Button-1>", self._on_click)

        # Try to set up tkdnd (drag-and-drop) — gracefully degrade if unavailable
        self._setup_dnd()

    # ------------------------------------------------------------------ #
    #  Drag-and-drop via tkdnd                                            #
    # ------------------------------------------------------------------ #

    def _setup_dnd(self) -> None:
        """Register drag-and-drop handlers if tkinterdnd2 is available."""
        try:
            # tkinterdnd2 patches the root window
            root = self.winfo_toplevel()
            if hasattr(root, "drop_target_register"):
                root.drop_target_register("DND_Files")  # type: ignore[attr-defined]
                root.dnd_bind("<<Drop>>", self._on_dnd_drop)  # type: ignore[attr-defined]
                root.dnd_bind("<<DragEnter>>", self._on_drag_enter)  # type: ignore[attr-defined]
                root.dnd_bind("<<DragLeave>>", self._on_drag_leave)  # type: ignore[attr-defined]
        except Exception:
            pass  # tkinterdnd2 not available — browse-only mode

    def _on_dnd_drop(self, event) -> None:
        """Handle file drop event from the OS."""
        raw = event.data
        # tkdnd wraps paths with spaces in braces: {C:/my path/file.jpg}
        files = self._parse_dnd_data(raw)
        valid = [f for f in files if self._is_valid(f)]
        if valid:
            self.on_files_dropped(valid)
        self._reset_style()

    def _on_drag_enter(self, event) -> None:
        self.configure(border_color="#3b82f6")
        self._icon_label.configure(text="⬇️")

    def _on_drag_leave(self, event) -> None:
        self._reset_style()

    # ------------------------------------------------------------------ #
    #  Click-to-browse                                                    #
    # ------------------------------------------------------------------ #

    def _on_click(self, event=None) -> None:
        filetypes = [
            ("All supported", " ".join(f"*{e}" for e in sorted(ALL_EXTENSIONS))),
            ("Images", " ".join(f"*{e}" for e in sorted(IMAGE_EXTENSIONS))),
            ("Videos", " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))),
            ("All files", "*.*"),
        ]
        paths = tk.filedialog.askopenfilenames(
            title="Select files to upscale",
            filetypes=filetypes,
        )
        if paths:
            valid = [p for p in paths if self._is_valid(p)]
            if valid:
                self.on_files_dropped(valid)

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _parse_dnd_data(data: str) -> List[str]:
        """Parse tkdnd drop data which may contain brace-wrapped paths."""
        files: List[str] = []
        i = 0
        while i < len(data):
            if data[i] == "{":
                end = data.index("}", i)
                files.append(data[i + 1 : end])
                i = end + 2  # skip closing brace + space
            elif data[i] == " ":
                i += 1
            else:
                end = data.find(" ", i)
                if end == -1:
                    end = len(data)
                files.append(data[i:end])
                i = end + 1
        return files

    @staticmethod
    def _is_valid(path: str) -> bool:
        p = Path(path)
        if p.is_dir():
            return True  # Folders are expanded later
        return p.suffix.lower() in ALL_EXTENSIONS

    def _reset_style(self) -> None:
        self.configure(border_color="#444444")
        self._icon_label.configure(text="📁")
