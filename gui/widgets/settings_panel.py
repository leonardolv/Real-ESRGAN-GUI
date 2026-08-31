"""Settings panel — right-hand sidebar with all upscaling controls.

Organized into four collapsible sections: Model, Upscaling, Enhancement,
and Output.  Controls are wired to a shared settings dictionary that the
main app reads when submitting jobs.
"""

from typing import Any, Callable, Dict, List, Optional

import customtkinter as ctk

from gui.controllers.model_manager import ModelInfo, ModelManager


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
            ctk.CTkRadioButton(
                cat_frame,
                text=cat,
                variable=self._category_var,
                value=cat,
                command=self._on_category_changed,
            ).pack(anchor="w", pady=1)

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
            command=self._on_download_model,
        )
        # Only shown when model is missing — initially hidden
        self._download_btn.pack(padx=16, pady=(0, 8))
        self._download_btn.pack_forget()

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
        ctk.CTkEntry(
            self, textvariable=self._tile_pad_var, width=248, height=28
        ).pack(padx=16, pady=(2, 4))

        # Pre padding
        ctk.CTkLabel(self, text="Pre Padding", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._pre_pad_var = ctk.StringVar(value="0")
        ctk.CTkEntry(
            self, textvariable=self._pre_pad_var, width=248, height=28
        ).pack(padx=16, pady=(2, 8))

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
        self._face_hint = ctk.CTkLabel(
            self,
            text="Restores and enhances faces. Not for anime.",
            font=ctk.CTkFont(size=10),
            text_color="#a0a0a0",
            wraplength=240,
            justify="left",
        )
        self._face_hint.pack(anchor="w", padx=32, pady=(0, 4))

        # Denoise strength slider
        self._denoise_label = ctk.CTkLabel(
            self, text="Denoise Strength", font=ctk.CTkFont(size=12)
        )
        self._denoise_label.pack(anchor="w", padx=16, pady=(4, 0))
        self._denoise_var = ctk.DoubleVar(value=0.5)
        self._denoise_slider = ctk.CTkSlider(
            self,
            from_=0,
            to=1,
            number_of_steps=20,
            variable=self._denoise_var,
            command=lambda v: self._emit("denoise_strength", round(float(v), 2)),
            width=248,
        )
        self._denoise_slider.pack(padx=16, pady=(2, 0))
        self._denoise_value_label = ctk.CTkLabel(
            self, text="0.50", font=ctk.CTkFont(size=11), text_color=("gray50", "gray60")
        )
        self._denoise_value_label.pack(anchor="w", padx=16, pady=(0, 2))
        self._denoise_var.trace_add("write", self._on_denoise_changed)
        self._denoise_hint = ctk.CTkLabel(
            self,
            text="Only for General v3 model. 0=keep noise, 1=strong denoise.",
            font=ctk.CTkFont(size=10),
            text_color="#a0a0a0",
            wraplength=240,
            justify="left",
        )
        self._denoise_hint.pack(anchor="w", padx=16, pady=(0, 4))

        # FP32 precision
        self._fp32_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            self,
            text="FP32 Precision",
            variable=self._fp32_var,
            command=lambda: self._emit("fp32", self._fp32_var.get()),
        ).pack(anchor="w", padx=16, pady=(4, 2))
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
        ctk.CTkOptionMenu(
            self,
            variable=self._alpha_var,
            values=["realesrgan", "bicubic"],
            command=lambda v: self._emit("alpha_upsampler", v),
            width=248,
        ).pack(padx=16, pady=(2, 8))

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
        ctk.CTkOptionMenu(
            self,
            variable=self._ext_var,
            values=["auto", "png", "jpg", "webp"],
            command=lambda v: self._emit("output_ext", v),
            width=248,
        ).pack(padx=16, pady=(2, 4))

        # Suffix
        ctk.CTkLabel(self, text="Suffix", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        self._suffix_var = ctk.StringVar(value="out")
        ctk.CTkEntry(
            self, textvariable=self._suffix_var, width=248, height=28,
            placeholder_text="e.g. out, upscaled, 4x"
        ).pack(padx=16, pady=(2, 4))

        # Output folder
        ctk.CTkLabel(self, text="Output Folder", font=ctk.CTkFont(size=12)).pack(
            anchor="w", padx=16, pady=(4, 0)
        )
        folder_frame = ctk.CTkFrame(self, fg_color="transparent")
        folder_frame.pack(fill="x", padx=16, pady=(2, 8))
        self._output_dir_var = ctk.StringVar(value="results")
        ctk.CTkEntry(
            folder_frame,
            textvariable=self._output_dir_var,
            height=28,
        ).pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            folder_frame,
            text="📂",
            width=36,
            height=28,
            command=self._browse_output_folder,
        ).pack(side="right", padx=(4, 0))

    # ================================================================== #
    #  Big Upscale Button                                                 #
    # ================================================================== #

    def add_upscale_button(self, command: Callable) -> ctk.CTkButton:
        """Add the primary action button at the bottom. Returns the button
        so the parent can control its state."""
        self._upscale_btn = ctk.CTkButton(
            self,
            text="▶  UPSCALE",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=48,
            corner_radius=10,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=command,
        )
        self._upscale_btn.pack(fill="x", padx=16, pady=(16, 16))
        return self._upscale_btn

    # ================================================================== #
    #  Public API                                                         #
    # ================================================================== #

    def get_settings(self) -> Dict[str, Any]:
        """Return the current settings as a dictionary."""
        tile_str = self._tile_var.get()
        tile = int(tile_str.split()[0]) if tile_str else 0

        return {
            "model_name": self._model_var.get(),
            "outscale": float(self._scale_var.get()),
            "tile": tile,
            "tile_pad": int(self._tile_pad_var.get() or 10),
            "pre_pad": int(self._pre_pad_var.get() or 0),
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

        # Conditional visibility: denoise slider only for general-v3
        is_v3 = name == "realesr-general-x4v3"
        if is_v3:
            self._denoise_label.pack(anchor="w", padx=16, pady=(4, 0))
            self._denoise_slider.pack(padx=16, pady=(2, 0))
            self._denoise_value_label.pack(anchor="w", padx=16, pady=(0, 2))
            self._denoise_hint.pack(anchor="w", padx=16, pady=(0, 4))
        else:
            self._denoise_label.pack_forget()
            self._denoise_slider.pack_forget()
            self._denoise_value_label.pack_forget()
            self._denoise_hint.pack_forget()

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
