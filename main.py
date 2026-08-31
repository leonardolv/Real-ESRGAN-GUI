#!/usr/bin/env python
"""Launch the Real-ESRGAN GUI application."""

import sys
import os

# Prevent OpenMP/MKL thread deadlocks when using PyTorch CPU inference on Windows
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import cv2
cv2.setNumThreads(0)
import torch
torch.set_num_threads(1)

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import RealESRGANApp

if __name__ == "__main__":
    app = RealESRGANApp()
    app.mainloop()
