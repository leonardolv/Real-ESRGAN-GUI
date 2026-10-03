"""Settings panel — right-hand sidebar with all upscaling controls.

Organized into four collapsible sections: Model, Upscaling, Enhancement,
and Output.  Controls are wired to a shared settings dictionary that the
main app reads when submitting jobs.
"""

import os
from pathlib import Path
import sys
from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from gui.controllers.model_manager import ModelInfo, ModelManager
from gui.widgets.tooltip import ToolTip


class SettingsPanel(ctk.CTkScrollableFrame):
    """Right-hand settings sidebar.

    Parameters
    ----------
    master : widget
        Parent widget.
    model_manager : ModelManager
        For model listing and metadata.
    on_settings_changed : callable
        ``(key, value) -> None`` called whenever a setting changes.
    """

    def __init__(
        self,
        master,
        model_manager: ModelManager,
        on_settings_changed: Optional[Callable[[str, Any], None]] = None,
        **kwargs,
    ):
        super().__init__(master, width=280, **kwargs)
        self._mm = model_manager
        self._on_changed = on_settings_changed

        # Internal state
        self._vars: Dict[str, Any] = {}
        self._tooltips: List[ToolTip] = []

        self._build_model_section()
        self._build_upscaling_section()
        self._build_enhancement_section()
        self._build_output_section()

        # Update initial model info state after all sections are built
        self._update_model_info()

    # ================================================================== #
    #  Section 1: Model                                                   #
    # ================================================================== #

    def _build_model_section(self) -> None:
        self._section_label("Model")

        # Category radio buttons
        ctk.CTkLabel(self, text="Category", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._category_var = ctk.StringVar(value="General")
        cat_frame = ctk.CTkFrame(self, fg_color="transparent")
        cat_frame.pack(fill="x", padx=16, pady=(2, 4))
        for cat in self._mm.categories():
            rb = ctk.CTkRadioButton(
                cat_frame,
                text=cat,
                variable=self._category_var,
                value=cat,
                command=self._on_category_changed,
            )
            rb.pack(anchor="w", pady=1)
            self._add_tooltip(rb, f"Filter models by '{cat}' category")

        # Model dropdown
        ctk.CTkLabel(self, text="Model", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._model_var = ctk.StringVar(value="RealESRGAN_x4plus")
        self._model_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self._model_var,
            values=self._get_model_names("General"),
            command=self._on_model_changed,
            width=248,
        )
        self._model_dropdown.pack(padx=16, pady=(2, 4))
        self._add_tooltip(self._model_dropdown, "Select upscaling model architecture")

        # Description label
        self._model_desc = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
            wraplength=240,
            justify="left",
        )
        self._model_desc.pack(anchor="w", padx=16, pady=(0, 4))

        # Download status
        self._model_status = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            justify="left",
        )
        self._model_status.pack(anchor="w", padx=16, pady=(0, 4))

        self._download_btn = ctk.CTkButton(
            self,
            text="Download Model",
            height=28,
            font=ctk.CTkFont(size=12),
            cursor="hand2",
            command=self._on_download_model,
        )
        # Only shown when model is missing — initially hidden
        self._download_btn.pack(padx=16, pady=(0, 8))
        self._download_btn.pack_forget()
        self._add_tooltip(self._download_btn, "Download model weights from official repository")

    # ================================================================== #
    #  Section 2: Upscaling                                               #
    # ================================================================== #

    def _build_upscaling_section(self) -> None:
        self._section_label("Upscaling")

        # Output scale
        ctk.CTkLabel(self, text="Output Scale", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._scale_var = ctk.StringVar(value="4")
        self._scale_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self._scale_var,
            values=["1", "2", "3", "4"],
            command=lambda v: self._emit("outscale", float(v)),
            width=248,
        )
        self._scale_dropdown.pack(padx=16, pady=(2, 4))
        self._add_tooltip(self._scale_dropdown, "Output image scaling multiplier (1x to 4x)")

        # Tile size
        ctk.CTkLabel(self, text="Tile Size", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._tile_var = ctk.StringVar(value="256")
        self._tile_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self._tile_var,
            values=["0 (no tile)", "128", "256", "512", "1024"],
            command=self._on_tile_changed,
            width=248,
        )
        self._tile_dropdown.pack(padx=16, pady=(2, 2))
        self._add_tooltip(self._tile_dropdown, "Tile dimension to conserve GPU VRAM (0 for un-tiled)")
        ctk.CTkLabel(
            self,
            text="Use tiles if you run out of VRAM",
            font=ctk.CTkFont(size=10),
            text_color="#a0a0a0",
        ).pack(anchor="w", padx=16, pady=(0, 4))

        # Tile padding
        ctk.CTkLabel(self, text="Tile Padding", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._tile_pad_var = ctk.StringVar(value="10")
        tile_pad_entry = ctk.CTkEntry(
            self, textvariable=self._tile_pad_var, width=248, height=28
        )
        tile_pad_entry.pack(padx=16, pady=(2, 4))
        tile_pad_entry.bind("<FocusOut>", lambda e: self._emit_int("tile_pad", self._tile_pad_var, 10))
        tile_pad_entry.bind("<Return>", lambda e: self._emit_int("tile_pad", self._tile_pad_var, 10))
        self._add_tooltip(tile_pad_entry, "Overlap border padding in pixels between tiles")

        # Pre padding
        ctk.CTkLabel(self, text="Pre Padding", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._pre_pad_var = ctk.StringVar(value="0")
        pre_pad_entry = ctk.CTkEntry(
            self, textvariable=self._pre_pad_var, width=248, height=28
        )
        pre_pad_entry.pack(padx=16, pady=(2, 8))
        pre_pad_entry.bind("<FocusOut>", lambda e: self._emit_int("pre_pad", self._pre_pad_var, 0))
        pre_pad_entry.bind("<Return>", lambda e: self._emit_int("pre_pad", self._pre_pad_var, 0))
        self._add_tooltip(pre_pad_entry, "Pre-padding pixels to reduce edge boundary artifacts")

    # ================================================================== #
    #  Section 3: Enhancement                                             #
    # ================================================================== #

    def _build_enhancement_section(self) -> None:
        self._section_label("Enhancement")

        # Face enhance
        self._face_var = ctk.BooleanVar(value=False)
        self._face_check = ctk.CTkCheckBox(
            self,
            text="Face Enhancement (GFPGAN)",
            variable=self._face_var,
            command=lambda: self._emit("face_enhance", self._face_var.get()),
        )
        self._face_check.pack(anchor="w", padx=16, pady=(4, 2))
        self._add_tooltip(self._face_check, "Face restoration using GFPGAN (recommended for portraits only)")
        self._face_hint = ctk.CTkLabel(
            self,
            text="Restores and enhances faces. Not for anime.",
            font=ctk.CTkFont(size=10),
            text_color="#a0a0a0",
            wraplength=240,
            justify="left",
        )
        self._face_hint.pack(anchor="w", padx=32, pady=(0, 4))

        # Denoise strength slider — wrapped in a container so show/hide
        # doesn't break pack ordering when toggling models.
        self._denoise_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._denoise_frame.pack(fill="x")

        self._denoise_label = ctk.CTkLabel(
            self._denoise_frame, text="Denoise Strength", font=ctk.CTkFont(size=12)
        )
        self._denoise_label.pack(anchor="w", padx=16, pady=(4, 0))
        self._denoise_var = ctk.DoubleVar(value=0.5)
        self._denoise_slider = ctk.CTkSlider(
            self._denoise_frame,
            from_=0,
            to=1,
            number_of_steps=20,
            variable=self._denoise_var,
            command=lambda v: self._emit("denoise_strength", round(float(v), 2)),
            width=248,
        )
        self._denoise_slider.pack(padx=16, pady=(2, 0))
        self._add_tooltip(self._denoise_slider, "Noise reduction strength for general-v3 model")
        self._denoise_value_label = ctk.CTkLabel(
            self._denoise_frame, text="0.50", font=ctk.CTkFont(size=11), text_color=("gray50", "gray60")
        )
        self._denoise_value_label.pack(anchor="w", padx=16, pady=(0, 2))
        self._denoise_var.trace_add("write", self._on_denoise_changed)
        self._denoise_hint = ctk.CTkLabel(
            self._denoise_frame,
            text="Only for General v3 model. 0=keep noise, 1=strong denoise.",
            font=ctk.CTkFont(size=10),
            text_color="#a0a0a0",
            wraplength=240,
            justify="left",
        )
        self._denoise_hint.pack(anchor="w", padx=16, pady=(0, 4))

        # FP32 precision
        self._fp32_var = ctk.BooleanVar(value=False)
        self._fp32_check = ctk.CTkCheckBox(
            self,
            text="FP32 Precision",
            variable=self._fp32_var,
            command=lambda: self._emit("fp32", self._fp32_var.get()),
        )
        self._fp32_check.pack(anchor="w", padx=16, pady=(4, 2))
        self._add_tooltip(self._fp32_check, "Force FP32 precision to avoid black or NaN outputs on older GPUs")
        ctk.CTkLabel(
            self,
            text="Use if you get NaN errors on older GPUs.",
            font=ctk.CTkFont(size=10),
            text_color="#a0a0a0",
            wraplength=240,
            justify="left",
        ).pack(anchor="w", padx=32, pady=(0, 4))

        # Alpha upsampler
        ctk.CTkLabel(self, text="Alpha Channel", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._alpha_var = ctk.StringVar(value="realesrgan")
        self._alpha_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self._alpha_var,
            values=["realesrgan", "bicubic"],
            command=lambda v: self._emit("alpha_upsampler", v),
            width=248,
        )
        self._alpha_dropdown.pack(padx=16, pady=(2, 8))
        self._add_tooltip(self._alpha_dropdown, "Upsampling technique for transparency / alpha channels")

    # ================================================================== #
    #  Section 4: Output                                                  #
    # ================================================================== #

    def _build_output_section(self) -> None:
        self._section_label("Output")

        # Format
        ctk.CTkLabel(self, text="Format", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._ext_var = ctk.StringVar(value="auto")
        self._ext_dropdown = ctk.CTkOptionMenu(
            self,
            variable=self._ext_var,
            values=["auto", "png", "jpg", "webp"],
            command=lambda v: self._emit("output_ext", v),
            width=248,
        )
        self._ext_dropdown.pack(padx=16, pady=(2, 4))
        self._add_tooltip(self._ext_dropdown, "Output image container format")

        # Suffix
        ctk.CTkLabel(self, text="Suffix", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._suffix_var = ctk.StringVar(value="out")
        suffix_entry = ctk.CTkEntry(
            self, textvariable=self._suffix_var, width=248, height=28,
            placeholder_text="e.g. out, upscaled, 4x"
        )
        suffix_entry.pack(padx=16, pady=(2, 4))
        suffix_entry.bind("<FocusOut>", lambda e: self._emit("suffix", self._suffix_var.get()))
        suffix_entry.bind("<Return>", lambda e: self._emit("suffix", self._suffix_var.get()))
        self._add_tooltip(suffix_entry, "Suffix appended to upscaled filenames")

        # Output folder
        ctk.CTkLabel(self, text="Output Folder", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(fill="x", padx=16, pady=(2, 8))
        self._output_dir_var = ctk.StringVar(value="results")
        output_dir_entry = ctk.CTkEntry(
            folder_frame,
            textvariable=self._output_dir_var,
            height=28,
        )
        output_dir_entry.pack(side="left", fill="x", expand=True)
        output_dir_entry.bind("<FocusOut>", lambda e: self._emit("output_folder", self._output_dir_var.get()))
        output_dir_entry.bind("<Return>", lambda e: self._emit("output_folder", self._output_dir_var.get()))
        self._add_tooltip(output_dir_entry, "Destination directory for generated files")

        self._open_folder_btn = ctk.CTkButton(
            folder_frame,
            text="↗",
            width=36,
            height=28,
            cursor="hand2",
            command=self._open_output_folder_in_os,
        )
        self._open_folder_btn.pack(side="right", padx=(2, 0))
        self._add_tooltip(self._open_folder_btn, "Open output folder in system file manager")

        self._browse_btn = ctk.CTkButton(
            folder_frame,
            text="📂",
            width=36,
            height=28,
            cursor="hand2",
            command=self._browse_output_folder,
        )
        self._browse_btn.pack(side="right", padx=(4, 0))
        self._add_tooltip(self._browse_btn, "Browse filesystem for destination folder")

    # ================================================================== #
    #  Big Upscale Button                                                 #
    # ================================================================== #

    def add_upscale_button(self, command: Callable) -> ctk.CTkButton:
        """Add the primary action button at the bottom. Returns the button
        so the parent can control its state."""
        self._reset_btn = ctk.CTkButton(
            self,
            text="↺  Reset to Defaults",
            height=28,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#a0a0a0",
            cursor="hand2",
            command=self.reset_to_defaults,
        )
        self._reset_btn.pack(fill="x", padx=16, pady=(12, 4))
        self._add_tooltip(self._reset_btn, "Reset all model and upscaling configurations to factory defaults")

        self._upscale_btn = ctk.CTkButton(
            self,
            text="▶  UPSCALE",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=48,
            corner_radius=10,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            cursor="hand2",
            command=command,
        )
        self._upscale_btn.pack(fill="x", padx=16, pady=(4, 16))
        self._add_tooltip(self._upscale_btn, "Execute Real-ESRGAN super-resolution upscaling on queued files")
        return self._upscale_btn

    # ================================================================== #
    #  Public API                                                         #
    # ================================================================== #

    def get_settings(self) -> Dict[str, Any]:
        """Return the current settings as a dictionary."""
        tile_str = self._tile_var.get()
        try:
            tile = int(tile_str.split()[0]) if tile_str else 0
        except (ValueError, IndexError):
            tile = 0

        try:
            tile_pad = int(self._tile_pad_var.get() or 10)
        except ValueError:
            tile_pad = 10

        try:
            pre_pad = int(self._pre_pad_var.get() or 0)
        except ValueError:
            pre_pad = 0

        try:
            outscale = float(self._scale_var.get())
        except ValueError:
            outscale = 4.0

        return {
            "model_name": self._model_var.get(),
            "outscale": outscale,
            "tile": tile,
            "tile_pad": tile_pad,
            "pre_pad": pre_pad,
            "face_enhance": self._face_var.get(),
            "fp32": self._fp32_var.get(),
            "denoise_strength": round(self._denoise_var.get(), 2),
            "alpha_upsampler": self._alpha_var.get(),
            "output_ext": self._ext_var.get(),
            "suffix": self._suffix_var.get(),
            "output_folder": self._output_dir_var.get(),
        }

    def load_settings(self, settings: Dict[str, Any]) -> None:
        """Restore settings from a config dict."""
        if "last_model" in settings:
            self._model_var.set(settings["last_model"])
        if "last_scale" in settings:
            self._scale_var.set(str(int(settings["last_scale"])))
        if "last_tile" in settings:
            tile = int(settings["last_tile"])
            self._tile_var.set(f"{tile} (no tile)" if tile == 0 else str(tile))
        if "face_enhance" in settings:
            self._face_var.set(settings["face_enhance"])
        if "fp32" in settings:
            self._fp32_var.set(settings["fp32"])
        if "denoise_strength" in settings:
            self._denoise_var.set(settings["denoise_strength"])
        if "output_format" in settings:
            self._ext_var.set(settings["output_format"])
        if "output_suffix" in settings:
            self._suffix_var.set(settings["output_suffix"])
        if "tile_pad" in settings:
            self._tile_pad_var.set(str(int(settings["tile_pad"])))
        if "pre_pad" in settings:
            self._pre_pad_var.set(str(int(settings["pre_pad"])))
        if "output_folder" in settings:
            self._output_dir_var.set(settings["output_folder"])

    def set_upscale_button_state(self, enabled: bool) -> None:
        """Enable or disable the upscale button."""
        if hasattr(self, "_upscale_btn"):
            self._upscale_btn.configure(state="normal" if enabled else "disabled")

    # ================================================================== #
    #  Internal callbacks                                                 #
    # ================================================================== #

    def _on_category_changed(self) -> None:
        cat = self._category_var.get()
        names = self._get_model_names(cat)
        self._model_dropdown.configure(values=names)
        if names:
            self._model_var.set(names[0])
            # Resolve display name → internal name
            self._on_model_changed(names[0])

    def _on_model_changed(self, display_name: str) -> None:
        # Find internal name from display name
        for m in self._mm.list_all():
            if m.display_name == display_name:
                self._model_var.set(m.name)
                break
        self._update_model_info()
        self._emit("model_name", self._model_var.get())

    def _on_tile_changed(self, value: str) -> None:
        tile = int(value.split()[0]) if value else 0
        self._emit("tile", tile)

    def _on_denoise_changed(self, *args) -> None:
        val = round(self._denoise_var.get(), 2)
        self._denoise_value_label.configure(text=f"{val:.2f}")

    def _on_download_model(self) -> None:
        name = self._model_var.get()
        self._model_status.configure(text="⏳ Downloading…")
        self._download_btn.configure(state="disabled")
        # Run download in a thread to avoid blocking UI
        import threading
        def _dl():
            try:
                self._mm.download_model(name)
                self.after(0, self._update_model_info)
            except Exception as e:
                self.after(0, lambda: self._model_status.configure(text=f"❌ {e}"))
        threading.Thread(target=_dl, daemon=True).start()

    def _browse_output_folder(self) -> None:
        import tkinter.filedialog as fd
        folder = fd.askdirectory(title="Select output folder")
        if folder:
            self._output_dir_var.set(folder)
            self._emit("output_folder", folder)

    def _open_output_folder_in_os(self) -> None:
        """Open the current output folder in the OS file explorer."""
        folder = self._output_dir_var.get().strip()
        if not folder:
            folder = "results"
        folder_path = Path(folder)
        try:
            folder_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        # Headless testing guard: do not spawn OS processes/explorers during automated runs
        if "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("QT_QPA_PLATFORM") == "offscreen":
            return

        try:
            if sys.platform == "win32":
                os.startfile(str(folder_path.resolve()))
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", str(folder_path.resolve())])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(folder_path.resolve())])
        except Exception:
            pass

    # ================================================================== #
    #  Helpers                                                            #
    # ================================================================== #

    def _update_model_info(self) -> None:
        """Refresh description and download status for the selected model."""
        name = self._model_var.get()
        info = self._mm.get(name)
        if info is None:
            return

        self._model_desc.configure(text=info.description)

        if info.downloaded:
            self._model_status.configure(text="● Downloaded ✓", text_color="#4ade80")
            self._download_btn.pack_forget()
        else:
            self._model_status.configure(text="○ Not downloaded", text_color="#fb923c")
            self._download_btn.pack(padx=16, pady=(0, 8))
            self._download_btn.configure(state="normal")

        # Conditional visibility: denoise slider only for general-v3.
        # Uses a container frame so show/hide doesn't break pack ordering.
        is_v3 = name == "realesr-general-x4v3"
        if is_v3:
            self._denoise_frame.pack(fill="x")
        else:
            self._denoise_frame.pack_forget()

        # Disable face enhance for anime models
        is_anime = "anime" in name.lower()
        if is_anime:
            self._face_var.set(False)
            self._face_check.configure(state="disabled")
            self._face_hint.configure(text="Not available for anime models.")
        else:
            self._face_check.configure(state="normal")
            self._face_hint.configure(text="Restores and enhances faces. Not for anime.")

    def _get_model_names(self, category: str) -> List[str]:
        """Return display names for models in a category."""
        return [m.display_name for m in self._mm.list_by_category(category)]

    def _section_label(self, text: str) -> None:
        """Add a section header."""
        ctk.CTkLabel(
            self,
            text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).pack(anchor="w", padx=12, pady=(12, 2))
        # Separator line
        sep = ctk.CTkFrame(self, height=1, fg_color="#333333")
        sep.pack(fill="x", padx=12, pady=(0, 4))

    def _emit(self, key: str, value: Any) -> None:
        if self._on_changed:
            self._on_changed(key, value)

    def _emit_int(self, key: str, var: ctk.StringVar, fallback: int) -> None:
        """Parse an int from a StringVar and emit, using fallback on error."""
        try:
            val = int(var.get() or fallback)
        except ValueError:
            val = fallback
        self._emit(key, val)

    def reset_to_defaults(self) -> None:
        """Reset all parameters to factory defaults and notify listeners."""
        self._category_var.set("General")
        self._on_category_changed()

        default_model = "RealESRGAN_x4plus"
        info = self._mm.get(default_model)
        disp = info.display_name if info else default_model
        self._model_var.set(default_model)
        self._on_model_changed(disp)

        self._scale_var.set("4")
        self._emit("outscale", 4.0)

        self._tile_var.set("0 (no tile)")
        self._emit("tile", 0)

        self._tile_pad_var.set("10")
        self._emit("tile_pad", 10)

        self._pre_pad_var.set("0")
        self._emit("pre_pad", 0)

        self._face_var.set(False)
        self._emit("face_enhance", False)

        self._fp32_var.set(False)
        self._emit("fp32", False)

        self._denoise_var.set(0.5)
        self._emit("denoise_strength", 0.5)

        self._alpha_var.set("realesrgan")
        self._emit("alpha_upsampler", "realesrgan")

        self._ext_var.set("auto")
        self._emit("output_ext", "auto")

        self._suffix_var.set("out")
        self._emit("suffix", "out")

        self._output_dir_var.set("results")
        self._emit("output_folder", "results")

    def _add_tooltip(self, widget: Any, text: str) -> Optional[ToolTip]:
        try:
            tip = ToolTip(widget, text=text, delay_ms=300)
            self._tooltips.append(tip)
            return tip
        except Exception:
            return None

    def destroy(self) -> None:
        for tip in self._tooltips:
            try:
                tip.destroy()
            except Exception:
                pass
        self._tooltips.clear()
        super().destroy()
