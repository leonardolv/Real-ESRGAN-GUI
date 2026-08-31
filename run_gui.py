#!/usr/bin/env python
"""Launch the Real-ESRGAN GUI application."""

import sys
import os

# Ensure project root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.app import RealESRGANApp

if __name__ == "__main__":
    app = RealESRGANApp()
    app.mainloop()
