# -*- coding: utf-8 -*-
"""Typed Windows API helpers for the screenshot overlay."""
import ctypes as C
from ctypes import wintypes as W
import io
import os
from pathlib import Path
import time

U = C.WinDLL('user32', use_last_error=True)
K = C.WinDLL('kernel32', use_last_error=True)
D = C.WinDLL('dwmapi')
ENUMPROC = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

class MONITORINFO(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('rcMonitor', W.RECT),
                ('rcWork', W.RECT), ('dwFlags', W.DWORD)]

def api(lib, name, args, result):
    fn = getattr(lib, name)
    fn.argtypes, fn.restype = args, result

for name, args, result in [
    ('EnumWindows', [ENUMPROC, W.LPARAM], W.BOOL),
    ('GetWindowRect', [W.HWND, C.POINTER(W.RECT)], W.BOOL),
    ('GetWindowTextLengthW', [W.HWND], C.c_int),
    ('GetWindowTextW', [W.HWND, W.LPWSTR, C.c_int], C.c_int),
    ('GetClassNameW', [W.HWND, W.LPWSTR, C.c_int], C.c_int),
    ('GetWindowThreadProcessId', [W.HWND, C.POINTER(W.DWORD)], W.DWORD),
    ('GetForegroundWindow', [], W.HWND), ('GetAncestor', [W.HWND, W.UINT], W.HWND),
    ('IsWindow', [W.HWND], W.BOOL), ('IsWindowVisible', [W.HWND], W.BOOL),
    ('IsIconic', [W.HWND], W.BOOL), ('ShowWindow', [W.HWND, C.c_int], W.BOOL),
    ('SetForegroundWindow', [W.HWND], W.BOOL), ('GetSystemMetrics', [C.c_int], C.c_int),
    ('GetDpiForWindow', [W.HWND], W.UINT),
    ('MonitorFromRect', [C.POINTER(W.RECT), W.DWORD], W.HANDLE),
    ('GetMonitorInfoW', [W.HANDLE, C.POINTER(MONITORINFO)], W.BOOL),
    ('SetProcessDpiAwarenessContext', [W.HANDLE], W.BOOL),
    ('SetWindowPos', [W.HWND, W.HWND, C.c_int, C.c_int, C.c_int, C.c_int, W.UINT], W.BOOL),
    ('GetWindowLongW', [W.HWND, C.c_int], W.LONG),
    ('SetWindowLongW', [W.HWND, C.c_int, W.LONG], W.LONG),
    ('OpenClipboard', [W.HWND], W.BOOL), ('CloseClipboard', [], W.BOOL),
    ('EmptyClipboard', [], W.BOOL), ('SetClipboardData', [W.UINT, W.HANDLE], W.HANDLE),
    ('GetClipboardSequenceNumber', [], W.DWORD),
]:
    api(U, name, args, result)
for name, args, result in [
    ('OpenProcess', [W.DWORD, W.BOOL, W.DWORD], W.HANDLE),
    ('QueryFullProcessImageNameW', [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)], W.BOOL),
    ('CloseHandle', [W.HANDLE], W.BOOL), ('GlobalAlloc', [W.UINT, C.c_size_t], W.HANDLE),
    ('GlobalLock', [W.HANDLE], C.c_void_p), ('GlobalUnlock', [W.HANDLE], W.BOOL),
    ('GlobalFree', [W.HANDLE], W.HANDLE),
    ('CreateMutexW', [C.c_void_p, W.BOOL, W.LPCWSTR], W.HANDLE),
    ('WaitForSingleObject', [W.HANDLE, W.DWORD], W.DWORD),
]:
    api(K, name, args, result)
api(D, 'DwmGetWindowAttribute', [W.HWND, W.DWORD, C.c_void_p, W.DWORD], C.c_long)
api(D, 'DwmSetWindowAttribute', [W.HWND, W.DWORD, C.c_void_p, W.DWORD], C.c_long)
api(D, 'DwmFlush', [], C.c_long)

def enable_dpi():
    U.SetProcessDpiAwarenessContext(C.c_void_p(-4))

