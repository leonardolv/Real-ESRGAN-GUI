"""Upscale controller — threaded bridge between the GUI and the Real-ESRGAN
inference engine.

Runs all GPU-bound work on a background ``threading.Thread`` and communicates
progress/results back to the UI via a ``queue.Queue`` polled by Tkinter's
``after()`` timer.
"""

import os
import queue
import threading
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import cv2
import numpy as np
import torch

from gui.controllers.model_manager import ModelManager


# ---------------------------------------------------------------------- #
#  Message types sent from worker → UI                                    #
# ---------------------------------------------------------------------- #

class MsgType(Enum):
    PROGRESS = auto()
    PREVIEW = auto()       # thumbnail of the output for live preview
    COMPLETE = auto()
    ERROR = auto()
    BATCH_PROGRESS = auto()
    LOG = auto()


@dataclass
class WorkerMessage:
    type: MsgType
    data: Any = None


# ---------------------------------------------------------------------- #
#  Job specification                                                      #
# ---------------------------------------------------------------------- #

@dataclass
class UpscaleJob:
    """Describes a single upscaling task."""
    input_path: str
    output_path: str
    model_name: str = "RealESRGAN_x4plus"
    outscale: float = 4.0
    tile: int = 0
    tile_pad: int = 10
    pre_pad: int = 0
    face_enhance: bool = False
    fp32: bool = False
    denoise_strength: float = 0.5
    alpha_upsampler: str = "realesrgan"
    output_ext: str = "auto"
    suffix: str = "out"
    gpu_id: Optional[int] = None


# ---------------------------------------------------------------------- #
#  Controller                                                             #
# ---------------------------------------------------------------------- #

