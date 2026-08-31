"""Model manager — discovery, download, and registry for Real-ESRGAN weights.

Maps the six official models to their network architectures, download URLs,
and metadata.  Scans the ``weights/`` directory on startup and reports which
models are already available.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional



ROOT_DIR = Path(__file__).resolve().parent.parent.parent  # project root
WEIGHTS_DIR = ROOT_DIR / "weights"


@dataclass
class ModelInfo:
    """Metadata for a single Real-ESRGAN model."""

    name: str  # internal key, e.g. "RealESRGAN_x4plus"
    display_name: str  # human label for the dropdown
    category: str  # "General", "Anime", "Video"
    scale: int  # native upscale factor (2 or 4)
    description: str
    urls: List[str]  # download URLs (may be >1 for DNI models)
    arch: str  # "rrdb" or "srvgg"
    arch_params: dict = field(default_factory=dict)
    supports_denoise: bool = False
    downloaded: bool = False
    file_path: Optional[str] = None


# -------------------------------------------------------------------- #
#  Official model registry                                              #
# -------------------------------------------------------------------- #

_REGISTRY: List[ModelInfo] = [
    ModelInfo(
        name="RealESRGAN_x4plus",
        display_name="RealESRGAN x4plus",
        category="General",
        scale=4,
        description="Best quality for real-world photos. Large 23-block RRDB network.",
        urls=["https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"],
        arch="rrdb",
        arch_params={"num_in_ch": 3, "num_out_ch": 3, "num_feat": 64, "num_block": 23, "num_grow_ch": 32, "scale": 4},
    ),
    ModelInfo(
        name="RealESRGAN_x2plus",
        display_name="RealESRGAN x2plus",
        category="General",
        scale=2,
        description="2× upscale model for general images.",
        urls=["https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.1/RealESRGAN_x2plus.pth"],
        arch="rrdb",
        arch_params={"num_in_ch": 3, "num_out_ch": 3, "num_feat": 64, "num_block": 23, "num_grow_ch": 32, "scale": 2},
    ),
    ModelInfo(
        name="RealESRNet_x4plus",
        display_name="RealESRNet x4plus",
        category="General",
        scale=4,
        description="MSE-trained variant — smoother results, less artifacts.",
        urls=["https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.1/RealESRNet_x4plus.pth"],
        arch="rrdb",
        arch_params={"num_in_ch": 3, "num_out_ch": 3, "num_feat": 64, "num_block": 23, "num_grow_ch": 32, "scale": 4},
    ),
    ModelInfo(
        name="realesr-general-x4v3",
        display_name="General v3 (Compact)",
        category="General",
        scale=4,
        description="Tiny model (~6 MB). Fast, low VRAM. Supports denoise strength.",
        urls=[
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-wdn-x4v3.pth",
        ],
        arch="srvgg",
        arch_params={"num_in_ch": 3, "num_out_ch": 3, "num_feat": 64, "num_conv": 32, "upscale": 4, "act_type": "prelu"},
        supports_denoise=True,
    ),
    ModelInfo(
        name="RealESRGAN_x4plus_anime_6B",
        display_name="Anime 6B",
        category="Anime",
        scale=4,
        description="Optimized for anime images / illustrations. 6 RRDB blocks.",
        urls=["https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.2.4/RealESRGAN_x4plus_anime_6B.pth"],
        arch="rrdb",
        arch_params={"num_in_ch": 3, "num_out_ch": 3, "num_feat": 64, "num_block": 6, "num_grow_ch": 32, "scale": 4},
    ),
    ModelInfo(
        name="realesr-animevideov3",
        display_name="Anime Video v3",
        category="Video",
        scale=4,
        description="Compact model for anime video frames. Very fast.",
        urls=["https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth"],
        arch="srvgg",
        arch_params={"num_in_ch": 3, "num_out_ch": 3, "num_feat": 64, "num_conv": 16, "upscale": 4, "act_type": "prelu"},
    ),
]


class ModelManager:
    """Manages model discovery, downloading, and instantiation."""

    def __init__(self, weights_dir: Path | None = None):
        self.weights_dir = weights_dir or WEIGHTS_DIR
        self.weights_dir.mkdir(parents=True, exist_ok=True)
        self._models: Dict[str, ModelInfo] = {}
        for info in _REGISTRY:
            self._models[info.name] = ModelInfo(**info.__dict__)  # copy
        self.refresh()

    # ------------------------------------------------------------------ #
    #  Discovery                                                          #
    # ------------------------------------------------------------------ #

    def refresh(self) -> None:
        """Scan weights dir and update download status of each model."""
        for model in self._models.values():
            pth_path = self.weights_dir / f"{model.name}.pth"
            if pth_path.is_file():
                model.downloaded = True
                model.file_path = str(pth_path)
            else:
                model.downloaded = False
                model.file_path = None

    # ------------------------------------------------------------------ #
    #  Queries                                                            #
    # ------------------------------------------------------------------ #

    def list_all(self) -> List[ModelInfo]:
        """Return all registered models."""
        return list(self._models.values())

    def list_by_category(self, category: str) -> List[ModelInfo]:
        """Return models filtered by category."""
        return [m for m in self._models.values() if m.category == category]

    def get(self, name: str) -> Optional[ModelInfo]:
        """Get model info by internal name."""
        return self._models.get(name)

    def categories(self) -> List[str]:
        """Return sorted unique category names."""
        return sorted({m.category for m in self._models.values()})

    # ------------------------------------------------------------------ #
    #  Download                                                           #
    # ------------------------------------------------------------------ #

    def download_model(
        self,
        name: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
    ) -> str:
        """Download model weights if not already present.

        Args:
            name: Internal model name.
            progress_callback: Optional ``(status_text, fraction)`` callback.

        Returns:
            Path to the downloaded ``.pth`` file.
        """
        model = self._models.get(name)
        if model is None:
            raise ValueError(f"Unknown model: {name}")

        if model.downloaded and model.file_path:
            return model.file_path

        from basicsr.utils.download_util import load_file_from_url

        if progress_callback:
            progress_callback(f"Downloading {model.display_name}…", 0.0)

        model_path = None
        for i, url in enumerate(model.urls):
            model_path = load_file_from_url(
                url=url,
                model_dir=str(self.weights_dir),
                progress=True,
                file_name=None,
            )
            if progress_callback:
                frac = (i + 1) / len(model.urls)
                progress_callback(f"Downloading {model.display_name}…", frac)

        self.refresh()
        return model_path or ""

    # ------------------------------------------------------------------ #
    #  Model instantiation helpers                                        #
    # ------------------------------------------------------------------ #

    def build_network(self, name: str):
        """Instantiate the PyTorch network (nn.Module) for a model.

        Returns the *unloaded* network — weights are loaded by RealESRGANer.
        """
        model = self._models.get(name)
        if model is None:
            raise ValueError(f"Unknown model: {name}")

        if model.arch == "rrdb":
            from basicsr.archs.rrdbnet_arch import RRDBNet
            return RRDBNet(**model.arch_params)
        elif model.arch == "srvgg":
            from realesrgan.archs.srvgg_arch import SRVGGNetCompact
            return SRVGGNetCompact(**model.arch_params)
        else:
            raise ValueError(f"Unknown architecture: {model.arch}")

    def get_model_path(self, name: str) -> str | List[str]:
        """Return the weight file path(s) for a model.

        For DNI models (realesr-general-x4v3) when denoise_strength != 1,
        two paths are returned.
        """
        model = self._models.get(name)
        if model is None:
            raise ValueError(f"Unknown model: {name}")
        pth = self.weights_dir / f"{model.name}.pth"
        return str(pth)
