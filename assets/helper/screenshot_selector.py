# -*- coding: utf-8 -*-
"""Frozen-screen region / window selection UI."""
import tkinter as tk
from PIL import ImageEnhance, ImageTk
from screenshot_win32 import place_window, window_at

class RegionSelector(tk.Toplevel):
    def __init__(self, app, screenshot, origin, candidates):
        super().__init__(app.root)
        self.withdraw()
        self.title('截图区域选择')
        self.app, self.screenshot, self.origin = app, screenshot, origin
        self.candidates, self.start, self.current = candidates, None, None
        self.finished = False
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.geometry(f'{screenshot.width}x{screenshot.height}+0+0')
        self.canvas = tk.Canvas(self, bg='#19202a', highlightthickness=0, cursor='crosshair')
        self.canvas.pack(fill='both', expand=True)
        self.dim = ImageTk.PhotoImage(ImageEnhance.Brightness(screenshot).enhance(.48))
        self.canvas.create_image(0, 0, image=self.dim, anchor='nw')
        self.bright = None
        self.canvas.bind('<Motion>', self.on_motion)
        self.canvas.bind('<ButtonPress-1>', self.on_press)
        self.canvas.bind('<B1-Motion>', self.on_drag)
        self.canvas.bind('<ButtonRelease-1>', self.on_release)
        self.canvas.bind('<Button-3>', lambda _e: self.finish(None))
        self.bind('<Escape>', lambda _e: self.finish(None))
        self.protocol('WM_DELETE_WINDOW', lambda: self.finish(None))
        self.update_idletasks()
        self.deiconify()
        place_window(self, *origin, screenshot.width, screenshot.height)
        self.focus_force()
        self.draw_hint()

    def draw_hint(self):
        x = max(16, min(self.screenshot.width - 430, self.winfo_pointerx() - self.origin[0] - 170))
        y = max(16, min(self.screenshot.height - 50, self.winfo_pointery() - self.origin[1] + 36))
        self.canvas.create_rectangle(x, y, x + 410, y + 33, fill='#17212f', outline='', tags='hint')
        self.canvas.create_text(x + 12, y + 16, anchor='w', fill='white', font=('Microsoft YaHei UI', 10),
                                text='拖动框选 · 单击选取窗口 · Esc / 右键取消', tags='hint')

    def local_window(self, event):
        rect = window_at((event.x + self.origin[0], event.y + self.origin[1]), self.candidates)
        if rect:
            return rect[0] - self.origin[0], rect[1] - self.origin[1], rect[2] - self.origin[0], rect[3] - self.origin[1]

    def show_selection(self, rect):
        self.canvas.delete('selection')
        self.canvas.delete('hint')
        if not rect:
            self.current = None
            self.draw_hint()
            return
        l, t, r, b = rect
        rect = max(0, l), max(0, t), min(self.screenshot.width, r), min(self.screenshot.height, b)
        l, t, r, b = rect
        self.current = rect
        if r <= l or b <= t:
            return
        self.bright = ImageTk.PhotoImage(self.screenshot.crop(rect))
        self.canvas.create_image(l, t, image=self.bright, anchor='nw', tags='selection')
        self.canvas.create_rectangle(l + 1, t + 1, r - 1, b - 1, outline='#3094ff', width=2, tags='selection')
        label_y = t - 28 if t > 30 else t + 5
        label_x = max(0, min(l + 5, self.screenshot.width - 230))
        self.canvas.create_rectangle(label_x, label_y, label_x + 220, label_y + 25, fill='#17212f', outline='', tags='selection')
        self.canvas.create_text(label_x + 9, label_y + 12, anchor='w', fill='white', font=('Microsoft YaHei UI', 9),
                                text=f'{r - l} × {b - t}    Esc 取消', tags='selection')

    def on_motion(self, event):
        if self.start is None:
            rect = self.local_window(event)
            if rect != self.current:
                self.show_selection(rect)

    def on_press(self, event):
        self.start = event.x, event.y

    def on_drag(self, event):
        if self.start:
            x, y = self.start
            self.show_selection((min(x, event.x), min(y, event.y), max(x, event.x), max(y, event.y)))

    def on_release(self, event):
        if self.start is None:
            return
        x, y = self.start
        if abs(event.x - x) >= 4 and abs(event.y - y) >= 4:
            self.finish((min(x, event.x), min(y, event.y), max(x, event.x), max(y, event.y)))
        else:
            rect = self.local_window(event)
            if rect:
                self.finish(rect)
            else:
                self.start = None  # A click on desktop never captures the entire screen.

    def finish(self, rect):
        if not self.finished:
            self.finished = True
            self.destroy()
            self.app.selector = None
            self.app.complete_capture(self.screenshot, rect)