class UpscaleController:
    """Orchestrates image upscaling in a background thread.

    Usage from the GUI::

        ctrl = UpscaleController(model_manager)
        ctrl.on_message = my_handler   # receives WorkerMessage objects
        ctrl.submit(job)               # non-blocking
        ctrl.cancel()                  # graceful abort

    The GUI should call ``ctrl.poll()`` periodically (e.g. via ``after(50)``)
    to drain the message queue and update the UI.
    """

    def __init__(self, model_manager: ModelManager):
        self.model_manager = model_manager
        self._msg_queue: queue.Queue[WorkerMessage] = queue.Queue()
        self._cancel_event = threading.Event()
        self._worker: Optional[threading.Thread] = None
        self._current_upsampler = None
        self._current_model_name: Optional[str] = None

        # External callback: set by the GUI
        self.on_message: Optional[Callable[[WorkerMessage], None]] = None

    # ------------------------------------------------------------------ #
    #  Public API                                                         #
    # ------------------------------------------------------------------ #

    @property
    def is_busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def submit(self, job: UpscaleJob) -> None:
        """Submit a single upscale job (non-blocking)."""
        if self.is_busy:
            self._post(MsgType.ERROR, "A job is already running.")
            return
        self._cancel_event.clear()
        self._worker = threading.Thread(
            target=self._run_job, args=(job,), daemon=True
        )
        self._worker.start()

    def submit_batch(self, jobs: List[UpscaleJob]) -> None:
        """Submit multiple jobs for sequential processing."""
        if self.is_busy:
            self._post(MsgType.ERROR, "A job is already running.")
            return
        self._cancel_event.clear()
        self._worker = threading.Thread(
            target=self._run_batch, args=(jobs,), daemon=True
        )
        self._worker.start()

    def cancel(self) -> None:
        """Signal the worker to stop after the current tile/frame."""
        self._cancel_event.set()

    def poll(self) -> List[WorkerMessage]:
        """Drain the message queue. Call from the GUI thread."""
        messages = []
        while True:
            try:
                msg = self._msg_queue.get_nowait()
                messages.append(msg)
                if self.on_message:
                    self.on_message(msg)
            except queue.Empty:
                break
        return messages

    # ------------------------------------------------------------------ #
    #  GPU info                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        """Return GPU name and VRAM info, or CPU fallback."""
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "name": torch.cuda.get_device_name(0),
                "total_vram_gb": round(props.total_mem / (1024 ** 3), 1),
                "used_vram_gb": round(torch.cuda.memory_allocated(0) / (1024 ** 3), 1),
                "device": "cuda",
            }
        return {"name": "CPU (no CUDA GPU detected)", "total_vram_gb": 0, "used_vram_gb": 0, "device": "cpu"}

    # ------------------------------------------------------------------ #
    #  Internal: single-job worker                                        #
    # ------------------------------------------------------------------ #

    def _run_job(self, job: UpscaleJob) -> None:
        from gui.utils.image_utils import is_video_file
        if is_video_file(job.input_path):
            self._run_video_job(job)
        else:
            self._run_image_job(job)

    def _run_image_job(self, job: UpscaleJob) -> None:
        try:
            self._post(MsgType.PROGRESS, {"percent": 0, "status": "Loading model…"})

            # Build / reuse upsampler
            upsampler = self._get_upsampler(job)
            if self._cancelled():
                return

            self._post(MsgType.PROGRESS, {"percent": 10, "status": "Reading image…"})

            # Read input
            img = cv2.imread(job.input_path, cv2.IMREAD_UNCHANGED)
            if img is None:
                self._post(MsgType.ERROR, f"Cannot read: {job.input_path}")
                return

            # Detect image mode
            if len(img.shape) == 3 and img.shape[2] == 4:
                img_mode = "RGBA"
            else:
                img_mode = None

            self._post(MsgType.PROGRESS, {"percent": 20, "status": "Upscaling…"})

            def progress_callback(p):
                percent = int(20 + p * 65)
                self._post(MsgType.PROGRESS, {"percent": percent, "status": f"Upscaling ({int(p*100)}%)…"})

            # Face enhancement path
            if job.face_enhance:
                face_enhancer = self._build_face_enhancer(upsampler, job)
                _, _, output = face_enhancer.enhance(
                    img, has_aligned=False, only_center_face=False, paste_back=True
                )
            else:
                output, _ = upsampler.enhance(img, outscale=job.outscale, progress_callback=progress_callback)

            if self._cancelled():
                return

            self._post(MsgType.PROGRESS, {"percent": 85, "status": "Saving…"})

            # Determine output path
            save_path = self._resolve_output_path(job, img_mode)

            # Save
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            cv2.imwrite(save_path, output)

            self._post(MsgType.PROGRESS, {"percent": 100, "status": "Done"})
            self._post(MsgType.COMPLETE, {
                "input_path": job.input_path,
                "output_path": save_path,
                "output_image": output,
            })

        except RuntimeError as e:
            err = str(e)
            if "out of memory" in err.lower():
                self._post(
                    MsgType.ERROR,
                    "GPU out of memory! Try setting Tile Size to 256 or 512 in Settings.",
                )
            else:
                self._post(MsgType.ERROR, f"Runtime error: {err}")
        except Exception as e:
            self._post(MsgType.ERROR, f"Error: {e}\n{traceback.format_exc()}")
        finally:
            # Free VRAM
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def _run_video_job(self, job: UpscaleJob) -> None:
        try:
            self._post(MsgType.PROGRESS, {"percent": 0, "status": "Loading model…"})
            upsampler = self._get_upsampler(job)
            if self._cancelled():
                return
                
            from gui.utils.video_utils import get_video_info, find_ffmpeg
            import ffmpeg
            
            ffmpeg_path = find_ffmpeg()
            if not ffmpeg_path:
                self._post(MsgType.ERROR, "FFmpeg is not installed or not in PATH.")
                return
                
            info = get_video_info(job.input_path)
            if not info:
                self._post(MsgType.ERROR, f"Cannot read video metadata: {job.input_path}")
                return
                
            width = info["width"]
            height = info["height"]
            fps = info["fps"]
            has_audio = info["has_audio"]
            nb_frames = max(1, info["nb_frames"])
            
            save_path = self._resolve_output_path(job, is_video=True)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            
            self._post(MsgType.PROGRESS, {"percent": 5, "status": "Starting video stream…"})
            
            # Setup Reader
            stream_reader = (
                ffmpeg.input(job.input_path).output(
                    'pipe:', format='rawvideo', pix_fmt='bgr24', loglevel='error'
                ).run_async(pipe_stdin=True, pipe_stdout=True, cmd=ffmpeg_path)
            )
            
            # Setup Writer
            out_width = int(width * job.outscale)
            out_height = int(height * job.outscale)
            
            writer_input = ffmpeg.input(
                'pipe:', format='rawvideo', pix_fmt='bgr24', 
                s=f'{out_width}x{out_height}', framerate=fps
            )
            
            if has_audio:
                audio = ffmpeg.input(job.input_path).audio
                stream_writer = ffmpeg.output(
                    writer_input, audio, save_path, 
                    pix_fmt='yuv420p', vcodec='libx264', acodec='copy', loglevel='error'
                ).overwrite_output().run_async(pipe_stdin=True, pipe_stdout=True, cmd=ffmpeg_path)
            else:
                stream_writer = ffmpeg.output(
                    writer_input, save_path, 
                    pix_fmt='yuv420p', vcodec='libx264', loglevel='error'
                ).overwrite_output().run_async(pipe_stdin=True, pipe_stdout=True, cmd=ffmpeg_path)

            # Face enhancer
            face_enhancer = None
            if job.face_enhance:
                face_enhancer = self._build_face_enhancer(upsampler, job)

            # Processing loop
            frame_idx = 0
            while True:
                if self._cancelled():
                    break
                    
                in_bytes = stream_reader.stdout.read(width * height * 3)
                if not in_bytes:
                    break
                    
                img = np.frombuffer(in_bytes, np.uint8).reshape([height, width, 3])
                
                if face_enhancer:
                    _, _, output = face_enhancer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
                else:
                    output, _ = upsampler.enhance(img, outscale=job.outscale)
                
                stream_writer.stdin.write(output.astype(np.uint8).tobytes())
                
                frame_idx += 1
                if frame_idx % max(1, nb_frames // 100) == 0:
                    pct = 5 + (frame_idx / nb_frames) * 90
                    self._post(MsgType.PROGRESS, {"percent": pct, "status": f"Frame {frame_idx}/{nb_frames}"})

            # Close pipes
            stream_reader.stdout.close()
            stream_reader.wait()
            stream_writer.stdin.close()
            stream_writer.wait()
            
            if self._cancelled():
                if os.path.exists(save_path):
                    os.remove(save_path)
                return

            self._post(MsgType.PROGRESS, {"percent": 100, "status": "Done"})
            self._post(MsgType.COMPLETE, {
                "input_path": job.input_path,
                "output_path": save_path,
                "output_image": None,
            })

        except RuntimeError as e:
            err = str(e)
            if "out of memory" in err.lower():
                self._post(MsgType.ERROR, "GPU out of memory! Try setting Tile Size to 256 or 512 in Settings.")
            else:
                self._post(MsgType.ERROR, f"Runtime error: {err}")
        except Exception as e:
            self._post(MsgType.ERROR, f"Error: {e}\n{traceback.format_exc()}")
        finally:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    # ------------------------------------------------------------------ #
    #  Internal: batch worker                                             #
    # ------------------------------------------------------------------ #

    def _run_batch(self, jobs: List[UpscaleJob]) -> None:
        total = len(jobs)
        for i, job in enumerate(jobs):
            if self._cancelled():
                self._post(MsgType.LOG, f"Batch cancelled at item {i + 1}/{total}")
                return
            self._post(MsgType.BATCH_PROGRESS, {
                "current": i + 1,
                "total": total,
                "file": os.path.basename(job.input_path),
            })
            self._run_job(job)

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _get_upsampler(self, job: UpscaleJob):
        """Build or reuse the RealESRGANer upsampler."""
        from realesrgan import RealESRGANer

        # Reuse if same model
        if self._current_upsampler and self._current_model_name == job.model_name:
            return self._current_upsampler

        model_info = self.model_manager.get(job.model_name)
        if model_info is None:
            raise ValueError(f"Unknown model: {job.model_name}")

        # Ensure downloaded
        if not model_info.downloaded:
            self.model_manager.download_model(job.model_name)

        network = self.model_manager.build_network(job.model_name)
        model_path = self.model_manager.get_model_path(job.model_name)

        # Handle DNI (denoise network interpolation) for general-v3
        dni_weight = None
        if job.model_name == "realesr-general-x4v3" and job.denoise_strength != 1:
            wdn_path = str(model_path).replace("realesr-general-x4v3", "realesr-general-wdn-x4v3")
            model_path = [model_path, wdn_path]
            dni_weight = [job.denoise_strength, 1 - job.denoise_strength]

        upsampler = RealESRGANer(
            scale=model_info.scale,
            model_path=model_path,
            dni_weight=dni_weight,
            model=network,
            tile=job.tile,
            tile_pad=job.tile_pad,
            pre_pad=job.pre_pad,
            half=not job.fp32,
            gpu_id=job.gpu_id,
        )

        self._current_upsampler = upsampler
        self._current_model_name = job.model_name
        return upsampler

    def _build_face_enhancer(self, upsampler, job: UpscaleJob):
        """Build GFPGAN face enhancer with the upsampler as background."""
        from gfpgan import GFPGANer
        return GFPGANer(
            model_path="https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.3.pth",
            upscale=job.outscale,
            arch="clean",
            channel_multiplier=2,
            bg_upsampler=upsampler,
        )

    def _resolve_output_path(self, job: UpscaleJob, img_mode: Optional[str] = None, is_video: bool = False) -> str:
        """Determine the full output file path."""
        basename = os.path.splitext(os.path.basename(job.input_path))[0]
        _, orig_ext = os.path.splitext(job.input_path)

        if is_video:
            if job.output_ext == "auto" or job.output_ext in ["png", "jpg", "webp"]:
                ext = orig_ext.lstrip(".")
                if ext.lower() not in ["mp4", "mkv", "avi", "mov"]:
                    ext = "mp4"
            else:
                ext = job.output_ext
        else:
            if job.output_ext == "auto":
                ext = orig_ext.lstrip(".")
            else:
                ext = job.output_ext

            # RGBA must be saved as PNG
            if img_mode == "RGBA":
                ext = "png"

        if job.suffix:
            filename = f"{basename}_{job.suffix}.{ext}"
        else:
            filename = f"{basename}.{ext}"

        return os.path.join(job.output_path, filename)

    def _post(self, msg_type: MsgType, data: Any = None) -> None:
        """Post a message to the UI queue."""
        self._msg_queue.put(WorkerMessage(type=msg_type, data=data))

    def _cancelled(self) -> bool:
        """Check if cancellation was requested."""
        if self._cancel_event.is_set():
            self._post(MsgType.LOG, "Cancelled by user.")
            return True
        return False

    def invalidate_model_cache(self) -> None:
        """Force model reload on next job (e.g. after settings change)."""
        self._current_upsampler = None
        self._current_model_name = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
