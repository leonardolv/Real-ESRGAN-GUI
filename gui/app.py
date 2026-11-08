"""Main application window - wires together all widgets and controllers.

Three-column layout:
  Left:   QueuePanel (220px)
  Center: PreviewCanvas (expandable)
  Right:  SettingsPanel (280px)

Plus toolbar at top, progress bar below preview, and status bar at bottom.
"""

import os
import re
import subprocess
import sys
import tkinter as tk
import tkinter.filedialog
import tkinter.messagebox
from pathlib import Path
from typing import Any, List, Optional

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
    is_video_file,
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
from gui.widgets.tooltip import ToolTip


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

        # ---- Batch state tracking ---- #
        self._is_batch: bool = False
        self._batch_total: int = 0
        self._batch_completed_count: int = 0

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

        # ---- Polling handle ---- #
        self._poll_id = None

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
            on_queue_cleared=self._on_queue_cleared,
            on_files_dropped=self._on_files_received,
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
        self._status_tooltip = ToolTip(
            self._status_text, "Current application status and upscale activity"
        )

        # GPU info
        gpu = self.upscale_ctrl.get_gpu_info()
        gpu_text = gpu["name"]
        if gpu["total_vram_gb"] > 0:
            gpu_text += f" - VRAM: {gpu['used_vram_gb']}/{gpu['total_vram_gb']} GB"

        self._gpu_label = ctk.CTkLabel(
            status,
            text=gpu_text,
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
            anchor="e",
        )
        self._gpu_label.pack(side="right", padx=8)
        self._gpu_tooltip = ToolTip(
            self._gpu_label,
            "Hardware acceleration info (device, active model execution backend, and VRAM utilization)",
        )

        # Show CPU warning if no GPU
        if gpu["device"] == "cpu":
            self._status_text.configure(
                text="Warning: No CUDA GPU - running in CPU mode (slower)",
                text_color="#fbbf24",
            )

    # ================================================================== #
    #  File operations                                                    #
    # ================================================================== #

    def _open_files(self) -> None:
        """Open file dialog and add selected files to the queue."""
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or "PYTEST_CURRENT_TEST" in os.environ:
            return
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
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or "PYTEST_CURRENT_TEST" in os.environ:
            return
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
        if os.environ.get("QT_QPA_PLATFORM") == "offscreen" or "PYTEST_CURRENT_TEST" in os.environ:
            return
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
            self._status_text.configure(text="Already processing - please wait")
            return

        settings = self.settings_panel.get_settings()

        idx = self.queue_panel.get_selected_index()
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
            item_index=idx,
        )

        self._is_batch = False
        self._batch_total = 1
        self._batch_completed_count = 0
        self.queue_panel.update_item_status(idx, ItemStatus.PROCESSING)
        self.settings_panel.set_upscale_button_state(False)
        self.progress.start(cancel_callback=self.upscale_ctrl.cancel, batch_total=1)

        self.upscale_ctrl.submit(job)

    def _process_all(self) -> None:
        """Start processing all queued items sequentially."""
        items = self.queue_panel.get_items()
        if not items:
            return

        if self.upscale_ctrl.is_busy:
            self._status_text.configure(text="Already processing - please wait")
            return

        settings = self.settings_panel.get_settings()
        jobs = []
        for idx, item in enumerate(items):
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
                item_index=idx,
            ))

        if not jobs:
            self._status_text.configure(text="All items already processed")
            return

        self._is_batch = len(jobs) > 1
        self._batch_total = len(jobs)
        self._batch_completed_count = 0
        self.settings_panel.set_upscale_button_state(False)
        self.progress.start(cancel_callback=self.upscale_ctrl.cancel, batch_total=len(jobs))
        self.upscale_ctrl.submit_batch(jobs)

    # ================================================================== #
    #  Worker message handling                                            #
    # ================================================================== #

    def _poll_worker(self) -> None:
        """Poll the worker message queue (called every 50ms)."""
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
        self.upscale_ctrl.poll()
        self._poll_id = self.after(50, self._poll_worker)

    def _on_worker_message(self, msg: WorkerMessage) -> None:
        """Handle messages from the upscale worker thread.

        Note: This is called from the polling loop, so it's safe to update UI.
        """
        if msg.type == MsgType.PROGRESS:
            d = msg.data
            self.progress.update_progress(d.get("percent", 0), d.get("status", ""))
            idx = d.get("item_index")
            if idx is None or idx < 0:
                idx = self.queue_panel.get_selected_index()
            if idx is not None and idx >= 0:
                self.queue_panel.update_item_status(
                    idx, ItemStatus.PROCESSING, d.get("percent", 0)
                )

        elif msg.type == MsgType.COMPLETE:
            d = msg.data
            idx = d.get("item_index")
            if idx is None or idx < 0:
                idx = self.queue_panel.get_selected_index()
            if idx is not None and idx >= 0:
                self.queue_panel.update_item_status(
                    idx, ItemStatus.COMPLETED, 100, d.get("output_path", "")
                )

            # Record item completion for batch cadence & speed calculation
            self.progress.item_finished()

            # Load output into preview if matching current selection or only item
            output_path = d.get("output_path", "")
            selected_idx = self.queue_panel.get_selected_index()
            if (idx == selected_idx or selected_idx < 0) and output_path and os.path.isfile(output_path):
                try:
                    if is_video_file(output_path):
                        self.preview.set_output_video(output_path)
                    else:
                        output_img = Image.open(output_path)
                        self.preview.set_output_image(output_img)
                except Exception:
                    pass

            if not self._is_batch:
                self.progress.finish("✓ Upscaling complete")
                self.settings_panel.set_upscale_button_state(True)
                self.toolbar.set_save_enabled(True)
                self._status_text.configure(text=f"✓ Saved: {os.path.basename(output_path)}")
            else:
                self._batch_completed_count += 1
                self.toolbar.set_save_enabled(True)
                self._status_text.configure(
                    text=f"✓ [{self._batch_completed_count}/{self._batch_total}] Saved: {os.path.basename(output_path)}"
                )
            self._update_gpu_info()

        elif msg.type == MsgType.BATCH_COMPLETE:
            d = msg.data or {}
            total = d.get("total", self._batch_completed_count)
            self._is_batch = False
            self.progress.finish(f"✓ Batch complete ({total} items)")
            self.settings_panel.set_upscale_button_state(True)
            self.toolbar.set_save_enabled(True)
            self._status_text.configure(text=f"✓ Batch complete: {total} items processed")

        elif msg.type == MsgType.ERROR:
            if isinstance(msg.data, dict):
                error_text = str(msg.data.get("error", ""))
                idx = msg.data.get("item_index")
            else:
                error_text = str(msg.data)
                idx = self.queue_panel.get_selected_index()

            if self._is_batch:
                self.progress.item_finished()
                self._status_text.configure(text=f"Error on item: {error_text[:80]}")
            else:
                self.progress.set_error(error_text)
                self.settings_panel.set_upscale_button_state(True)
                self._status_text.configure(text=f"Error: {error_text[:80]}")

            if idx is None or idx < 0:
                idx = self.queue_panel.get_selected_index()
            if idx is not None and idx >= 0:
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
            idx = d.get("item_index")
            if idx is not None and 0 <= idx < self.queue_panel.count:
                self.queue_panel.select(idx)

        elif msg.type == MsgType.LOG:
            log_str = str(msg.data)
            self._status_text.configure(text=log_str)
            if "cancelled" in log_str.lower():
                self._is_batch = False
                self.progress.finish("Operation cancelled")
                self.settings_panel.set_upscale_button_state(True)

    # ================================================================== #
    #  Queue selection                                                    #
    # ================================================================== #

    def _on_queue_item_selected(self, item) -> None:
        """When user selects a queue item, show its preview."""
        if os.path.isfile(item.path):
            try:
                if is_video_file(item.path):
                    self.preview.set_input_video(item.path)
                else:
                    img = Image.open(item.path)
                    self.preview.set_input_image(img)
            except Exception:
                self.preview.clear()

        # If completed, also load output
        if item.status == ItemStatus.COMPLETED and item.output_path:
            if os.path.isfile(item.output_path):
                try:
                    if is_video_file(item.output_path):
                        self.preview.set_output_video(item.output_path)
                    else:
                        out_img = Image.open(item.output_path)
                        self.preview.set_output_image(out_img)
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
            "tile_pad": "tile_pad",
            "pre_pad": "pre_pad",
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
        self.bind("<Control-Shift-O>", lambda e: self._open_output_folder())
        self.bind("<Control-Shift-o>", lambda e: self._open_output_folder())
        self.bind("<Control-p>", self._on_process_all_shortcut)
        self.bind("<Control-P>", self._on_process_all_shortcut)
        self.bind("<Control-Return>", self._on_process_all_shortcut)
        self.bind("<Return>", self._on_return_key)
        self.bind("<Escape>", lambda e: self.upscale_ctrl.cancel())
        self.bind("<Delete>", lambda e: self._delete_selected())
        self.bind("<Control-q>", lambda e: self._on_close())
        self.bind("<F1>", lambda e: self.toolbar._show_about())
        self.bind("<F11>", lambda e: self._toggle_fullscreen())

    def _on_return_key(self, event) -> None:
        """Handle Return key - ignore if focus is in a text entry."""
        widget = self.focus_get()
        if widget and widget.winfo_class() in ("Entry", "TEntry", "Text"):
            return  # Don't trigger upscale when typing in an entry
        self._start_upscale()

    def _on_process_all_shortcut(self, event=None) -> None:
        """Handle Process All shortcut key - ignore if focus is in a text entry."""
        widget = self.focus_get()
        if widget and widget.winfo_class() in ("Entry", "TEntry", "Text"):
            return  # Don't trigger batch upscale when typing in an entry
        self._process_all()

    def _on_queue_cleared(self) -> None:
        """Handle queue becoming empty."""
        self.preview.clear()
        self._show_drop_zone()
        self.toolbar.set_save_enabled(False)
        self._status_text.configure(text="Ready")

    def _delete_selected(self) -> None:
        idx = self.queue_panel.get_selected_index()
        if idx >= 0:
            self.queue_panel.remove(idx)

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
                # Position is off-screen - center on primary monitor
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
            # Not on Windows or ctypes unavailable - trust the saved position
            return True

    def _save_geometry(self) -> None:
        try:
            geo = self.geometry()
            # Format: WxH+X+Y or WxH+-X+Y (negative coords on multi-monitor)
            match = re.match(r'(\d+)x(\d+)\+(-?\d+)\+(-?\d+)', geo)
            if match:
                w, h, x, y = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
                self.config_store.update({
                    "window_width": w,
                    "window_height": h,
                    "window_x": x,
                    "window_y": y,
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

        if hasattr(self, "_status_tooltip") and self._status_tooltip:
            try:
                self._status_tooltip.destroy()
            except Exception:
                pass
        if hasattr(self, "_gpu_tooltip") and self._gpu_tooltip:
            try:
                self._gpu_tooltip.destroy()
            except Exception:
                pass

        self.destroy()

    def destroy(self) -> None:
        """Cleanly cancel timers and destroy window."""
        if hasattr(self, "_poll_id") and self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except Exception:
                pass
            self._poll_id = None
        super().destroy()

    def _update_gpu_info(self) -> None:
        """Refresh GPU VRAM usage in the status bar."""
        gpu = self.upscale_ctrl.get_gpu_info()
        if gpu["total_vram_gb"] > 0:
            text = f"{gpu['name']} - VRAM: {gpu['used_vram_gb']}/{gpu['total_vram_gb']} GB"
        else:
            text = gpu["name"]
        self._gpu_label.configure(text=text)

    # ================================================================== #
    #  Public properties and query helpers                                #
    # ================================================================== #

    @property
    def status_label(self) -> ctk.CTkLabel:
        """The left-aligned status text label in the status bar."""
        return self._status_text

    @property
    def gpu_label(self) -> ctk.CTkLabel:
        """The right-aligned GPU info label in the status bar."""
        return self._gpu_label

    @property
    def status_tooltip(self) -> Optional[ToolTip]:
        """The tooltip attached to the status text label."""
        return getattr(self, "_status_tooltip", None)

    @property
    def gpu_tooltip(self) -> Optional[ToolTip]:
        """The tooltip attached to the GPU info label."""
        return getattr(self, "_gpu_tooltip", None)

    def status_message(self) -> str:
        """Return the current message displayed in the status bar."""
        return self._status_text.cget("text")

    def gpu_info_text(self) -> str:
        """Return the current text displayed in the GPU info label."""
        return self._gpu_label.cget("text")

    def is_batch_mode(self) -> bool:
        """Check whether batch processing mode is active."""
        return bool(self._is_batch)

    def is_upscaling(self) -> bool:
        """Check whether upscaling controller is currently busy."""
        return bool(self.upscale_ctrl.is_busy)

    def queue_count(self) -> int:
        """Return the number of items currently in the queue."""
        return self.queue_panel.item_count()

    def has_queue_items(self) -> bool:
        """Check whether there are any items in the queue."""
        return not self.queue_panel.is_empty()

    @property
    def upscale_button(self) -> ctk.CTkButton:
        """The main Upscale button in the settings panel."""
        return self._upscale_btn

    @property
    def toolbar_widget(self) -> Toolbar:
        """The top toolbar widget."""
        return self.toolbar

    @property
    def queue_widget(self) -> QueuePanel:
        """The queue panel widget."""
        return self.queue_panel

    @property
    def settings_widget(self) -> SettingsPanel:
        """The settings panel widget."""
        return self.settings_panel

    @property
    def preview_widget(self) -> PreviewCanvas:
        """The central preview canvas widget."""
        return self.preview

    @property
    def progress_widget(self) -> ProgressPanel:
        """The progress bar panel widget."""
        return self.progress

    @property
    def drop_zone_widget(self) -> DropZone:
        """The drop zone overlay widget."""
        return self.drop_zone

    def is_drop_zone_visible(self) -> bool:
        """Check whether the drop zone overlay is currently placed."""
        return bool(self.drop_zone.place_info())

    def selected_queue_item(self) -> Optional[Any]:
        """Return the currently selected queue item, if any."""
        return self.queue_panel.get_selected()

    def selected_queue_index(self) -> int:
        """Return the index of the currently selected queue item, or -1."""
        return self.queue_panel.get_selected_index()

    def can_start_upscale(self) -> bool:
        """Check whether an upscale operation can currently be started."""
        return (self.queue_panel.get_selected() is not None) and (not self.upscale_ctrl.is_busy)

    def selected_model(self) -> str:
        """Return the display name of the currently selected model."""
        return self.settings_panel.current_model()

    def selected_category(self) -> str:
        """Return the currently selected model category name."""
        return self.settings_panel.current_category()

    def selected_scale(self) -> float:
        """Return the currently configured upscaling multiplier."""
        return self.settings_panel.current_scale()

    def output_directory(self) -> str:
        """Return the configured target output directory path."""
        return str(self.settings_panel.get_settings().get("output_folder", ""))

    def is_face_enhance_enabled(self) -> bool:
        """Return True if face enhancement is enabled in settings."""
        return self.settings_panel.is_face_enhance_enabled()

    def is_denoise_enabled(self) -> bool:
        """Return True if denoising is enabled in settings."""
        return self.settings_panel.is_denoise_enabled()

    def denoise_strength(self) -> float:
        """Return the currently configured denoising strength (0.0 to 1.0)."""
        return self.settings_panel.denoise_strength()

    def output_extension(self) -> str:
        """Return the currently selected output image extension (e.g. 'png')."""
        return self.settings_panel.output_extension()

    def is_fullscreen(self) -> bool:
        """Check whether the application is currently in fullscreen mode."""
        try:
            return bool(self.attributes("-fullscreen"))
        except Exception:
            return False

    def trigger_toggle_fullscreen(self) -> bool:
        """Toggle fullscreen mode and return the new fullscreen state."""
        self._toggle_fullscreen()
        return self.is_fullscreen()

    def trigger_delete_selected(self) -> bool:
        """Delete the currently selected queue item if one is selected."""
        if self.selected_queue_item() is not None:
            self._delete_selected()
            return True
        return False

    def trigger_clear_queue(self) -> bool:
        """Clear all items from the queue if not currently busy."""
        if self.has_queue_items() and not self.is_upscaling():
            self.queue_panel.clear()
            return True
        return False

    def trigger_upscale(self) -> bool:
        """Trigger upscaling for the selected item if possible."""
        if self.can_start_upscale():
            self._start_upscale()
            return True
        return False

    def trigger_process_all(self) -> bool:
        """Trigger batch processing for all queue items if possible."""
        if self.has_queue_items() and not self.is_upscaling():
            self._process_all()
            return True
        return False
    def select_model(self, name: str) -> None:
        """Programmatically select upscaling model."""
        self.settings_panel.select_model(name)

    def select_category(self, cat: str) -> None:
        """Programmatically select model category."""
        self.settings_panel.select_category(cat)

    def select_scale(self, scale: float | str) -> None:
        """Programmatically select scaling factor."""
        self.settings_panel.select_scale(scale)

    def set_face_enhance(self, enabled: bool) -> None:
        """Programmatically toggle face enhancement."""
        self.settings_panel.set_face_enhance(enabled)

    def set_denoise_strength(self, val: float) -> None:
        """Programmatically set denoise strength."""
        self.settings_panel.set_denoise_strength(val)

    def select_output_extension(self, ext: str) -> None:
        """Programmatically select output extension."""
        self.settings_panel.select_extension(ext)

    def trigger_reset_settings(self) -> None:
        """Programmatically reset settings to defaults."""
        self.settings_panel.trigger_reset_defaults()

    def trigger_preview_zoom_in(self) -> None:
        """Trigger preview canvas zoom in."""
        self.preview.trigger_zoom_in()

    def trigger_preview_zoom_out(self) -> None:
        """Trigger preview canvas zoom out."""
        self.preview.trigger_zoom_out()

    def trigger_preview_zoom_fit(self) -> None:
        """Trigger preview canvas fit/reset zoom."""
        self.preview.trigger_zoom_fit()

    def preview_zoom_percent_text(self) -> str:
        """Return preview zoom percentage label text."""
        return self.preview.zoom_percent_text()

    def preview_has_input(self) -> bool:
        """Return True if preview canvas has input image/video."""
        return self.preview.has_input()

    def preview_has_output(self) -> bool:
        """Return True if preview canvas has output image/video."""
        return self.preview.has_output()

    def preview_slider_position(self) -> float:
        """Return preview before/after slider position."""
        return self.preview.slider_position()

    def set_preview_slider_position(self, pos: float) -> None:
        """Set preview before/after slider position."""
        self.preview.set_slider_position(pos)

    def progress_percent(self) -> float:
        """Return current operation completion percentage (0.0 to 100.0)."""
        return self.progress.current_percent()

    def progress_status_text(self) -> str:
        """Return current progress status label text."""
        return self.progress.status_text()

    def progress_eta_text(self) -> str:
        """Return current ETA label text."""
        return self.progress.eta_text()

    def progress_percent_text(self) -> str:
        """Return current completion percentage label text."""
        return self.progress.percent_text()

    def is_progress_active(self) -> bool:
        """Return True if an upscale progress tracking operation is active."""
        return self.progress.is_active()

    def trigger_cancel_progress(self) -> bool:
        """Programmatically request cancellation of current upscale operation."""
        if self.upscale_ctrl.is_busy:
            self.upscale_ctrl.cancel()
            self.progress.trigger_cancel()
            return True
        return False


    def trigger_open(self) -> None:
        """Trigger toolbar Open files action."""
        self.toolbar.trigger_open()

    def trigger_save(self) -> bool:
        """Trigger toolbar Save As action if available."""
        return self.toolbar.trigger_save()

    def trigger_open_output_folder(self) -> None:
        """Trigger toolbar Open Output Folder action."""
        self.toolbar.trigger_output_folder()

    def trigger_show_about(self) -> None:
        """Trigger toolbar About dialog."""
        self.toolbar.trigger_about()

    def trigger_close_about(self) -> bool:
        """Close About dialog if open, returning True if closed."""
        if self.toolbar.is_about_open():
            self.toolbar.close_about()
            return True
        return False

    def is_about_dialog_open(self) -> bool:
        """Return True if About dialog window is currently open."""
        return self.toolbar.is_about_open()

    def is_save_enabled(self) -> bool:
        """Return True if Save As toolbar action is enabled."""
        return self.toolbar.is_save_enabled()

    def set_save_enabled(self, enabled: bool) -> None:
        """Enable or disable Save As toolbar action."""
        self.toolbar.set_save_enabled(enabled)

    def trigger_drop_files(self, paths: List[str]) -> bool:
        """Simulate dropping files onto the application drop zone."""
        return self.drop_zone.trigger_drop_files(paths)

    def queue_item_paths(self) -> List[str]:
        """Return list of file paths in the processing queue."""
        return self.queue_panel.item_paths()

    def queue_item_filenames(self) -> List[str]:
        """Return list of file names in the processing queue."""
        return self.queue_panel.item_filenames()

    def queue_count_text(self) -> str:
        """Return the formatted count label text of the queue."""
        return self.queue_panel.count_text()

    def trigger_select_queue_index(self, idx: int) -> bool:
        """Programmatically select item at queue index."""
        return self.queue_panel.trigger_select(idx)

    def trigger_remove_queue_index(self, idx: int) -> bool:
        """Programmatically remove item at queue index."""
        return self.queue_panel.trigger_remove(idx)

    def trigger_move_queue_item_up(self, idx: int) -> bool:
        """Programmatically move item at queue index one position up."""
        return self.queue_panel.trigger_move_up(idx)

    def trigger_move_queue_item_down(self, idx: int) -> bool:
        """Programmatically move item at queue index one position down."""
        return self.queue_panel.trigger_move_down(idx)
