import os
import sys
import tempfile
from pathlib import Path
from PIL import Image
import pytest
import customtkinter as ctk

from gui.utils.config import Config
from gui.utils.image_utils import (
    is_image_file,
    is_supported_file,
    generate_thumbnail,
    IMAGE_EXTENSIONS,
    VIDEO_EXTENSIONS,
)
from gui.controllers.model_manager import ModelManager
from gui.controllers.upscale_controller import UpscaleJob, UpscaleController, MsgType
from gui.widgets.queue_panel import QueuePanel, ItemStatus
from gui.widgets.settings_panel import SettingsPanel
from gui.widgets.progress_bar import ProgressPanel


class TestImageUtils:
    def test_image_extensions_detection(self):
        assert is_image_file('photo.png') is True
        assert is_image_file('photo.JPG') is True
        assert is_image_file('photo.webp') is True
        assert is_image_file('doc.pdf') is False
        assert is_image_file('script.py') is False

    def test_supported_extensions(self):
        assert is_supported_file('video.mp4') is True
        assert is_supported_file('clip.MKV') is True
        assert is_supported_file('image.png') is True
        assert is_supported_file('archive.zip') is False

    def test_generate_thumbnail(self, tmp_path):
        img_path = tmp_path / 'test_sample.png'
        img = Image.new('RGB', (200, 100), color='blue')
        img.save(img_path)

        thumb = generate_thumbnail(str(img_path), max_size=50)
        assert thumb is not None
        assert max(thumb.size) <= 50


class TestConfigManagement:
    def test_default_config(self):
        cfg = Config()
        assert cfg.get('last_model') == 'RealESRGAN_x4plus'
        assert cfg.get('last_scale') == 4.0
        assert cfg.get('last_tile') == 0
        assert cfg.get('theme') == 'system'

    def test_config_save_and_load(self, tmp_path):
        cfg_file = tmp_path / 'settings.json'
        cfg = Config(path=Path(cfg_file))
        cfg.set('last_model', 'RealESRNet_x4plus')
        cfg.set('last_scale', 2.0)

        loaded = Config(path=Path(cfg_file))
        assert loaded.get('last_model') == 'RealESRNet_x4plus'
        assert loaded.get('last_scale') == 2.0


class TestModelManager:
    def test_model_manager_initialization(self):
        mm = ModelManager()
        model_names = [m.name for m in mm.list_all()]
        assert 'RealESRGAN_x4plus' in model_names
        assert 'RealESRNet_x4plus' in model_names
        assert len(mm.categories()) > 0
        assert mm.weights_dir.exists()


class TestUpscaleControllerQueue:
    def test_upscale_job_creation(self):
        job = UpscaleJob(
            input_path='input.png',
            output_path='output.png',
            model_name='RealESRGAN_x4plus',
            outscale=4.0,
            denoise_strength=0.5,
            tile=0,
            face_enhance=False,
        )
        assert job.input_path == 'input.png'
        assert job.output_path == 'output.png'
        assert job.model_name == 'RealESRGAN_x4plus'
        assert job.tile == 0

    def test_controller_state(self):
        mm = ModelManager()
        ctrl = UpscaleController(mm)
        assert ctrl.is_busy is False


class TestGUIWidgetsHeadless:
    def test_widgets_instantiation_and_lifecycle(self, tmp_path):
        root = ctk.CTk()
        root.withdraw()
        try:
            mm = ModelManager()
            # Settings panel
            settings = SettingsPanel(root, model_manager=mm)
            settings.pack()
            current_settings = settings.get_settings()
            assert 'model_name' in current_settings
            assert current_settings['outscale'] >= 1.0

            # Progress panel
            progress = ProgressPanel(root)
            progress.pack()
            progress.update_progress(0.75, "Processing 75%")
            root.update_idletasks()

            # Queue panel
            queue = QueuePanel(root)
            queue.pack()
            sample_img = tmp_path / "item.png"
            Image.new('RGB', (10, 10), color='red').save(sample_img)
            queue.add_files([str(sample_img)])
            items = queue.get_items()
            assert len(items) == 1
            assert items[0].status == ItemStatus.QUEUED

        finally:
            root.destroy()

