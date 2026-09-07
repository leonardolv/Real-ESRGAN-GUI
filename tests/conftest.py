"""Pytest configuration and global patches."""

import os
import sys

# Ensure TCL_LIBRARY and TK_LIBRARY are set properly for Windows virtual environments
tcl_dir = os.path.join(sys.base_prefix, "tcl", "tcl8.6")
tk_dir = os.path.join(sys.base_prefix, "tcl", "tk8.6")
if os.path.isdir(tcl_dir) and "TCL_LIBRARY" not in os.environ:
    os.environ["TCL_LIBRARY"] = tcl_dir
if os.path.isdir(tk_dir) and "TK_LIBRARY" not in os.environ:
    os.environ["TK_LIBRARY"] = tk_dir

# Patch torchvision for basicsr compatibility on newer PyTorch/Torchvision versions
try:
    import torchvision.transforms.functional as tv_f
    sys.modules["torchvision.transforms.functional_tensor"] = tv_f
except ImportError:
    pass
