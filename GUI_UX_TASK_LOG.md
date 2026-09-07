# GUI & UX Maintenance Log

## In Progress

## Blocked / Needs Review

## Completed
- [x] **Fix App Startup Failure & Harden main.py Launch Pipeline** (2026-09-07)
  - Resolved startup crash (`AttributeError: module 'torch' has no attribute 'set_num_threads'`): cleared corrupted/conflicting PyTorch packages and OneDrive `-GALAXY` sync conflict files from `.venv\Lib\site-packages`.
  - Reinstalled clean PyTorch 2.5.1 with CUDA 12.1 acceleration (`torch==2.5.1+cu121`, `torchvision==0.20.1+cu121`) and `pytest`.
  - Created `tests/conftest.py` with global `torchvision.transforms.functional_tensor` compatibility patch for `basicsr`.
  - Hardened `main.py`: initialized logging early before heavy imports to capture startup tracebacks, guarded PyTorch/OpenCV thread setup, cleanly handled `KeyboardInterrupt` to avoid console traceback spam, and added GUI error modal fallback on unexpected crashes.
  - Verified with full test suite: 14 passed, 1 skipped, 0 failures in 68s.
- [x] **Headless Test Suite & Cross-Platform Windows GUI/UX Hardening**
  - Added comprehensive headless test suite `tests/test_gui.py` covering `Config`, `ImageUtils`, `ModelManager`, `UpscaleJob`, `UpscaleController`, and CustomTkinter widgets (`SettingsPanel`, `ProgressPanel`, `QueuePanel`).
  - Fixed Windows path backslash matching in `tests/test_dataset.py`.
  - Added CUDA availability skips for GPU-only tests in `tests/test_model.py` and pretrained weight checks in `tests/test_utils.py`.
  - Hardened window geometry persistence in `gui/app.py` against multi-monitor setups with negative coordinates.
  - Added video file handling and preview integrations in `preview_canvas.py` and `app.py`.
  - Ensured all tests execute non-interactively with 100% pass/skip rate (12 passed, 3 skipped, 0 failures).

## Backlog
- [ ] Add batch drag-and-drop progress cancellation tests.

