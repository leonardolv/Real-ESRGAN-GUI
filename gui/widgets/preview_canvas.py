"""Preview canvas — centerpiece widget for image display with before/after
comparison slider, zoom, and pan.

States:
  - Empty: shows the DropZone
  - Input loaded: shows input image fit-to-canvas
  - Completed: before/after split-screen with draggable vertical divider
"""

import tkinter as tk
from typing import Optional, Tuple

import cv2
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

        # Video Playback State
        self._input_video_cap: Optional[cv2.VideoCapture] = None
        self._output_video_cap: Optional[cv2.VideoCapture] = None
        self._is_video = False
        self._video_loop_id: Optional[str] = None
        self._video_fps = 30.0

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

        # Video Controls (hidden by default)
        self._controls_frame = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="#1a1a1a")
        
        self._is_paused = True
        self._total_frames = 0
        self._current_frame = 0
        
        # Timeline
        self._slider_var = tk.DoubleVar(value=0.0)
        self._timeline_slider = ctk.CTkSlider(self._controls_frame, from_=0, to=1, variable=self._slider_var, command=self._on_timeline_seek)
        self._timeline_slider.pack(side="top", fill="x", padx=10, pady=(5,0))
        
        # Buttons Frame
        btns_frame = ctk.CTkFrame(self._controls_frame, fg_color="transparent")
        btns_frame.pack(side="bottom", fill="x", pady=5, padx=10)
        
        self._prev_btn = ctk.CTkButton(btns_frame, text="⏮", width=40, command=self._step_backward)
        self._prev_btn.pack(side="left", padx=5)
        
        self._play_btn = ctk.CTkButton(btns_frame, text="▶ Play", width=80, command=self._toggle_pause, fg_color="#10B981", hover_color="#059669")
        self._play_btn.pack(side="left", padx=5)
        
        self._next_btn = ctk.CTkButton(btns_frame, text="⏭", width=40, command=self._step_forward)
        self._next_btn.pack(side="left", padx=5)
        
        self._time_label = ctk.CTkLabel(btns_frame, text="0:00 / 0:00", text_color="#a0a0a0")
        self._time_label.pack(side="right", padx=5)

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
        self._stop_video()
        self._is_video = False
        self._input_image = img.copy()
        self._output_image = None
        self._has_output = False
        self._slider_pos = 0.5
        self._fit_to_canvas()

    def set_output_image(self, img: Image.Image) -> None:
        """Set the output (after) image for comparison."""
        self._stop_video()
        self._is_video = False
        self._output_image = img.copy()
        self._has_output = True
        self._slider_pos = 0.5
        self._render()

    def set_input_video(self, path: str) -> None:
        """Set the input video and start paused."""
        self._stop_video()
        self._is_video = True
        self._is_paused = True
        self._input_image = None
        self._output_image = None
        self._has_output = False
        self._slider_pos = 0.5
        self._input_video_cap = cv2.VideoCapture(path)
        if self._input_video_cap.isOpened():
            fps = self._input_video_cap.get(cv2.CAP_PROP_FPS)
            self._video_fps = fps if fps > 0 else 30.0
            self._total_frames = int(self._input_video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self._current_frame = 0
            
            # Read first frame to initialize canvas scaling
            self._read_and_render_once()
            self._fit_to_canvas()
            
            self._start_video()
            self._update_controls_ui()

    def set_output_video(self, path: str) -> None:
        """Set the output video for comparison and start paused."""
        self._is_video = True
        self._is_paused = True
        self._output_image = None
        self._has_output = True
        self._slider_pos = 0.5
        
        if self._output_video_cap is not None:
            self._output_video_cap.release()
            
        self._output_video_cap = cv2.VideoCapture(path)
        
        # Sync input video to current frame
        if self._input_video_cap is not None:
            self._input_video_cap.set(cv2.CAP_PROP_POS_FRAMES, self._current_frame)
            
        self._read_and_render_once()
        self._start_video()
        self._update_controls_ui()

    def clear(self) -> None:
        """Clear both images/videos and reset state."""
        self._stop_video()
        self._is_video = False
        self._is_paused = True
        self._controls_frame.pack_forget()
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
    #  Video Playback                                                     #
    # ================================================================== #

    def _start_video(self) -> None:
        """Start the video playback loop."""
        if self._video_loop_id is None:
            self._play_video_frame()

    def _stop_video(self) -> None:
        """Stop video playback and release captures."""
        if self._video_loop_id is not None:
            self.after_cancel(self._video_loop_id)
            self._video_loop_id = None
            
        if self._input_video_cap is not None:
            self._input_video_cap.release()
            self._input_video_cap = None
            
        if self._output_video_cap is not None:
            self._output_video_cap.release()
            self._output_video_cap = None

    def _toggle_pause(self) -> None:
        """Toggle video play/pause state."""
        self._is_paused = not self._is_paused
        self._update_controls_ui()

    def _update_controls_ui(self) -> None:
        """Update button state and visibility."""
        if not self._is_video:
            self._controls_frame.pack_forget()
            return
            
        self._controls_frame.pack(side="bottom", fill="x", before=self._canvas)
        if self._is_paused:
            self._play_btn.configure(text="▶ Play", fg_color="#10B981", hover_color="#059669")
        else:
            self._play_btn.configure(text="⏸ Pause", fg_color="#2563EB", hover_color="#1d4ed8")
            
        self._update_time_label()

    def _update_time_label(self):
        def format_time(frames, fps):
            seconds = int(frames / max(1, fps))
            return f"{seconds // 60}:{seconds % 60:02d}"
        
        cur = format_time(self._current_frame, self._video_fps)
        tot = format_time(self._total_frames, self._video_fps)
        self._time_label.configure(text=f"{cur} / {tot}")
        
        if self._total_frames > 0:
            self._slider_var.set(self._current_frame / self._total_frames)

    def _on_timeline_seek(self, value):
        if not self._is_video or self._total_frames == 0: return
        self._is_paused = True
        self._current_frame = int(float(value) * self._total_frames)
        self._sync_video_caps(self._current_frame)
        self._read_and_render_once()
        self._update_controls_ui()

    def _step_backward(self):
        if not self._is_video: return
        self._is_paused = True
        self._current_frame = max(0, self._current_frame - 1)
        self._sync_video_caps(self._current_frame)
        self._read_and_render_once()
        self._update_controls_ui()
        
    def _step_forward(self):
        if not self._is_video: return
        self._is_paused = True
        self._current_frame = min(self._total_frames - 1, self._current_frame + 1)
        self._sync_video_caps(self._current_frame)
        self._read_and_render_once()
        self._update_controls_ui()

    def _sync_video_caps(self, frame_idx):
        if self._input_video_cap is not None:
            self._input_video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        if self._output_video_cap is not None:
            self._output_video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)

    def _read_and_render_once(self) -> bool:
        need_render = False
        
        if self._input_video_cap is not None:
            ret, frame = self._input_video_cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._input_image = Image.fromarray(frame_rgb)
                need_render = True
            else:
                return False

        if self._has_output and self._output_video_cap is not None:
            ret, frame = self._output_video_cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self._output_image = Image.fromarray(frame_rgb)
                need_render = True
            else:
                return False

        if need_render:
            self._render()
            return True
        return False

    def _play_video_frame(self) -> None:
        """Read the next frame from videos, render, and schedule the next frame."""
        if not self._is_video:
            self._video_loop_id = None
            return

        delay_ms = max(10, int(1000 / self._video_fps))

        if self._is_paused:
            self._video_loop_id = self.after(delay_ms, self._play_video_frame)
            return

        # Read frame
        if self._read_and_render_once():
            self._current_frame += 1
            self._update_time_label()
        else:
            # End of video -> loop back
            self._current_frame = 0
            self._sync_video_caps(0)
            self._read_and_render_once()
            self._update_time_label()

        self._video_loop_id = self.after(delay_ms, self._play_video_frame)

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
        cx = cw // 2 + int(self._pan_x)
        cy = ch // 2 + int(self._pan_y)
        self._canvas.create_image(cx, cy, image=self._display_input, anchor="center")

        # Label with dimensions
        iw, ih = self._input_image.size
        self._canvas.create_text(
            12, 12, text=f"Input  ·  {iw} × {ih}", fill="#AAAAAA",
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
        composite = Image.new("RGBA", (w, h), (0,0,0,0))
        # Left side (before / input)
        if split_x > 0:
            left_crop = input_display.crop((0, 0, split_x, h)).convert("RGBA")
            composite.paste(left_crop, (0, 0))
        # Right side (after / output)
        if split_x < w:
            right_crop = output_display.crop((split_x, 0, w, h)).convert("RGBA")
            composite.paste(right_crop, (split_x, 0))

        # Modern Slider Handle UI
        overlay = Image.new("RGBA", (w, h), (0,0,0,0))
        draw = ImageDraw.Draw(overlay)

        # Draw soft shadow for the line
        shadow_w = 4
        for i in range(shadow_w):
            alpha = int(100 * (1 - i/shadow_w))
            draw.line([(split_x - i, 0), (split_x - i, h)], fill=(0,0,0,alpha), width=1)
            draw.line([(split_x + i, 0), (split_x + i, h)], fill=(0,0,0,alpha), width=1)
            
        # Draw divider line (thicker)
        draw.line([(split_x, 0), (split_x, h)], fill=(255, 255, 255, 255), width=3)

        # Pill-shaped handle with shadow
        handle_y = h // 2
        handle_w, handle_h = 44, 28
        hx0, hy0 = split_x - handle_w // 2, handle_y - handle_h // 2
        hx1, hy1 = split_x + handle_w // 2, handle_y + handle_h // 2
        
        # Handle shadow
        for i in range(3):
            alpha = 60 - i * 20
            draw.rounded_rectangle([hx0-i, hy0-i, hx1+i, hy1+i], radius=14, fill=(0,0,0,alpha))

        # Handle body (white background, translucent edge)
        draw.rounded_rectangle([hx0, hy0, hx1, hy1], radius=14, fill=(255,255,255,255), outline=(37, 99, 235, 255), width=2)
        
        # Draw inner grip arrows
        try:
            # Simple text as fallback since custom font might fail
            font = ImageFont.truetype("arial.ttf", 12)
            draw.text((split_x - 14, handle_y - 8), "◀", fill=(37, 99, 235, 255), font=font)
            draw.text((split_x + 2, handle_y - 8), "▶", fill=(37, 99, 235, 255), font=font)
        except IOError:
            draw.text((split_x - 10, handle_y - 6), "<", fill=(37, 99, 235, 255))
            draw.text((split_x + 4, handle_y - 6), ">", fill=(37, 99, 235, 255))

        # Merge overlay onto composite
        composite = Image.alpha_composite(composite, overlay)

        self._composite = ImageTk.PhotoImage(composite.convert("RGB"))
        # Center in canvas, applying pan offsets
        cx = (cw - w) // 2 + int(self._pan_x)
        cy = (ch - h) // 2 + int(self._pan_y)
        self._canvas.create_image(cx, cy, image=self._composite, anchor="nw", tags="composite")

        # Labels with dimensions
        in_w, in_h = self._input_image.size
        out_w, out_h = self._output_image.size
        self._canvas.create_text(
            cx + 12, cy + 12, text=f"Before  ·  {in_w} × {in_h}", fill="#AAAAAA",
            font=("Segoe UI", 11, "bold"), anchor="nw"
        )
        self._canvas.create_text(
            cx + w - 12, cy + 12, text=f"After  ·  {out_w} × {out_h}", fill="#AAAAAA",
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
                self._canvas.configure(cursor="size_we")
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
            self._render()

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
