"""Toolbar — top action bar with Open, Save, Output Folder, and About buttons."""

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk


class ToolTip:
    """Lightweight hover tooltip for widgets."""

    def __init__(self, widget, text: str):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self._show_tip)
        self.widget.bind("<Leave>", self._hide_tip)

    def _show_tip(self, event=None) -> None:
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            label = tk.Label(
                tw,
                text=self.text,
                justify=tk.LEFT,
                background="#2a2d35",
                foreground="#ffffff",
                relief=tk.SOLID,
                borderwidth=1,
                font=("Segoe UI", 9),
                padx=6,
                pady=3,
            )
            label.pack()
        except Exception:
            pass

    def _hide_tip(self, event=None) -> None:
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


class Toolbar(ctk.CTkFrame):
    """Horizontal toolbar at the top of the main window.

    Parameters
    ----------
    on_open : callable
        Called when the user clicks "Open".
    on_save : callable
        Called when the user clicks "Save As".
    on_open_output : callable
        Called when the user clicks "Output Folder".
    """

    def __init__(
        self,
        master,
        on_open: Callable,
        on_save: Callable,
        on_open_output: Callable,
        **kwargs,
    ):
        super().__init__(master, height=44, **kwargs)
        self.configure(fg_color="#1a1a1a", corner_radius=0)
        self.pack_propagate(False)

        self._on_open = on_open
        self._on_save = on_save
        self._on_open_output = on_open_output

        btn_kwargs = dict(
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#ffffff",
        )

        # Left buttons
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=8)

        open_btn = ctk.CTkButton(
            left, text="📂  Open", command=on_open, width=90, **btn_kwargs
        )
        open_btn.pack(side="left", padx=2)
        ToolTip(open_btn, "Open image or video files (Ctrl+O)")

        self._save_btn = ctk.CTkButton(
            left, text="💾  Save As", command=on_save, width=100, **btn_kwargs
        )
        self._save_btn.pack(side="left", padx=2)
        self._save_btn.configure(state="disabled")
        ToolTip(self._save_btn, "Save upscaled result to new file (Ctrl+S)")

        output_btn = ctk.CTkButton(
            left, text="📁  Output Folder", command=on_open_output, width=140, **btn_kwargs
        )
        output_btn.pack(side="left", padx=2)
        ToolTip(output_btn, "Open output directory in file manager")

        # Right buttons
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=8)

        about_btn = ctk.CTkButton(
            right, text="ℹ  About", command=self._show_about, width=80, **btn_kwargs
        )
        about_btn.pack(side="left", padx=2)
        ToolTip(about_btn, "About Real-ESRGAN GUI")

    # ------------------------------------------------------------------ #
    #  Public                                                             #
    # ------------------------------------------------------------------ #

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_btn.configure(state="normal" if enabled else "disabled")

    # ------------------------------------------------------------------ #
    #  Internal                                                           #
    # ------------------------------------------------------------------ #

    def _show_about(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("About Real-ESRGAN GUI")
        dialog.geometry("440x370")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Real-ESRGAN GUI",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(20, 4))

        ctk.CTkLabel(
            dialog,
            text="v0.1.0",
            font=ctk.CTkFont(size=14),
            text_color="#a0a0a0",
        ).pack()

        ctk.CTkLabel(
            dialog,
            text=(
                "A modern desktop interface for Real-ESRGAN\n"
                "AI-powered image & video super-resolution.\n\n"
                "Based on Real-ESRGAN by Xintao Wang et al.\n"
                "Tencent ARC Lab\n\n"
                "Licensed under BSD-3-Clause"
            ),
            font=ctk.CTkFont(size=12),
            justify="center",
        ).pack(pady=(12, 14))

        links_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        links_frame.pack(pady=(0, 14))

        ctk.CTkButton(
            links_frame,
            text="🌐 GitHub Repository",
            font=ctk.CTkFont(size=11),
            height=28,
            width=150,
            fg_color="#2b2b2b",
            hover_color="#3b3b3b",
            command=lambda: webbrowser.open_new_tab("https://github.com/leonardolv/Real-ESRGAN-GUI"),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            links_frame,
            text="Upstream Real-ESRGAN",
            font=ctk.CTkFont(size=11),
            height=28,
            width=150,
            fg_color="#2b2b2b",
            hover_color="#3b3b3b",
            command=lambda: webbrowser.open_new_tab("https://github.com/xinntao/Real-ESRGAN"),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            dialog, text="Close", width=100, command=dialog.destroy
        ).pack(pady=(0, 16))
