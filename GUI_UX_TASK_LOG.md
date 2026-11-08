# GUI & UX Maintenance Log



## In Progress

## Completed

### Task: RealESRGANApp fullscreen, queue triggers, upscale actions, settings accessors, and unit tests
- **Completed**: 2026-11-07
- **Changes**:
  - `gui/app.py`:
    - Added fullscreen query and toggle trigger: `is_fullscreen()`, `trigger_toggle_fullscreen()`.
    - Added queue triggers: `trigger_delete_selected()`, `trigger_clear_queue()`.
    - Added upscale triggers: `trigger_upscale()`, `trigger_process_all()`.
    - Exposed settings accessors: `denoise_strength()`, `output_extension()`.
    - Standardized GPU status text formatting with standard hyphen.
  - `gui/widgets/queue_panel.py`:
    - Added `add_item(item: QueueItem)` helper.
  - `tests/test_gui.py`:
    - Added unit test `test_real_esrgan_app_fullscreen_and_action_triggers`.
- **Verification**: Verified headlessly with `python -m pytest tests/ -v` (42 passed, 3 skipped in 14.96s, 0 errors).
- **Status**: Completed



