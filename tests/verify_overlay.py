# -*- coding: utf-8 -*-
"""Focused checks for the packaged helper; never changes the clipboard or target apps."""
import ctypes
import io
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace as Event
from unittest.mock import patch, Mock
from PIL import Image, BmpImagePlugin

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets' / 'helper'))
import screenshot_win32 as win
import codex_screenshot_overlay as main
from screenshot_selector import RegionSelector
from screenshot_settings import SettingsPopup
from workbuddy_screenshot_overlay import WorkBuddyOverlay


class WorkBuddyPositionTests(unittest.TestCase):
    def test_saved_drag_offset_stays_inside_resized_window(self):
        app = Event(width=76, height=30, scale=1,
                    settings={'horizontal_adjust': -506., 'vertical_adjust': 569.})
        rect = (26, 201, 1315, 954)
        with patch('workbuddy_screenshot_overlay.monitor_work_area', return_value=(0, 0, 1920, 1050)):
            self.assertEqual(WorkBuddyOverlay.get_toolbar_position(app, rect), (466, 924))

    def test_default_model_spacing_is_preserved(self):
        app = Event(width=76, height=30, scale=1, settings={})
        with patch('workbuddy_screenshot_overlay.monitor_work_area', return_value=(0, 0, 1920, 1050)):
            self.assertEqual(WorkBuddyOverlay.get_toolbar_position(app, (308, 100, 1508, 900)), (1165, 542))

    def test_dpi_and_extreme_offsets(self):
        app = Event(width=152, height=60, scale=2,
                    settings={'horizontal_adjust': 9000., 'vertical_adjust': -9000.})
        with patch('workbuddy_screenshot_overlay.monitor_work_area', return_value=(0, 0, 1920, 1050)):
            self.assertEqual(WorkBuddyOverlay.get_toolbar_position(app, (20, 30, 1800, 1000)), (1648, 30))

    def test_partly_offscreen_window_on_negative_monitor(self):
        self.assertEqual(win.clamp_toolbar_position((-2500, 2000), (-2200, -100, -200, 1200),
                                                    (76, 30), (-1920, 0, 0, 1040)), (-1920, 1010))


class SettingsFocusTests(unittest.TestCase):
    def test_external_focus_closes_even_without_mouse_press(self):
        popup = Mock(hwnd=101)
        popup.winfo_ismapped.return_value = True
        with patch('screenshot_settings.U.GetForegroundWindow', return_value=202):
            SettingsPopup._check_focus(popup)
        popup.unpost.assert_called_once()

    def test_focus_inside_settings_keeps_menu_open(self):
        popup = Mock(hwnd=101)
        popup.winfo_ismapped.return_value = True
        with patch('screenshot_settings.U.GetForegroundWindow', return_value=101):
            SettingsPopup._check_focus(popup)
        popup.unpost.assert_not_called()

    def test_close_withdraws_and_cancels_pending_watch(self):
        popup = Mock(watch_timer='timer1')
        self.assertEqual(SettingsPopup.unpost(popup), 'break')
        popup.after_cancel.assert_called_once_with('timer1')
        popup.withdraw.assert_called_once()
        self.assertIsNone(popup.watch_timer)


class OverlayTests(unittest.TestCase):
    def test_position_tracks_centered_composer_and_bottom(self):
        settings = dict(anchor='composer', horizontal_adjust=0, bottom_gap=23, right_gap=408)
        a = win.toolbar_position((182, 57, 1542, 968), (76, 30), settings, 1)
        b = win.toolbar_position((182, 57, 1742, 1168), (76, 30), settings, 1)
        self.assertEqual(b[0] - a[0], 100)
        self.assertEqual(b[1] - a[1], 200)
        self.assertEqual(a, (1060, 915))

    def test_selection_reverse_drag_window_click_and_empty_click(self):
        selector = object.__new__(RegionSelector)
        selector.origin = (-1920, 0)
        selector.candidates = [((-1900, 20, -1800, 120), 'test')]
        completed = []
        selector.finish = completed.append
        selector.start = (150, 150)
        selector.on_release(Event(x=50, y=30))
        self.assertEqual(completed.pop(), (50, 30, 150, 150))
        selector.start = (25, 25)
        selector.on_release(Event(x=26, y=25))
        self.assertEqual(completed.pop(), (20, 20, 120, 120))

    def test_clipboard_dib_roundtrip_real_x64_memory(self):
        source = Image.new('RGB', (3, 2))
        source.putdata([(255, 0, 0), (0, 255, 0), (0, 0, 255), (1, 2, 3), (4, 5, 6), (7, 8, 9)])
        captured = []
        def record(_format, handle):
            pointer = win.K.GlobalLock(handle)
            try:
                captured.append((handle, ctypes.string_at(pointer, len(win.image_dib(source)))))
            finally:
                win.K.GlobalUnlock(handle)
            return handle
        fake = Event(OpenClipboard=lambda _: True, EmptyClipboard=lambda: True,
                     SetClipboardData=record, CloseClipboard=lambda: True)
        try:
            with patch.object(win, 'U', fake):
                win.set_clipboard_image(source, 1)
            decoded = BmpImagePlugin.DibImageFile(io.BytesIO(captured[0][1])).convert('RGB')
            self.assertEqual(list(decoded.getdata()), list(source.getdata()))
        finally:
            for handle, _ in captured:
                win.K.GlobalFree(handle)

    def test_failed_hide_does_not_capture_visible_target(self):
        fake_dwm = Event(DwmSetWindowAttribute=lambda *args: 0, DwmFlush=lambda: None)
        fake_user = Event(ShowWindow=lambda *args: None, IsWindowVisible=lambda _: True)
        with patch.object(win, 'D', fake_dwm), patch.object(win, 'U', fake_user):
            with self.assertRaises(RuntimeError):
                win.hide_window_immediately(123)


if __name__ == '__main__':
    unittest.main(verbosity=2)
