# GUI & UX Maintenance Log

## In Progress

## Blocked / Needs Review

## Completed
- [x] **Headless Test Suite & Cross-Platform Windows GUI/UX Hardening**
  - Added comprehensive headless test suite `tests/test_gui.py` covering `Config`, `ImageUtils`, `ModelManager`, `UpscaleJob`, `UpscaleController`, and CustomTkinter widgets (`SettingsPanel`, `ProgressPanel`, `QueuePanel`).
  - Fixed Windows path backslash matching in `tests/test_dataset.py`.
  - Added CUDA availability skips for GPU-only tests in `tests/test_model.py` and pretrained weight checks in `tests/test_utils.py`.
  - Hardened window geometry persistence in `gui/app.py` against multi-monitor setups with negative coordinates.
  - Added video file handling and preview integrations in `preview_canvas.py` and `app.py`.
  - Ensured all tests execute non-interactively with 100% pass/skip rate (12 passed, 3 skipped, 0 failures).

## Backlog
- [ ] Add batch drag-and-drop progress cancellation tests.