def hide_window_immediately(hwnd):
    # SW_HIDE clears IsWindowVisible before DWM's fade-out has finished.
    # Suppress that one transition, then release the temporary override.
    # DWMWA_TRANSITIONS_FORCEDISABLED (3) is a setter-only BOOL attribute.
    disabled = W.BOOL(True)
    suppressed = D.DwmSetWindowAttribute(hwnd, 3, C.byref(disabled), C.sizeof(disabled)) == 0
    try:
        U.ShowWindow(hwnd, 0)
        D.DwmFlush()
    finally:
        if suppressed:
            enabled = W.BOOL(False)
            D.DwmSetWindowAttribute(hwnd, 3, C.byref(enabled), C.sizeof(enabled))
    if U.IsWindowVisible(hwnd):
        raise RuntimeError('Codex 窗口未能完全隐藏，本次截图已取消。')
    return suppressed

def window_pid(hwnd):
    pid = W.DWORD()
    U.GetWindowThreadProcessId(hwnd, C.byref(pid))
    return pid.value

def process_name(pid):
    handle = K.OpenProcess(0x1000, False, pid)
    if not handle:
        return ''
    try:
        size = W.DWORD(32768)
        buf = C.create_unicode_buffer(size.value)
        return Path(buf.value).name.lower() if K.QueryFullProcessImageNameW(handle, 0, buf, C.byref(size)) else ''
    finally:
        K.CloseHandle(handle)

def window_title(hwnd):
    buf = C.create_unicode_buffer(U.GetWindowTextLengthW(hwnd) + 1)
    U.GetWindowTextW(hwnd, buf, len(buf))
    return buf.value

def window_rect(hwnd, visible_frame=False):
    if not hwnd:
        return None
    rect = W.RECT()
    if visible_frame and D.DwmGetWindowAttribute(hwnd, 9, C.byref(rect), C.sizeof(rect)) == 0:
        return rect.left, rect.top, rect.right, rect.bottom
    if U.GetWindowRect(hwnd, C.byref(rect)):
        return rect.left, rect.top, rect.right, rect.bottom

def all_windows():
    result = []
    @ENUMPROC
    def callback(hwnd, _):
        result.append(hwnd)
        return True
    U.EnumWindows(callback, 0)
    return result

def find_window(preferred=None, process_names=('chatgpt.exe', 'codex.exe'), title_terms=('codex', 'chatgpt')):
    candidates, cache = [], {}
    for hwnd in all_windows():
        if not U.IsWindowVisible(hwnd) or U.IsIconic(hwnd):
            continue
        if not any(s in window_title(hwnd).lower() for s in title_terms):
            continue
        pid = window_pid(hwnd)
        if pid not in cache:
            cache[pid] = process_name(pid)
        if cache[pid] not in set(process_names):
            continue
        rect = window_rect(hwnd)
        if rect and rect[2] - rect[0] > 400 and rect[3] - rect[1] > 300:
            candidates.append(hwnd)
    foreground = U.GetForegroundWindow()
    return foreground if foreground in candidates else (preferred if preferred in candidates else (candidates[0] if candidates else None))

def find_codex_window(preferred=None):
    return find_window(preferred)

def find_workbuddy_window(preferred=None):
    return find_window(preferred, ('workbuddy.exe',), ('workbuddy',))

def virtual_bounds():
    x, y, w, h = [U.GetSystemMetrics(i) for i in (76, 77, 78, 79)]
    return x, y, x + w, y + h

def monitor_work_area(rect):
    """Use one real monitor's work area, excluding its taskbar and monitor gaps."""
    native_rect = W.RECT(*rect)
    monitor = U.MonitorFromRect(C.byref(native_rect), 2)  # MONITOR_DEFAULTTONEAREST
    info = MONITORINFO()
    info.cbSize = C.sizeof(info)
    if monitor and U.GetMonitorInfoW(monitor, C.byref(info)):
        area = info.rcWork
        return area.left, area.top, area.right, area.bottom
    return virtual_bounds()

