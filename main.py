#!/usr/bin/env python
"""Launch the Real-ESRGAN GUI application."""

import os
import sys
import logging

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Prevent OpenMP/MKL thread deadlocks when using PyTorch CPU inference on Windows
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

# Setup basic logging early so startup issues are recorded
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("realesrgan_gui.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        return
    logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

sys.excepthook = handle_exception

# Configure PyTorch and OpenCV threads
try:
    import torch
    if hasattr(torch, "set_num_threads"):
        torch.set_num_threads(1)
except Exception as e:
    logger.warning(f"Failed to configure PyTorch thread count: {e}")

try:
    import cv2
    if hasattr(cv2, "setNumThreads"):
        cv2.setNumThreads(0)
except Exception as e:
    logger.warning(f"Failed to configure OpenCV thread count: {e}")

# Patch torchvision for basicsr compatibility on newer PyTorch/torchvision versions
try:
    import torchvision.transforms.functional as tv_f
    sys.modules["torchvision.transforms.functional_tensor"] = tv_f
except ImportError:
    pass

from gui.app import RealESRGANApp

if __name__ == "__main__":
    logger.info("Starting Real-ESRGAN GUI application...")
    try:
        app = RealESRGANApp()
        app.mainloop()
    except KeyboardInterrupt:
        logger.info("Application closed by user interrupt.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Application crashed: {e}", exc_info=True)
        try:
            import tkinter.messagebox
            tkinter.messagebox.showerror(
                "Real-ESRGAN GUI Error",
                f"Application encountered an unexpected error:\n\n{e}\n\nPlease check 'realesrgan_gui.log' for details."
            )
        except Exception:
            pass
        sys.exit(1)
    logger.info("Application exited successfully.")
