"""Toolbar — top action bar with Open, Save, Output Folder, and About buttons."""

import os
import subprocess
import sys
import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk


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

        ctk.CTkButton(left, text="📂  Open", command=on_open, width=90, **btn_kwargs).pack(
            side="left", padx=2
        )
        self._save_btn = ctk.CTkButton(
            left, text="💾  Save As", command=on_save, width=100, **btn_kwargs
        )
        self._save_btn.pack(side="left", padx=2)
        self._save_btn.configure(state="disabled")

        ctk.CTkButton(
            left, text="📁  Output Folder", command=on_open_output, width=140, **btn_kwargs
        ).pack(side="left", padx=2)

        # Right buttons
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=8)

        ctk.CTkButton(
            right, text="ℹ  About", command=self._show_about, width=80, **btn_kwargs
        ).pack(side="left", padx=2)

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
        dialog.geometry("420x320")
        dialog.resizable(False, False)
        dialog.grab_set()

        ctk.CTkLabel(
            dialog,
            text="Real-ESRGAN GUI",
            font=ctk.CTkFont(size=22, weight="bold"),
        ).pack(pady=(24, 4))

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
        ).pack(pady=16)

        ctk.CTkButton(
            dialog, text="Close", width=100, command=dialog.destroy
        ).pack(pady=(0, 16))
