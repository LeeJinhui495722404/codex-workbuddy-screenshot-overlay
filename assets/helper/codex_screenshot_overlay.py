# -*- coding: utf-8 -*-
"""Codex 截图伴随浮层。图片只保存到本地、复制到剪贴板，由用户粘贴。"""
import atexit
import ctypes
from datetime import datetime
import json
import logging
import os
import queue
import shutil
from pathlib import Path
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from PIL import ImageGrab
from screenshot_selector import RegionSelector
from screenshot_settings import SettingsPopup
from screenshot_win32 import (U, K, D, enable_dpi, find_codex_window, window_rect,
    native_hwnd, place_window, toolbar_position, window_pid, virtual_bounds,
    window_candidates, set_clipboard_image, restore_watchdog, hide_window_immediately)

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / 'codex_screenshot_overlay.json'
CAPTURE_DIR = APP_DIR / 'captures'

class OverlayApp:
    target_label = 'Codex'
    config_path = CONFIG_PATH
    capture_dir = CAPTURE_DIR
    capture_prefix = 'codex'
    launcher_path = Path(__file__).resolve()

    def find_target(self, preferred):
        return find_codex_window(preferred)

    def get_toolbar_position(self, rect):
        return toolbar_position(rect, (self.width, self.height), self.settings, self.scale)

    def __init__(self):
        self.settings = self.load_settings()
        self.codex_hwnd = self.hidden_codex_hwnd = None
        self.capturing = False
        self.attaching = False
        self.attach_results = queue.Queue()
        self.drag_offset = self.selector = self.tooltip = self.tip_timer = None
        self.scale, self.last_lookup, self.last_rect = 1., 0, None
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title(f'{self.target_label} 截图助手')
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.attributes('-transparentcolor', '#ff00ff')
        self.root.report_callback_exception = self.callback_error
        self.mode_var = tk.BooleanVar(value=self.settings['hide_codex'])
        self.menu = SettingsPopup(self.root, f'{self.target_label} 截图设置')
        self.menu.add_radiobutton(label=f'隐藏 {self.target_label} 后截图', variable=self.mode_var, value=True, command=self.change_default)
        self.menu.add_radiobutton(label=f'保留 {self.target_label} 界面截图', variable=self.mode_var, value=False, command=self.change_default)
        self.auto_attach_var = tk.BooleanVar(value=self.settings['auto_attach'])
        self.menu.add_checkbutton(label='截图后自动添加到输入框', variable=self.auto_attach_var, command=self.change_auto_attach)
        self.menu.add_separator()
        self.menu.add_command(label='重置到模型栏附近', command=self.reset_position)
        self.menu.add_command(label='切换浅色 / 深色外观', command=self.toggle_theme)
        self.menu.add_command(label='打开截图文件夹', command=self.open_capture_folder)
        self.menu.add_separator()
        self.menu.add_command(label='退出截图助手', command=self.quit)
        self.canvas = tk.Canvas(self.root, highlightthickness=0, bg='#ff00ff')
        self.canvas.pack()
        self.canvas.bind('<Motion>', self.hover)
        self.canvas.bind('<Leave>', lambda _e: self.hide_tip())
        self.canvas.bind('<ButtonPress-1>', self.press)
        self.canvas.bind('<B1-Motion>', self.drag)
        self.canvas.bind('<ButtonRelease-1>', self.release)
        self.build_toolbar()
        self.root.update_idletasks()
        self.hwnd = native_hwnd(self.root)
        U.SetWindowLongW(self.hwnd, -20, U.GetWindowLongW(self.hwnd, -20) | 0x80 | 0x08000000)
        atexit.register(self.restore_target)
        self.track_codex()

    def load_settings(self):
        defaults = dict(version=2, hide_codex=True, right_gap=408., bottom_gap=23., theme='light',
                        anchor='composer', horizontal_adjust=0., vertical_adjust=0., auto_attach=True)
        try:
            saved = json.loads(self.config_path.read_text(encoding='utf-8-sig'))
            if not isinstance(saved, dict):
                return defaults
            if isinstance(saved.get('hide_codex'), bool):
                defaults['hide_codex'] = saved['hide_codex']
            if isinstance(saved.get('auto_attach'), bool):
                defaults['auto_attach'] = saved['auto_attach']
            if saved.get('version') == 2:
                for key in ('right_gap', 'bottom_gap'):
                    if isinstance(saved.get(key), (int, float)) and 0 <= saved[key] <= 10000:
                        defaults[key] = saved[key]
                if saved.get('theme') in {'light', 'dark'}:
                    defaults['theme'] = saved['theme']
                if saved.get('anchor') in {'composer', 'window'}:
                    defaults['anchor'] = saved['anchor']
                if isinstance(saved.get('horizontal_adjust'), (int, float)) and abs(saved['horizontal_adjust']) < 10000:
                    defaults['horizontal_adjust'] = saved['horizontal_adjust']
                if isinstance(saved.get('vertical_adjust'), (int, float)) and abs(saved['vertical_adjust']) < 10000:
                    defaults['vertical_adjust'] = saved['vertical_adjust']
        except (OSError, ValueError):
            pass
        return defaults

    def save_settings(self):
        tmp = self.config_path.with_suffix('.json.tmp')
        tmp.write_text(json.dumps(self.settings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(self.config_path)

    def build_toolbar(self):
        s = self.scale
        self.width, self.height = round(76*s), round(30*s)
        self.canvas.configure(width=self.width, height=self.height)
        self.canvas.delete('all')
        dark = self.settings['theme'] == 'dark'
        bg, fg, border = ('#25282d', '#eef0f3', '#464b53') if dark else ('#ffffff', '#515966', '#dde1e7')
        def xy(points):
            return [v*s for v in points]
        self.canvas.create_polygon(xy([8,1,68,1,75,1,75,8,75,22,75,29,68,29,8,29,1,29,1,22,1,8,1,1]),
                                   smooth=True, splinesteps=24, fill=bg, outline=border)
        for x in (7,11):
            for y in (11,15,19):
                self.canvas.create_oval(*xy([x-.6,y-.6,x+.6,y+.6]), fill='#a3abb7', outline='')
        self.canvas.create_line(*xy([54,7,54,23]), fill=border)
        self.canvas.create_line(*xy([24,10,28,10,30,7,37,7,39,10,43,10,43,22,24,22,24,10]),
                                fill=fg, width=max(1,round(1.4*s)), joinstyle='round')
        self.canvas.create_oval(*xy([29,12,38,21]), outline=fg, width=max(1,round(1.4*s)))
        self.canvas.create_line(*xy([61,13,65,17,69,13]), fill=fg, width=max(1,round(1.5*s)))

    def change_default(self):
        self.settings['hide_codex'] = bool(self.mode_var.get())
        self.save_settings()

    def change_auto_attach(self):
        self.settings['auto_attach'] = bool(self.auto_attach_var.get())
        self.save_settings()

    def toggle_theme(self):
        self.settings['theme'] = 'dark' if self.settings['theme'] == 'light' else 'light'
        self.save_settings()
        self.build_toolbar()

    def reset_position(self):
        self.settings.update(right_gap=408., bottom_gap=23., anchor='composer', horizontal_adjust=0., vertical_adjust=0.)
        self.save_settings()
        self.last_rect = None

    def close_menu(self, _event=None):
        self.menu.unpost()
        return 'break' if _event else None

    def hover(self, event):
        self.canvas.configure(cursor='fleur' if event.x < 17*self.scale else 'hand2')
        if self.tip_timer is None and self.tooltip is None:
            text = ('拖动调整位置' if event.x < 17*self.scale else '截图设置' if event.x >= 54*self.scale else
                    f'截图 · 隐藏 {self.target_label} 后框选' if self.settings['hide_codex'] else f'截图 · 保留 {self.target_label} 后框选')
            self.tip_timer = self.root.after(650, lambda: self.show_tip(text))

    def show_tip(self, text, timeout=None):
        self.hide_tip()
        if self.capturing or self.menu.winfo_ismapped() or not self.root.winfo_viewable():
            return
        self.tooltip = tk.Toplevel(self.root)
        self.tooltip.overrideredirect(True)
        self.tooltip.attributes('-topmost', True)
        tk.Label(self.tooltip, text=text, bg='#253144', fg='white', padx=10, pady=6,
                 font=('Microsoft YaHei UI', 9)).pack()
        self.tooltip.update_idletasks()
        place_window(self.tooltip, self.root.winfo_x(), self.root.winfo_y()-self.tooltip.winfo_height()-7)
        if timeout:
            self.tip_timer = self.root.after(timeout, self.hide_tip)

    def hide_tip(self):
        if self.tip_timer:
            self.root.after_cancel(self.tip_timer)
            self.tip_timer = None
        if self.tooltip:
            self.tooltip.destroy()
            self.tooltip = None

    def press(self, event):
        self.hide_tip()
        if event.x < 17*self.scale:
            self.drag_offset = event.x_root-self.root.winfo_x(), event.y_root-self.root.winfo_y()

    def drag(self, event):
        if self.drag_offset:
            place_window(self.root, event.x_root-self.drag_offset[0], event.y_root-self.drag_offset[1])

    def release(self, event):
        if self.drag_offset:
            self.drag_offset = None
            rect = window_rect(self.codex_hwnd)
            if rect:
                expected_x, expected_y = self.get_toolbar_position(rect)
                self.settings['horizontal_adjust'] += (self.root.winfo_x()-expected_x)/self.scale
                self.settings['vertical_adjust'] += (self.root.winfo_y()-expected_y)/self.scale
                self.settings['right_gap'] = max(0, (rect[2]-self.root.winfo_x()-self.width)/self.scale)
                self.settings['bottom_gap'] = max(0, (rect[3]-self.root.winfo_y()-self.height)/self.scale)
                self.save_settings()
                self.last_rect = None
        elif event.x >= 54*self.scale:
            self.hide_tip()
            if self.menu.winfo_ismapped():
                self.close_menu()
            else:
                self.menu.popup(self.root.winfo_x(), self.root.winfo_y())
        elif 17*self.scale <= event.x < 54*self.scale:
            self.begin_capture()

    def track_codex(self):
        try:
            self.poll_attach_result()
            if self.capturing:
                return
            now = time.monotonic()
            if now-self.last_lookup > 1. or not self.codex_hwnd:
                self.codex_hwnd = self.find_target(self.codex_hwnd)
                self.last_lookup = now
            foreground = U.GetForegroundWindow()
            active = foreground == self.codex_hwnd or window_pid(foreground) == os.getpid()
            rect = window_rect(self.codex_hwnd)
            if not rect or not active or not U.IsWindowVisible(self.codex_hwnd) or U.IsIconic(self.codex_hwnd):
                self.close_menu()
                self.hide_tip()
                self.root.withdraw()
                return
            scale = max(1., U.GetDpiForWindow(self.codex_hwnd)/96)
            if abs(scale-self.scale) > .01:
                self.scale = scale
                self.build_toolbar()
                self.root.update_idletasks()
                self.last_rect = None
            if not self.drag_offset:
                x,y = self.get_toolbar_position(rect)
                if not self.root.winfo_viewable():
                    self.root.deiconify()
                    self.last_rect = None
                if (x,y) != self.last_rect:
                    place_window(self.root, x,y,self.width,self.height)
                    self.last_rect = x,y
        finally:
            self.root.after(100, self.track_codex)

    def begin_capture(self):
        if self.attaching:
            self.show_tip('正在将上一张截图添加到输入框…', timeout=1800)
            return
        if self.capturing:
            return
        self.capturing = True
        self.close_menu()
        self.hide_tip()
        self.root.withdraw()
        self.root.update_idletasks()
        try:
            settle_ms = 60
            if self.settings['hide_codex'] and self.codex_hwnd and U.IsWindowVisible(self.codex_hwnd):
                self.hidden_codex_hwnd = self.codex_hwnd
                suppressed = hide_window_immediately(self.codex_hwnd)
                settle_ms = 80 if suppressed else 350
                subprocess.Popen([sys.executable,str(self.launcher_path),'--watch-parent',str(os.getpid()),str(self.codex_hwnd)],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
            D.DwmFlush()
            self.root.after(settle_ms, self.create_selector)  # Allow final desktop composition, no countdown.
        except Exception:
            self.restore_target()
            self.capturing = False
            raise

    def create_selector(self):
        try:
            if self.hidden_codex_hwnd and U.IsWindowVisible(self.hidden_codex_hwnd):
                raise RuntimeError(f'{self.target_label} 意外重新显示，本次截图已取消，请重试。')
            bounds = virtual_bounds()
            candidates = window_candidates({os.getpid()})
            screenshot = ImageGrab.grab(all_screens=True)
            self.selector = RegionSelector(self, screenshot, bounds[:2], candidates)
        except Exception:
            self.restore_target()
            self.capturing = False
            raise

    def restore_target(self):
        if self.hidden_codex_hwnd:
            hwnd, self.hidden_codex_hwnd = self.hidden_codex_hwnd, None
            if U.IsWindow(hwnd):
                U.ShowWindow(hwnd, 5)

    def complete_capture(self, screenshot, rect):
        self.restore_target()
        self.capturing = False
        if self.codex_hwnd and U.IsWindow(self.codex_hwnd):
            U.SetForegroundWindow(self.codex_hwnd)
        if rect is None:
            return
        l,t,r,b = rect
        rect = max(0,l),max(0,t),min(screenshot.width,r),min(screenshot.height,b)
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            return
        selected = screenshot.crop(rect)
        self.capture_dir.mkdir(exist_ok=True)
        output = self.capture_dir / (self.capture_prefix+'-capture-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.png')
        selected.save(output)
        try:
            set_clipboard_image(selected, self.hwnd)
            if self.settings['auto_attach']:
                self.start_auto_attach(U.GetClipboardSequenceNumber())
            else:
                self.root.after(180, lambda: self.show_tip('已复制截图 · 在输入框 Ctrl+V 粘贴', timeout=2500))
        except OSError as error:
            messagebox.showwarning('截图已保存', f'{output}\n\n{error}', parent=self.root)

    def start_auto_attach(self, sequence):
        self.attaching = True
        hwnd = self.codex_hwnd
        def worker():
            try:
                executable = shutil.which('pwsh.exe')
                if not executable and Path('C:/Program Files/PowerShell/7/pwsh.exe').is_file():
                    executable = 'C:/Program Files/PowerShell/7/pwsh.exe'
                if not executable:
                    raise RuntimeError('未找到 PowerShell 7，请在输入框 Ctrl+V 粘贴。')
                result = subprocess.run([executable, '-NoLogo', '-NoProfile', '-NonInteractive', '-STA',
                                         '-File', str(APP_DIR/'attach_capture.ps1'),
                                         '-TargetHwnd', str(hwnd), '-ClipboardSequence', str(sequence)],
                                        creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True,
                                        encoding='utf-8-sig', errors='replace', timeout=10)
                response = json.loads(result.stdout.strip())
                if result.returncode != 0 or not response.get('ok'):
                    raise RuntimeError(response.get('error', '自动附图未完成，请 Ctrl+V 粘贴。'))
                self.attach_results.put((True, '截图已添加到输入框 · 尚未发送'))
            except Exception as error:
                logging.warning('Auto-attach did not complete: %s', error)
                self.attach_results.put((False, '自动附图未完成 · 请在输入框 Ctrl+V 粘贴'))
        threading.Thread(target=worker, daemon=True).start()

    def poll_attach_result(self):
        try:
            _ok, message = self.attach_results.get_nowait()
        except queue.Empty:
            return
        self.attaching = False
        self.root.after(160, lambda: self.show_tip(message, timeout=3200))

    def open_capture_folder(self):
        self.capture_dir.mkdir(exist_ok=True)
        os.startfile(self.capture_dir)

    def callback_error(self, kind, value, traceback):
        logging.error('UI callback error', exc_info=(kind,value,traceback))
        self.restore_target()
        self.capturing = False
        if self.selector:
            self.selector.destroy()
            self.selector = None
        messagebox.showerror('截图助手', f'操作未完成：{value}\n可以重新尝试。', parent=self.root)

    def quit(self):
        self.restore_target()
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        finally:
            self.restore_target()

if __name__ == '__main__':
    enable_dpi()
    if len(sys.argv) == 4 and sys.argv[1] == '--watch-parent':
        restore_watchdog(int(sys.argv[2]), int(sys.argv[3]))
    else:
        mutex = K.CreateMutexW(None, False, 'Local\\CodexScreenshotOverlay-v2')
        if ctypes.get_last_error() != 183:
            logging.basicConfig(filename=APP_DIR/'overlay.log', encoding='utf-8', level=logging.ERROR)
            try:
                OverlayApp().run()
            finally:
                if mutex:
                    K.CloseHandle(mutex)
