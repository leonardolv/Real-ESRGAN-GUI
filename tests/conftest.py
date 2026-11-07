"""Pytest configuration and global patches."""

import os
import sys

# Ensure TCL_LIBRARY and TK_LIBRARY are set properly for Windows virtual environments
# Forward slashes prevent Tcl's interpreter from wrapping Windows paths in curly braces
tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6").replace("\\", "/")
tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6").replace("\\", "/")
if os.path.isdir(tcl_dir):
    os.environ["TCL_LIBRARY"] = tcl_dir
if os.path.isdir(tk_dir):
    os.environ["TK_LIBRARY"] = tk_dir

# Increase stdio file descriptor limit on Windows to prevent C fopen exhaustions during repeated Tcl/Tk loads
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.cdll.msvcrt._setmaxstdio(2048)
    except Exception:
        pass

# Patch torchvision for basicsr compatibility on newer PyTorch/Torchvision versions
try:
    import torchvision.transforms.functional as tv_f
    sys.modules["torchvision.transforms.functional_tensor"] = tv_f
except ImportError:
    pass
