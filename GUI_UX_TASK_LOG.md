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
- [x] **Batch Cancellation & Queue Context Menu Hardening** (2026-09-07)
  - Added queue context menu actions (Open File, Show in File Explorer, Copy Path, Reset Status to Queued) in `gui/widgets/queue_panel.py`.
  - Added padding and denoise strength settings persistence in `gui/widgets/settings_panel.py`.
  - Refactored headless test suite fixture `ctk_root` with class-scoped reuse and per-test child widget cleanup to prevent Windows Tcl interpreter reinitialization crashes (`invalid command name "tcl_findLibrary"`).
  - Added test coverage for batch execution cancellation (`test_batch_progress_and_cancellation`) and queue context menu status reset (`test_queue_panel_context_menu_and_status_reset`).
  - Verified with full test suite: 20 passed, 1 skipped, 0 failures.

- [x] **Drag-and-Drop Visual Indicator & Direct Queue Drop** (2026-09-07)
  - Added visual drag indicator border (`#3b82f6`) and drop banner (`⬇ Drop files here to add`) to `QueuePanel` when files are dragged over the queue.
  - Implemented `set_drag_highlight()`, `_on_drag_enter()`, `_on_drag_leave()`, and `_on_dnd_drop()` with safe OS path parsing and image/video format validation.
  - Connected `on_files_dropped` callback to `app._on_files_received` so dropping onto `QueuePanel` adds files to the queue and updates application state.
  - Added `pythonpath=.` to `setup.cfg` for seamless test module resolution.
  - Added automated test `test_queue_panel_drag_and_drop_visual_indicator` verifying drag enter, highlight activation, banner packing, drag leave, and drop event parsing.
  - Verified with full test suite: 21 passed, 1 skipped, 0 failures.
- [x] Add thumbnail preview tooltip on hover over completed queue items (2026-09-07)
  - Created reusable `ToolTip` and `ThumbnailToolTip` in `gui/widgets/tooltip.py` with 350ms ergonomic hover delay filter, automatic cancel on leave/click, and screen edge bound checking.
  - Added thumbnail rendering and lazy caching for completed upscaled results (capped at 150px) and source items via `PIL` and `ImageTk.PhotoImage`.
  - Added upscale metadata (dimensions and file size) to completed preview tooltips, and diagnostics formatting for error items.
  - Unified `Toolbar` tooltip usage by importing `ToolTip` from `gui.widgets.tooltip`.
  - Added robust tooltip lifecycle management (`_cleanup_tooltips()`, `destroy()`) in `QueuePanel` to cleanly destroy popup windows and cancel pending timers during item clearing, rebuilding, or window destruction.
  - Added automated unit test coverage in `tests/test_gui.py` (`test_tooltip_lifecycle`, `test_thumbnail_tooltip_completed_and_error`, `test_queue_panel_item_tooltip_integration`).
  - Verified with headless test suite: 19 passed, 0 failures in 5.02s.

## Backlog
- [ ] Add keyboard navigation (Up/Down arrow keys to select, Delete key to remove) in QueuePanel.
- [ ] Add estimated time remaining (ETA) calculation in ProgressPanel based on average item processing speed.

