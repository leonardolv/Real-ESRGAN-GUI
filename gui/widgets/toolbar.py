"""Toolbar — top action bar with Open, Save, Output Folder, and About buttons."""

import os
import subprocess
import sys
import tkinter as tk
import webbrowser
from typing import Callable, Optional

import customtkinter as ctk


from gui.widgets.tooltip import ToolTip


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
        self._tooltips: list[ToolTip] = []
        self._about_dialog: Optional[ctk.CTkToplevel] = None

        btn_kwargs = dict(
            height=32,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            fg_color="transparent",
            hover_color="#2b2b2b",
            text_color="#ffffff",
            cursor="hand2",
        )

        # Left buttons
        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=8)

        self._open_btn = ctk.CTkButton(
            left, text="📂  Open", command=on_open, width=90, **btn_kwargs
        )
        self._open_btn.pack(side="left", padx=2)
        self._tooltips.append(ToolTip(self._open_btn, "Open image or video files (Ctrl+O)"))

        self._save_btn = ctk.CTkButton(
            left, text="💾  Save As", command=on_save, width=100, **btn_kwargs
        )
        self._save_btn.pack(side="left", padx=2)
        self._save_btn.configure(state="disabled")
        self._tooltips.append(ToolTip(self._save_btn, "Save upscaled result to new file (Ctrl+S)"))

        self._output_btn = ctk.CTkButton(
            left, text="📁  Output Folder", command=on_open_output, width=140, **btn_kwargs
        )
        self._output_btn.pack(side="left", padx=2)
        self._tooltips.append(ToolTip(self._output_btn, "Open output directory in file manager"))

        # Right buttons
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=8)

        self._about_btn = ctk.CTkButton(
            right, text="ℹ  About", command=self._show_about, width=80, **btn_kwargs
        )
        self._about_btn.pack(side="left", padx=2)
        self._tooltips.append(ToolTip(self._about_btn, "About Real-ESRGAN GUI"))

    # ------------------------------------------------------------------ #
    #  Public                                                             #
    # ------------------------------------------------------------------ #

    def set_save_enabled(self, enabled: bool) -> None:
        self._save_btn.configure(state="normal" if enabled else "disabled")

    def destroy(self):
        """Clean up child tooltips and dialogs before destruction."""
        for tooltip in self._tooltips:
            try:
                tooltip.destroy()
            except Exception:
                pass
        self._tooltips.clear()
        if self._about_dialog and self._about_dialog.winfo_exists():
            try:
                self._about_dialog.destroy()
            except Exception:
                pass
            self._about_dialog = None
        super().destroy()

    # ------------------------------------------------------------------ #
    #  Internal                                                           #
    # ------------------------------------------------------------------ #

    def _show_about(self) -> None:
        if self._about_dialog and self._about_dialog.winfo_exists():
            self._about_dialog.focus()
            return

        dialog = ctk.CTkToplevel(self)
        self._about_dialog = dialog
        dialog.title("About Real-ESRGAN GUI")
        dialog.geometry("440x370")
        dialog.resizable(False, False)
        dialog.grab_set()
        dialog.bind("<Escape>", lambda e: dialog.destroy())

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

        gh_btn = ctk.CTkButton(
            links_frame,
            text="🌐 GitHub Repository",
            font=ctk.CTkFont(size=11),
            height=28,
            width=150,
            cursor="hand2",
            fg_color="#2b2b2b",
            hover_color="#3b3b3b",
            command=lambda: webbrowser.open_new_tab("https://github.com/leonardolv/Real-ESRGAN-GUI"),
        )
        gh_btn.pack(side="left", padx=4)
        ToolTip(gh_btn, "Open GitHub project page in browser")

        upstream_btn = ctk.CTkButton(
            links_frame,
            text="Upstream Real-ESRGAN",
            font=ctk.CTkFont(size=11),
            height=28,
            width=150,
            cursor="hand2",
            fg_color="#2b2b2b",
            hover_color="#3b3b3b",
            command=lambda: webbrowser.open_new_tab("https://github.com/xinntao/Real-ESRGAN"),
        )
        upstream_btn.pack(side="left", padx=4)
        ToolTip(upstream_btn, "Open upstream Real-ESRGAN repository in browser")

        close_btn = ctk.CTkButton(
            dialog, text="Close", width=100, cursor="hand2", command=dialog.destroy
        )
        close_btn.pack(pady=(0, 16))
        ToolTip(close_btn, "Dismiss dialog (Esc)")
