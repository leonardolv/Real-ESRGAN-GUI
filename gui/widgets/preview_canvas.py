"""Preview canvas — centerpiece widget for image display with before/after
comparison slider, zoom, and pan.

States:
  - Empty: shows the DropZone
  - Input loaded: shows input image fit-to-canvas
  - Completed: before/after split-screen with draggable vertical divider
"""

import tkinter as tk
from typing import Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageTk


class PreviewCanvas(ctk.CTkFrame):
    """Image preview area with before/after comparison.

    Parameters
    ----------
    master : widget
        Parent widget.
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color="#121212", corner_radius=0)

        # State
        self._input_image: Optional[Image.Image] = None
        self._output_image: Optional[Image.Image] = None
        self._display_input: Optional[ImageTk.PhotoImage] = None
        self._display_output: Optional[ImageTk.PhotoImage] = None
        self._composite: Optional[ImageTk.PhotoImage] = None

        # Zoom / pan
        self._zoom: float = 1.0
        self._pan_x: float = 0.0
        self._pan_y: float = 0.0
        self._drag_start: Optional[Tuple[int, int]] = None

        # Before/after slider position (0.0 = full after, 1.0 = full before)
        self._slider_pos: float = 0.5
        self._dragging_slider: bool = False

        # Labels for before/after
        self._has_output = False

        # Canvas
        self._canvas = tk.Canvas(
            self,
            bg="#121212",
            highlightthickness=0,
            cursor="crosshair",
        )
        self._canvas.pack(fill="both", expand=True)

        # Zoom indicator label (bottom-right overlay)
        self._zoom_label = ctk.CTkLabel(
            self,
            text="100%",
            font=ctk.CTkFont(size=11),
            text_color="#a0a0a0",
            fg_color="#222222",
            corner_radius=4,
            width=60,
            height=22,
        )
        self._zoom_label.place(relx=1.0, rely=1.0, anchor="se", x=-8, y=-8)

        # Bind events
        self._canvas.bind("<Configure>", self._on_resize)
        self._canvas.bind("<MouseWheel>", self._on_scroll)
        self._canvas.bind("<Button-1>", self._on_mouse_down)
        self._canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self._canvas.bind("<Button-2>", self._on_pan_start)
        self._canvas.bind("<B2-Motion>", self._on_pan_drag)
        self._canvas.bind("<Double-Button-1>", self._on_double_click)

        # Keyboard
        top = self.winfo_toplevel()
        top.bind("<Control-equal>", lambda e: self._zoom_step(1))
        top.bind("<Control-minus>", lambda e: self._zoom_step(-1))
        top.bind("<Control-0>", lambda e: self._fit_to_canvas())
        top.bind("<Left>", self._nudge_slider_left)
        top.bind("<Right>", self._nudge_slider_right)
        top.bind("<space>", self._toggle_slider)

    # ================================================================== #
    #  Public API                                                         #
    # ================================================================== #

    def set_input_image(self, img: Image.Image) -> None:
        """Set the input (before) image."""
        self._input_image = img.copy()
        self._output_image = None
        self._has_output = False
        self._slider_pos = 0.5
        self._fit_to_canvas()

    def set_output_image(self, img: Image.Image) -> None:
        """Set the output (after) image for comparison."""
        self._output_image = img.copy()
        self._has_output = True
        self._slider_pos = 0.5
        self._render()

    def clear(self) -> None:
        """Clear both images and reset state."""
        self._input_image = None
        self._output_image = None
        self._has_output = False
        self._composite = None
        self._display_input = None
        self._display_output = None
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._canvas.delete("all")
        self._zoom_label.configure(text="100%")

    def get_zoom(self) -> float:
        return self._zoom

    # ================================================================== #
    #  Rendering                                                          #
    # ================================================================== #

    def _render(self) -> None:
        """Redraw the canvas content based on current state."""
        self._canvas.delete("all")

        cw = self._canvas.winfo_width()
        ch = self._canvas.winfo_height()
        if cw <= 1 or ch <= 1:
            return

        if self._input_image is None:
            return

        if self._has_output and self._output_image is not None:
            self._render_comparison(cw, ch)
        else:
            self._render_single(cw, ch)

    def _render_single(self, cw: int, ch: int) -> None:
        """Render just the input image."""
        img = self._input_image
        if img is None:
            return

        display_img = self._transform_image(img, cw, ch)
        self._display_input = ImageTk.PhotoImage(display_img)
        self._canvas.create_image(cw // 2, ch // 2, image=self._display_input, anchor="center")

        # Label
        self._canvas.create_text(
            12, 12, text="Input", fill="#AAAAAA",
            font=("Segoe UI", 11, "bold"), anchor="nw"
        )

    def _render_comparison(self, cw: int, ch: int) -> None:
        """Render before/after comparison with slider."""
        if self._input_image is None or self._output_image is None:
            return

        # Transform both images to canvas coordinates
        input_display = self._transform_image(self._input_image, cw, ch)
        output_display = self._transform_image(self._output_image, cw, ch)

        # Ensure same size
        w, h = input_display.size
        if output_display.size != (w, h):
            output_display = output_display.resize((w, h), Image.LANCZOS)

        # Split position in pixels
        split_x = int(self._slider_pos * w)

        # Create composite: left=before, right=after
        composite = Image.new("RGB", (w, h))
        # Left side (before / input)
        if split_x > 0:
            left_crop = input_display.crop((0, 0, split_x, h))
            composite.paste(left_crop, (0, 0))
        # Right side (after / output)
        if split_x < w:
            right_crop = output_display.crop((split_x, 0, w, h))
            composite.paste(right_crop, (split_x, 0))

        # Draw divider line
        draw = ImageDraw.Draw(composite)
        draw.line([(split_x, 0), (split_x, h)], fill="white", width=2)

        # Draw slider handle
        handle_y = h // 2
        handle_r = 12
        draw.ellipse(
            [split_x - handle_r, handle_y - handle_r, split_x + handle_r, handle_y + handle_r],
            fill="white",
            outline="#2563EB",
            width=2,
        )
        # Arrows in handle
        draw.text((split_x - 7, handle_y - 6), "◀▶", fill="#2563EB")

        self._composite = ImageTk.PhotoImage(composite)
        # Center in canvas
        cx = (cw - w) // 2
        cy = (ch - h) // 2
        self._canvas.create_image(cx, cy, image=self._composite, anchor="nw", tags="composite")

        # Labels
        self._canvas.create_text(
            cx + 12, cy + 12, text="Before", fill="#AAAAAA",
            font=("Segoe UI", 11, "bold"), anchor="nw"
        )
        self._canvas.create_text(
            cx + w - 12, cy + 12, text="After", fill="#AAAAAA",
            font=("Segoe UI", 11, "bold"), anchor="ne"
        )

        # Store geometry for hit testing
        self._comp_x = cx
        self._comp_y = cy
        self._comp_w = w
        self._comp_h = h

    def _transform_image(self, img: Image.Image, cw: int, ch: int) -> Image.Image:
        """Apply zoom and fit-to-canvas transform."""
        iw, ih = img.size
        # Calculate scale to fit canvas
        base_scale = min(cw / iw, ch / ih, 1.0)
        scale = base_scale * self._zoom
        new_w = max(1, int(iw * scale))
        new_h = max(1, int(ih * scale))
        return img.resize((new_w, new_h), Image.LANCZOS)

    # ================================================================== #
    #  Zoom & Pan                                                         #
    # ================================================================== #

    def _fit_to_canvas(self) -> None:
        """Reset zoom and pan to fit the image in canvas."""
        self._zoom = 1.0
        self._pan_x = 0.0
        self._pan_y = 0.0
        self._zoom_label.configure(text="100%")
        self._render()

    def _zoom_step(self, direction: int) -> None:
        """Zoom in (+1) or out (-1) by 0.25x steps."""
        new_zoom = self._zoom + direction * 0.25
        new_zoom = max(0.25, min(8.0, new_zoom))
        self._zoom = new_zoom
        self._zoom_label.configure(text=f"{int(self._zoom * 100)}%")
        self._render()

    def _on_scroll(self, event) -> None:
        direction = 1 if event.delta > 0 else -1
        self._zoom_step(direction)

    # ================================================================== #
    #  Slider interaction                                                 #
    # ================================================================== #

    def _on_mouse_down(self, event) -> None:
        if self._has_output and hasattr(self, "_comp_x"):
            # Check if near slider
            split_px = self._comp_x + int(self._slider_pos * self._comp_w)
            if abs(event.x - split_px) < 20:
                self._dragging_slider = True
                self._canvas.configure(cursor="ew_resize")
                return
        self._drag_start = (event.x, event.y)

    def _on_mouse_drag(self, event) -> None:
        if self._dragging_slider and hasattr(self, "_comp_x"):
            rel_x = event.x - self._comp_x
            self._slider_pos = max(0.02, min(0.98, rel_x / self._comp_w))
            self._render()
        elif self._drag_start:
            # Pan
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self._pan_x += dx
            self._pan_y += dy
            self._drag_start = (event.x, event.y)

    def _on_mouse_up(self, event) -> None:
        self._dragging_slider = False
        self._drag_start = None
        self._canvas.configure(cursor="crosshair")

    def _on_pan_start(self, event) -> None:
        self._drag_start = (event.x, event.y)
        self._canvas.configure(cursor="fleur")

    def _on_pan_drag(self, event) -> None:
        if self._drag_start:
            dx = event.x - self._drag_start[0]
            dy = event.y - self._drag_start[1]
            self._pan_x += dx
            self._pan_y += dy
            self._drag_start = (event.x, event.y)
            self._render()

    def _on_double_click(self, event) -> None:
        """Double-click resets slider to 50/50."""
        if self._has_output:
            self._slider_pos = 0.5
            self._render()

    def _nudge_slider_left(self, event) -> None:
        if self._has_output:
            self._slider_pos = max(0.02, self._slider_pos - 0.05)
            self._render()

    def _nudge_slider_right(self, event) -> None:
        if self._has_output:
            self._slider_pos = min(0.98, self._slider_pos + 0.05)
            self._render()

    def _toggle_slider(self, event) -> None:
        """Toggle between 50/50 and 0/100 (full after)."""
        if self._has_output:
            if self._slider_pos > 0.1:
                self._slider_pos = 0.02
            else:
                self._slider_pos = 0.5
            self._render()

    # ================================================================== #
    #  Resize                                                             #
    # ================================================================== #

    def _on_resize(self, event) -> None:
        self._render()
