# -*- coding: utf-8 -*-
"""WorkBuddy 伴随截图浮层。复用与 Codex 相同的截图和自动附图流程。"""
import ctypes
import logging
from pathlib import Path
import sys

from codex_screenshot_overlay import APP_DIR, OverlayApp
from screenshot_win32 import (K, enable_dpi, find_workbuddy_window, restore_watchdog,
                              clamp_toolbar_position, monitor_work_area)


class WorkBuddyOverlay(OverlayApp):
    target_label = 'WorkBuddy'
    config_path = APP_DIR / 'workbuddy_screenshot_overlay.json'
    capture_dir = APP_DIR / 'workbuddy-captures'
    capture_prefix = 'workbuddy'
    launcher_path = Path(__file__).resolve()

    def find_target(self, preferred):
        return find_workbuddy_window(preferred)

    def get_toolbar_position(self, rect):
        # WorkBuddy's composer is vertically centered on its start/task screen.
        # This aligns immediately left of its model selector on the current 5.5.x layout.
        left, top, right, _bottom = rect
        scale = self.scale
        x = right - self.width - round(267 * scale) + round(self.settings.get('horizontal_adjust', 0) * scale)
        y = top + round(442 * scale) + round(self.settings.get('vertical_adjust', 0) * scale)
        # Saved drag offsets can exceed a resized window or a smaller monitor.
        # Keep the preferences, but constrain the displayed button to visible pixels.
        return clamp_toolbar_position((x, y), rect, (self.width, self.height),
                                      monitor_work_area(rect))


if __name__ == '__main__':
    enable_dpi()
    if len(sys.argv) == 4 and sys.argv[1] == '--watch-parent':
        restore_watchdog(int(sys.argv[2]), int(sys.argv[3]))
    else:
        mutex = K.CreateMutexW(None, False, 'Local\\WorkBuddyScreenshotOverlay-v1')
        if ctypes.get_last_error() != 183:
            logging.basicConfig(filename=APP_DIR/'workbuddy-overlay.log', encoding='utf-8', level=logging.ERROR)
            try:
                WorkBuddyOverlay().run()
            finally:
                if mutex:
                    K.CloseHandle(mutex)