def clamp_toolbar_position(position, rect, size, work_area):
    """Keep the whole toolbar inside the visible window/monitor intersection."""
    left, top = max(rect[0], work_area[0]), max(rect[1], work_area[1])
    right, bottom = min(rect[2], work_area[2]), min(rect[3], work_area[3])
    if right-left < size[0] or bottom-top < size[1]:
        left, top, right, bottom = work_area
    return (max(left, min(round(position[0]), right-size[0])),
            max(top, min(round(position[1]), bottom-size[1])))

def native_hwnd(widget):
    return U.GetAncestor(widget.winfo_id(), 2)

def place_window(widget, x, y, width=None, height=None):
    # Tk -x means offset from right; SetWindowPos supports real negative desktop coordinates.
    U.SetWindowPos(native_hwnd(widget), None, round(x), round(y), width or 0, height or 0,
                   0x0010 | 0x0004 | (0x0001 if width is None else 0))

def toolbar_position(rect, size, settings, scale):
    left, top, right, bottom = rect
    w, h = size
    if settings.get('anchor') == 'composer':
        content_left = left + min(275 * scale, (right-left)*.4)
        content_width = right-content_left
        composer_width = min(736 * scale, max(100 * scale, content_width-48*scale))
        # Match the centered composer; keep clear of the native busy indicator.
        composer_right = content_left + (content_width+composer_width)/2
        x = round(composer_right-(232-settings.get('horizontal_adjust', 0))*scale)-w
    else:
        x = right - round(settings['right_gap'] * scale) - w
    y = bottom - round(settings['bottom_gap'] * scale) - h + round(settings.get('vertical_adjust', 0) * scale)
    return max(left, min(x, right - w)), max(top, min(y, bottom - h))

def window_candidates(excluded_pids):
    # Snapshot Z-order before creating the selector, so the selector cannot select itself.
    result = []
    for hwnd in all_windows():
        if not U.IsWindowVisible(hwnd) or U.IsIconic(hwnd) or window_pid(hwnd) in excluded_pids:
            continue
        cloaked = W.DWORD()
        D.DwmGetWindowAttribute(hwnd, 14, C.byref(cloaked), C.sizeof(cloaked))
        if cloaked.value:
            continue
        cls = C.create_unicode_buffer(256)
        U.GetClassNameW(hwnd, cls, len(cls))
        if cls.value in {'Progman', 'WorkerW', 'Shell_TrayWnd', 'Shell_SecondaryTrayWnd', 'tooltips_class32'}:
            continue
        rect = window_rect(hwnd, True)
        if rect and rect[2] - rect[0] >= 40 and rect[3] - rect[1] >= 30:
            result.append((rect, window_title(hwnd)))
    return result

def window_at(point, candidates):
    x, y = point
    return next((r for r, _ in candidates if r[0] <= x < r[2] and r[1] <= y < r[3]), None)

def image_dib(image):
    stream = io.BytesIO()
    image.convert('RGB').save(stream, 'BMP')
    return stream.getvalue()[14:]

def set_clipboard_image(image, owner):
    payload = image_dib(image)
    handle = K.GlobalAlloc(0x0002, len(payload))
    if not handle:
        raise C.WinError(C.get_last_error())
    try:
        pointer = K.GlobalLock(handle)
        if not pointer:
            raise C.WinError(C.get_last_error())
        try:
            C.memmove(pointer, payload, len(payload))
        finally:
            K.GlobalUnlock(handle)
        for _ in range(10):
            if U.OpenClipboard(owner):
                try:
                    if not U.EmptyClipboard() or not U.SetClipboardData(8, handle):
                        raise C.WinError(C.get_last_error())
                    handle = None
                    return
                finally:
                    U.CloseClipboard()
            time.sleep(.03)
        raise OSError('剪贴板被占用；截图已保存，可稍后重试。')
    finally:
        if handle:
            K.GlobalFree(handle)

def restore_watchdog(parent_pid, hwnd):
    handle = K.OpenProcess(0x00100000, False, parent_pid)
    try:
        while U.IsWindow(hwnd) and not U.IsWindowVisible(hwnd):
            if not handle or K.WaitForSingleObject(handle, 200) == 0:
                U.ShowWindow(hwnd, 5)
                return
    finally:
        if handle:
            K.CloseHandle(handle)
