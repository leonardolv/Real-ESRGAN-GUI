"""Main application window — wires together all widgets and controllers.

Three-column layout:
  Left:   QueuePanel (220px)
  Center: PreviewCanvas (expandable)
  Right:  SettingsPanel (280px)

Plus toolbar at top, progress bar below preview, and status bar at bottom.
"""

import os
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from typing import List, Optional

import customtkinter as ctk
from PIL import Image
try:
    from tkinterdnd2 import TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from gui.controllers.model_manager import ModelManager
from gui.controllers.upscale_controller import (
    MsgType,
    UpscaleController,
    UpscaleJob,
    WorkerMessage,
)
from gui.utils.config import Config
from gui.utils.image_utils import (
    generate_thumbnail,
    is_image_file,
    is_supported_file,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
    ALL_EXTENSIONS,
)
from gui.widgets.drop_zone import DropZone
from gui.widgets.preview_canvas import PreviewCanvas
from gui.widgets.progress_bar import ProgressPanel
from gui.widgets.queue_panel import ItemStatus, QueuePanel
from gui.widgets.settings_panel import SettingsPanel
from gui.widgets.toolbar import Toolbar


class RealESRGANApp(ctk.CTk, TkinterDnD.DnDWrapper if HAS_DND else object):
    """The main Real-ESRGAN GUI application window."""

    MIN_WIDTH = 1100
    MIN_HEIGHT = 700

    def __init__(self):
        super().__init__()
        global HAS_DND
        if HAS_DND:
            try:
                self.TkdndVersion = TkinterDnD._require(self)
            except Exception as e:
                print(f"Warning: Drag-and-drop disabled. Failed to initialize TkinterDnD: {e}")
                HAS_DND = False

        # ---- Configuration ---- #
        self.config_store = Config()
        self._apply_theme()

        # ---- Window setup ---- #
        self.title("Real-ESRGAN GUI")
        self.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self._restore_geometry()

        # ---- Controllers ---- #
        self.model_manager = ModelManager()
        self.upscale_ctrl = UpscaleController(self.model_manager)
        self.upscale_ctrl.on_message = self._on_worker_message

        # ---- Build UI ---- #
        self._build_toolbar()
        self._build_main_area()
        self._build_status_bar()

        # ---- Keyboard shortcuts ---- #
        self._bind_shortcuts()

        # ---- Restore settings ---- #
        self.settings_panel.load_settings(self.config_store.data)

        # ---- Window events ---- #
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # ---- Start polling worker messages ---- #
        self._poll_worker()

        # ---- Ensure window is visible and focused ---- #
        self.lift()
        self.focus_force()

    # ================================================================== #
    #  UI construction                                                    #
    # ================================================================== #

    def _build_toolbar(self) -> None:
        self.toolbar = Toolbar(
            self,
            on_open=self._open_files,
            on_save=self._save_output,
            on_open_output=self._open_output_folder,
        )
        self.toolbar.pack(fill="x")

    def _build_main_area(self) -> None:
        """Build the three-column layout."""
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True)

        # Left: queue panel
        self.queue_panel = QueuePanel(
            main,
            on_item_selected=self._on_queue_item_selected,
            on_add_files=self._open_files,
        )
        self.queue_panel.pack(side="left", fill="y")
        self.queue_panel.set_process_all_command(self._process_all)

        # Right: settings panel
        self.settings_panel = SettingsPanel(
            main,
            model_manager=self.model_manager,
            on_settings_changed=self._on_setting_changed,
        )
        self.settings_panel.pack(side="right", fill="y")
        self._upscale_btn = self.settings_panel.add_upscale_button(self._start_upscale)

        # Center: preview + progress
        center = ctk.CTkFrame(main, fg_color="transparent")
        center.pack(side="left", fill="both", expand=True)

        self.preview = PreviewCanvas(center)
        self.preview.pack(fill="both", expand=True)

        self.progress = ProgressPanel(center)
        self.progress.pack(fill="x", padx=8, pady=(4, 4))

        # Drop zone (shown when queue is empty)
        self.drop_zone = DropZone(
            self.preview,
            on_files_dropped=self._on_files_received,
        )
        self._show_drop_zone()

    def _build_status_bar(self) -> None:
        status = ctk.CTkFrame(self, height=26, corner_radius=0, fg_color="#1a1a1a")
        status.pack(fill="x", side="bottom")
        status.pack_propagate(False)

        self._status_text = ctk.CTkLabel(
            status,
            text="Ready",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self._status_text.pack(side="left", padx=8)

        # GPU info
        gpu = self.upscale_ctrl.get_gpu_info()
        gpu_text = gpu["name"]
        if gpu["total_vram_gb"] > 0:
            gpu_text += f"  ·  VRAM: {gpu['used_vram_gb']}/{gpu['total_vram_gb']} GB"

        self._gpu_label = ctk.CTkLabel(
            status,
            text=gpu_text,
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
            anchor="e",
        )
        self._gpu_label.pack(side="right", padx=8)

        # Show CPU warning if no GPU
        if gpu["device"] == "cpu":
            self._status_text.configure(
                text="⚠ No CUDA GPU — running in CPU mode (slower)",
                text_color="#fbbf24",
            )

    # ================================================================== #
    #  File operations                                                    #
    # ================================================================== #

    def _open_files(self) -> None:
        """Open file dialog and add selected files to the queue."""
        filetypes = [
            ("All supported", " ".join(f"*{e}" for e in sorted(ALL_EXTENSIONS))),
            ("Images", " ".join(f"*{e}" for e in sorted(IMAGE_EXTENSIONS))),
            ("Videos", " ".join(f"*{e}" for e in sorted(VIDEO_EXTENSIONS))),
            ("All files", "*.*"),
        ]
        last_dir = self.config_store.get("last_input_folder") or ""
        paths = tk.filedialog.askopenfilenames(
            title="Select files to upscale",
            filetypes=filetypes,
            initialdir=last_dir if last_dir else None,
        )
        if paths:
            self.config_store.set("last_input_folder", str(Path(paths[0]).parent))
            self._on_files_received(list(paths))

    def _on_files_received(self, paths: List[str]) -> None:
        """Handle files from drop zone or file dialog."""
        # Expand directories
        expanded: List[str] = []
        for p in paths:
            pp = Path(p)
            if pp.is_dir():
                for f in sorted(pp.iterdir()):
                    if is_supported_file(f):
                        expanded.append(str(f))
            elif is_supported_file(p):
                expanded.append(p)

        if not expanded:
            return

        self.queue_panel.add_files(expanded)
        self._hide_drop_zone()

        for p in expanded:
            self.config_store.add_recent_file(p)

    def _save_output(self) -> None:
        """Save the current output image via Save As dialog."""
        item = self.queue_panel.get_selected()
        if not item or not item.output_path:
            return

        save_path = tk.filedialog.asksaveasfilename(
            title="Save upscaled image",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("WebP", "*.webp")],
            initialfile=os.path.basename(item.output_path),
        )
        if save_path:
            import shutil
            shutil.copy2(item.output_path, save_path)
            self._status_text.configure(text=f"Saved to {save_path}")

    def _open_output_folder(self) -> None:
        """Open the output folder in the system file manager."""
        folder = self.settings_panel.get_settings().get("output_folder", "results")
        abs_folder = Path(folder).resolve()
        abs_folder.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(abs_folder))
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(abs_folder)])
        else:
            subprocess.Popen(["xdg-open", str(abs_folder)])

    # ================================================================== #
    #  Upscale actions                                                    #
    # ================================================================== #

    def _start_upscale(self) -> None:
        """Upscale the currently selected queue item."""
        item = self.queue_panel.get_selected()
        if item is None:
            self._status_text.configure(text="No file selected")
            return

        if self.upscale_ctrl.is_busy:
            self._status_text.configure(text="Already processing — please wait")
            return

        settings = self.settings_panel.get_settings()

        job = UpscaleJob(
            input_path=item.path,
            output_path=settings["output_folder"],
            model_name=settings["model_name"],
            outscale=settings["outscale"],
            tile=settings["tile"],
            tile_pad=settings["tile_pad"],
            pre_pad=settings["pre_pad"],
            face_enhance=settings["face_enhance"],
            fp32=settings["fp32"],
            denoise_strength=settings["denoise_strength"],
            alpha_upsampler=settings["alpha_upsampler"],
            output_ext=settings["output_ext"],
            suffix=settings["suffix"],
        )

        idx = self.queue_panel.get_selected_index()
        self.queue_panel.update_item_status(idx, ItemStatus.PROCESSING)
        self.settings_panel.set_upscale_button_state(False)
        self.progress.start(cancel_callback=self.upscale_ctrl.cancel)

        self.upscale_ctrl.submit(job)

    def _process_all(self) -> None:
        """Start processing all queued items sequentially."""
        items = self.queue_panel.get_items()
        if not items:
            return

        if self.upscale_ctrl.is_busy:
            self._status_text.configure(text="Already processing — please wait")
            return

        settings = self.settings_panel.get_settings()
        jobs = []
        for item in items:
            if item.status == ItemStatus.COMPLETED:
                continue  # skip already done
            jobs.append(UpscaleJob(
                input_path=item.path,
                output_path=settings["output_folder"],
                model_name=settings["model_name"],
                outscale=settings["outscale"],
                tile=settings["tile"],
                tile_pad=settings["tile_pad"],
                pre_pad=settings["pre_pad"],
                face_enhance=settings["face_enhance"],
                fp32=settings["fp32"],
                denoise_strength=settings["denoise_strength"],
                alpha_upsampler=settings["alpha_upsampler"],
                output_ext=settings["output_ext"],
                suffix=settings["suffix"],
            ))

        if not jobs:
            self._status_text.configure(text="All items already processed")
            return

        self.settings_panel.set_upscale_button_state(False)
        self.progress.start(cancel_callback=self.upscale_ctrl.cancel)
        self.upscale_ctrl.submit_batch(jobs)

    # ================================================================== #
    #  Worker message handling                                            #
    # ================================================================== #

    def _poll_worker(self) -> None:
        """Poll the worker message queue (called every 50ms)."""
        self.upscale_ctrl.poll()
        self.after(50, self._poll_worker)

    def _on_worker_message(self, msg: WorkerMessage) -> None:
        """Handle messages from the upscale worker thread.

        Note: This is called from the polling loop, so it's safe to update UI.
        """
        if msg.type == MsgType.PROGRESS:
            d = msg.data
            self.progress.update_progress(d.get("percent", 0), d.get("status", ""))
            idx = self.queue_panel.get_selected_index()
            if idx >= 0:
                self.queue_panel.update_item_status(
                    idx, ItemStatus.PROCESSING, d.get("percent", 0)
                )

        elif msg.type == MsgType.COMPLETE:
            d = msg.data
            self.progress.finish("✓ Upscaling complete")
            self.settings_panel.set_upscale_button_state(True)
            self.toolbar.set_save_enabled(True)

            idx = self.queue_panel.get_selected_index()
            if idx >= 0:
                self.queue_panel.update_item_status(
                    idx, ItemStatus.COMPLETED, 100, d.get("output_path", "")
                )

            # Load output into preview
            output_path = d.get("output_path", "")
            if output_path and os.path.isfile(output_path):
                try:
                    output_img = Image.open(output_path)
                    self.preview.set_output_image(output_img)
                except Exception:
                    pass

            self._status_text.configure(text=f"✓ Saved: {os.path.basename(output_path)}")
            self._update_gpu_info()

        elif msg.type == MsgType.ERROR:
            error_text = str(msg.data)
            self.progress.set_error(error_text)
            self.settings_panel.set_upscale_button_state(True)
            self._status_text.configure(text=f"Error: {error_text[:80]}")

            idx = self.queue_panel.get_selected_index()
            if idx >= 0:
                self.queue_panel.update_item_status(idx, ItemStatus.ERROR)

            # Show error dialog for CUDA OOM
            if "out of memory" in error_text.lower() or "tile" in error_text.lower():
                tk.messagebox.showwarning(
                    "GPU Out of Memory",
                    error_text + "\n\nTry setting Tile Size to 256 or 512 in the settings panel.",
                )

        elif msg.type == MsgType.BATCH_PROGRESS:
            d = msg.data
            self.progress.update_batch(d["current"], d["total"], d.get("file", ""))

        elif msg.type == MsgType.LOG:
            self._status_text.configure(text=str(msg.data))

    # ================================================================== #
    #  Queue selection                                                    #
    # ================================================================== #

    def _on_queue_item_selected(self, item) -> None:
        """When user selects a queue item, show its preview."""
        if is_image_file(item.path):
            thumb = generate_thumbnail(item.path)
            if thumb:
                self.preview.set_input_image(thumb)

            # If already processed, also show output
            if item.output_path and os.path.isfile(item.output_path):
                try:
                    output_img = Image.open(item.output_path)
                    self.preview.set_output_image(output_img)
                    self.toolbar.set_save_enabled(True)
                except Exception:
                    pass
            else:
                self.toolbar.set_save_enabled(False)

        self._status_text.configure(text=f"Selected: {item.filename}")

    # ================================================================== #
    #  Settings                                                           #
    # ================================================================== #

    def _on_setting_changed(self, key: str, value) -> None:
        """Persist setting changes."""
        config_key_map = {
            "model_name": "last_model",
            "outscale": "last_scale",
            "tile": "last_tile",
            "face_enhance": "face_enhance",
            "fp32": "fp32",
            "denoise_strength": "denoise_strength",
            "output_ext": "output_format",
            "suffix": "output_suffix",
            "output_folder": "output_folder",
        }
        config_key = config_key_map.get(key)
        if config_key:
            self.config_store.set(config_key, value)

        # If model changed, invalidate cache
        if key == "model_name":
            self.upscale_ctrl.invalidate_model_cache()

    # ================================================================== #
    #  Drop zone visibility                                               #
    # ================================================================== #

    def _show_drop_zone(self) -> None:
        self.drop_zone.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.7, relheight=0.6)

    def _hide_drop_zone(self) -> None:
        self.drop_zone.place_forget()

    # ================================================================== #
    #  Theme                                                              #
    # ================================================================== #

    def _apply_theme(self) -> None:
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

    # ================================================================== #
    #  Keyboard shortcuts                                                 #
    # ================================================================== #

    def _bind_shortcuts(self) -> None:
        self.bind("<Control-o>", lambda e: self._open_files())
        self.bind("<Control-s>", lambda e: self._save_output())
        self.bind("<Return>", self._on_return_key)
        self.bind("<Escape>", lambda e: self.upscale_ctrl.cancel())
        self.bind("<Delete>", lambda e: self._delete_selected())
        self.bind("<Control-q>", lambda e: self._on_close())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

    def _on_return_key(self, event) -> None:
        """Handle Return key — ignore if focus is in a text entry."""
        widget = self.focus_get()
        if widget and widget.winfo_class() in ("Entry", "TEntry", "Text"):
            return  # Don't trigger upscale when typing in an entry
        self._start_upscale()

    def _delete_selected(self) -> None:
        idx = self.queue_panel.get_selected_index()
        if idx >= 0:
            self.queue_panel.remove(idx)
            if self.queue_panel.count == 0:
                self.preview.clear()
                self._show_drop_zone()

    def _toggle_fullscreen(self) -> None:
        current = self.attributes("-fullscreen")
        self.attributes("-fullscreen", not current)

    # ================================================================== #
    #  Window lifecycle                                                   #
    # ================================================================== #

    def _restore_geometry(self) -> None:
        w = self.config_store.get("window_width", 1400)
        h = self.config_store.get("window_height", 850)
        x = self.config_store.get("window_x")
        y = self.config_store.get("window_y")

        if x is not None and y is not None:
            # Validate that the saved position is on a visible screen
            if self._is_position_on_screen(x, y, w, h):
                self.geometry(f"{w}x{h}+{x}+{y}")
            else:
                # Position is off-screen — center on primary monitor
                self.geometry(f"{w}x{h}")
                self.update_idletasks()
                screen_w = self.winfo_screenwidth()
                screen_h = self.winfo_screenheight()
                cx = max(0, (screen_w - w) // 2)
                cy = max(0, (screen_h - h) // 2)
                self.geometry(f"{w}x{h}+{cx}+{cy}")
        else:
            self.geometry(f"{w}x{h}")

        if self.config_store.get("window_maximized"):
            self.state("zoomed")

    @staticmethod
    def _is_position_on_screen(x: int, y: int, w: int, h: int) -> bool:
        """Check if at least part of the window is visible on any screen.

        Uses a simple heuristic: the top-left corner should be within
        reasonable bounds.  On Windows with multiple monitors the
        virtual screen can have negative coordinates, but a single-monitor
        setup always starts at (0, 0).
        """
        try:
            import ctypes
            user32 = ctypes.windll.user32
            screen_w = user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            screen_h = user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            screen_x = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            screen_y = user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            # At least 100px of the window must be on the virtual screen
            return (
                x + 100 > screen_x
                and y + 100 > screen_y
                and x < screen_x + screen_w
                and y < screen_y + screen_h
            )
        except Exception:
            # Not on Windows or ctypes unavailable — trust the saved position
            return True

    def _save_geometry(self) -> None:
        try:
            geo = self.geometry()
            # Format: WxH+X+Y
            size, pos = geo.split("+", 1)
            w, h = size.split("x")
            parts = pos.split("+")
            self.config_store.update({
                "window_width": int(w),
                "window_height": int(h),
                "window_x": int(parts[0]),
                "window_y": int(parts[1]) if len(parts) > 1 else 0,
                "window_maximized": self.state() == "zoomed",
            })
        except Exception:
            pass

    def _on_close(self) -> None:
        """Clean shutdown."""
        self._save_geometry()
        # Save current settings
        settings = self.settings_panel.get_settings()
        self._on_setting_changed("model_name", settings["model_name"])
        self._on_setting_changed("outscale", settings["outscale"])

        if self.upscale_ctrl.is_busy:
            self.upscale_ctrl.cancel()

        self.destroy()

    def _update_gpu_info(self) -> None:
        """Refresh GPU VRAM usage in the status bar."""
        gpu = self.upscale_ctrl.get_gpu_info()
        if gpu["total_vram_gb"] > 0:
            text = f"{gpu['name']}  ·  VRAM: {gpu['used_vram_gb']}/{gpu['total_vram_gb']} GB"
        else:
            text = gpu["name"]
        self._gpu_label.configure(text=text)
