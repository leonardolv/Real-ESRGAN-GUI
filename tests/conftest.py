"""Pytest configuration and global patches."""

import gc
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
def _apply_maxstdio():
    if sys.platform == "win32":
        for lib_name, limit in (("ucrtbase", 8192), ("msvcrt", 2048)):
            try:
                import ctypes
                lib = ctypes.CDLL(lib_name)
                lib._setmaxstdio(limit)
            except Exception:
                pass

_apply_maxstdio()

try:
    import pytest

    @pytest.fixture(autouse=True)
    def _isolate_config(tmp_path):
        from gui.utils import config as config_mod
        old = config_mod.CONFIG_FILE
        config_mod.CONFIG_FILE = tmp_path / "isolated_config.json"
        if os.path.isdir(tcl_dir):
            os.environ["TCL_LIBRARY"] = tcl_dir
        if os.path.isdir(tk_dir):
            os.environ["TK_LIBRARY"] = tk_dir
        _apply_maxstdio()
        yield
        config_mod.CONFIG_FILE = old

    @pytest.fixture(autouse=True)
    def _cleanup_tk():
        yield
        gc.collect()
except ImportError:
    pass

# Patch torchvision for basicsr compatibility on newer PyTorch/Torchvision versions
try:
    import torchvision.transforms.functional as tv_f
    sys.modules["torchvision.transforms.functional_tensor"] = tv_f
except ImportError:
    pass
