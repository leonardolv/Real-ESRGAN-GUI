"""Pytest configuration and global patches."""

import sys

# Patch torchvision for basicsr compatibility on newer PyTorch/Torchvision versions
try:
    import torchvision.transforms.functional as tv_f
    sys.modules["torchvision.transforms.functional_tensor"] = tv_f
except ImportError:
    pass
