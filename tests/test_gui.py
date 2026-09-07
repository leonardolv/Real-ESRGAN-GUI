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
from gui.widgets.tooltip import ToolTip, ThumbnailToolTip


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

    def test_upscale_job_with_item_index(self):
        job = UpscaleJob(
            input_path='input.png',
            output_path='output.png',
            model_name='RealESRGAN_x4plus',
            item_index=3,
        )
        assert job.item_index == 3

    def test_batch_progress_and_cancellation(self):
        mm = ModelManager()
        ctrl = UpscaleController(mm)
        job1 = UpscaleJob("in1.png", "out1.png", "RealESRGAN_x4plus", item_index=0)
        job2 = UpscaleJob("in2.png", "out2.png", "RealESRGAN_x4plus", item_index=1)

        # Signal cancellation
        ctrl.cancel()
        assert ctrl._cancelled() is True

        # Run batch with cancelled flag set
        ctrl._run_batch([job1, job2])
        messages = ctrl.poll()
        log_msgs = [m for m in messages if m.type == MsgType.LOG]
        assert any("cancelled" in str(m.data).lower() for m in log_msgs)


class TestGUIWidgetsHeadless:
    @pytest.fixture(scope="class")
    @classmethod
    def ctk_root(cls):
        root = ctk.CTk()
        root.withdraw()
        yield root
        try:
            root.destroy()
        except Exception:
            pass

    @pytest.fixture(autouse=True)
    def clean_root(self, ctk_root):
        yield
        for child in ctk_root.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    def test_widgets_instantiation_and_lifecycle(self, ctk_root, tmp_path):
        mm = ModelManager()
        # Settings panel
        settings = SettingsPanel(ctk_root, model_manager=mm)
        settings.pack()
        current_settings = settings.get_settings()
        assert 'model_name' in current_settings
        assert current_settings['outscale'] >= 1.0

        # Progress panel
        progress = ProgressPanel(ctk_root)
        progress.pack()
        progress.update_progress(0.75, "Processing 75%")
        ctk_root.update_idletasks()

        # Queue panel
        queue = QueuePanel(ctk_root)
        queue.pack()
        sample_img = tmp_path / "item.png"
        Image.new('RGB', (10, 10), color='red').save(sample_img)
        queue.add_files([str(sample_img)])
        items = queue.get_items()
        assert len(items) == 1
        assert items[0].status == ItemStatus.QUEUED

    def test_queue_panel_lifecycle_and_clear_callback(self, ctk_root, tmp_path):
        cleared = []
        queue = QueuePanel(ctk_root, on_queue_cleared=lambda: cleared.append(True))
        queue.pack()
        img1 = tmp_path / "img1.png"
        img2 = tmp_path / "img2.png"
        Image.new('RGB', (10, 10)).save(img1)
        Image.new('RGB', (10, 10)).save(img2)
        queue.add_files([str(img1), str(img2)])
        assert queue.count == 2
        assert len(cleared) == 0

        # Remove first item
        queue.remove(0)
        assert queue.count == 1
        assert len(cleared) == 0

        # Remove second item (queue becomes empty)
        queue.remove(0)
        assert queue.count == 0
        assert len(cleared) == 1

        # Add and clear
        queue.add_files([str(img1)])
        assert queue.count == 1
        queue.clear()
        assert queue.count == 0
        assert len(cleared) == 2

    def test_queue_panel_context_menu_and_status_reset(self, ctk_root, tmp_path):
        queue = QueuePanel(ctk_root)
        queue.pack()
        img = tmp_path / "reset_test.png"
        Image.new('RGB', (10, 10)).save(img)
        queue.add_files([str(img)])
        queue.update_item_status(0, ItemStatus.ERROR, 0.5)
        assert queue.get_items()[0].status == ItemStatus.ERROR

        # Reset status via update_item_status (as done by context menu option)
        queue.update_item_status(0, ItemStatus.QUEUED, 0)
        assert queue.get_items()[0].status == ItemStatus.QUEUED

    def test_settings_panel_padding_and_denoise(self, ctk_root):
        mm = ModelManager()
        settings = SettingsPanel(ctk_root, model_manager=mm)
        settings.pack()
        s = settings.get_settings()
        assert 'tile_pad' in s
        assert 'pre_pad' in s

        settings.load_settings({"tile_pad": 20, "pre_pad": 5})
        s2 = settings.get_settings()
        assert s2['tile_pad'] == 20
        assert s2['pre_pad'] == 5

    def test_toolbar_and_tooltip(self, ctk_root):
        from gui.widgets.toolbar import Toolbar
        toolbar = Toolbar(
            ctk_root,
            on_open=lambda: None,
            on_save=lambda: None,
            on_open_output=lambda: None,
        )
        toolbar.pack()
        assert toolbar._save_btn.cget("state") == "disabled"
        toolbar.set_save_enabled(True)
        assert toolbar._save_btn.cget("state") == "normal"

    def test_queue_panel_drag_and_drop_visual_indicator(self, ctk_root, tmp_path):
        dropped_files = []
        queue = QueuePanel(ctk_root, on_files_dropped=lambda files: dropped_files.extend(files))
        queue.pack()

        # Initially inactive
        assert not queue._is_drag_active
        assert queue.cget("border_color") == "#2b2b2b"

        # Drag enter activates indicator
        queue._on_drag_enter()
        assert queue._is_drag_active
        assert queue.cget("border_color") == "#3b82f6"
        assert queue._drop_banner.winfo_manager() == "pack"

        # Drag leave clears indicator
        queue._on_drag_leave()
        assert not queue._is_drag_active
        assert queue.cget("border_color") == "#2b2b2b"
        assert queue._drop_banner.winfo_manager() == ""

        # Drop files event
        img = tmp_path / "drop_test.png"
        Image.new('RGB', (10, 10)).save(img)

        class MockDndEvent:
            data = str(img)

        queue.set_drag_highlight(True)
        assert queue._is_drag_active
        queue._on_dnd_drop(MockDndEvent())
        assert not queue._is_drag_active
        assert queue.count == 1
        assert len(dropped_files) == 1
        assert dropped_files[0] == str(img)

    def test_tooltip_lifecycle(self, ctk_root):
        btn = ctk.CTkButton(ctk_root, text="Hover me")
        btn.pack()
        tip = ToolTip(btn, text="Helpful tip", delay_ms=50)
        assert tip.tip_window is None
        assert tip._after_id is None

        # Simulate enter
        tip._on_enter()
        assert tip._after_id is not None

        # Cancel timer on leave
        tip._on_leave()
        assert tip._after_id is None
        assert tip.tip_window is None

        # Show tip directly
        tip.show_tip()
        assert tip.tip_window is not None
        assert tip.tip_window.winfo_exists()

        # Hide tip
        tip.hide_tip()
        assert tip.tip_window is None
        tip.destroy()

    def test_thumbnail_tooltip_completed_and_error(self, ctk_root, tmp_path):
        out_img = tmp_path / "upscaled.png"
        Image.new("RGB", (64, 64), color="green").save(out_img)

        btn = ctk.CTkButton(ctk_root, text="Card")
        btn.pack()

        # Completed item thumbnail tooltip
        tip = ThumbnailToolTip(
            widget=btn,
            image_path=str(out_img),
            title="✓ Done: upscaled.png",
            details="Upscaled: 64 × 64 · 1 KB",
            delay_ms=50,
        )
        tip.show_tip()
        assert tip.tip_window is not None
        assert tip._cached_photo is not None
        tip.hide_tip()
        assert tip.tip_window is None
        tip.destroy()

        # Error diagnostic tooltip
        err_tip = ThumbnailToolTip(
            widget=btn,
            image_path="",
            title="✗ Failed: bad.png",
            error="Out of CUDA memory",
            delay_ms=50,
        )
        err_tip.show_tip()
        assert err_tip.tip_window is not None
        err_tip.hide_tip()
        assert err_tip.tip_window is None
        err_tip.destroy()

    def test_queue_panel_item_tooltip_integration(self, ctk_root, tmp_path):
        in_img = tmp_path / "input.png"
        Image.new("RGB", (32, 32), color="red").save(in_img)

        out_img = tmp_path / "output_upscaled.png"
        Image.new("RGB", (128, 128), color="green").save(out_img)

        queue = QueuePanel(ctk_root)
        queue.pack()
        queue.add_files([str(in_img)])

        # Queued item has tooltip
        assert len(queue._active_tooltips) == 1
        card_tip = queue._active_tooltips[0]
        assert isinstance(card_tip, ThumbnailToolTip)
        assert card_tip.title == f"Original: {in_img.name}"

        # Update to completed with output_path
        queue.update_item_status(0, ItemStatus.COMPLETED, 100.0, output_path=str(out_img))
        assert len(queue._active_tooltips) == 1
        completed_tip = queue._active_tooltips[0]
        assert isinstance(completed_tip, ThumbnailToolTip)
        assert "Done" in completed_tip.title
        assert "128" in completed_tip.details

        # Trigger show_tip
        completed_tip.show_tip()
        assert completed_tip.tip_window is not None

        # Clearing queue dismisses all tooltips
        queue.clear()
        assert len(queue._active_tooltips) == 0
        assert completed_tip.tip_window is None




