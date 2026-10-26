# -*- coding: utf-8 -*-
"""Focusable settings popup shared by both screenshot helpers."""
import tkinter as tk
from screenshot_win32 import U, native_hwnd, place_window, virtual_bounds


class SettingsPopup(tk.Toplevel):
    def __init__(self, parent, title):
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.overrideredirect(True)
        self.attributes('-topmost', True)
        self.configure(bg='#dde1e7', padx=1, pady=1)
        self.hwnd = None
        self.watch_timer = None
        self.bind('<Escape>', self.unpost)
        self.bind('<FocusOut>', self._focus_out)

    def _add(self, widget_type, label, command, **options):
        def choose():
            self.unpost()
            command()
        widget = widget_type(self, text=label, command=choose, anchor='w',
                             bg='white', fg='#263244', activebackground='#e8f0fe',
                             activeforeground='#263244', relief='flat', bd=0,
                             padx=12, pady=6, font=('Microsoft YaHei UI', 10),
                             **options)
        widget.pack(fill='x')
        widget.bind('<Enter>', lambda _e: widget.configure(bg='#e8f0fe'))
        widget.bind('<Leave>', lambda _e: widget.configure(bg='white'))

    def add_radiobutton(self, **options):
        self._add(tk.Radiobutton, **options)

    def add_checkbutton(self, **options):
        self._add(tk.Checkbutton, **options)

    def add_command(self, **options):
        self._add(tk.Button, **options)

    def add_separator(self):
        tk.Frame(self, height=1, bg='#dde1e7').pack(fill='x')

    def popup(self, x, bottom):
        self.update_idletasks()
        width, height = self.winfo_reqwidth(), self.winfo_reqheight()
        left, top, right, screen_bottom = virtual_bounds()
        x = max(left, min(x, right-width))
        y = max(top, min(bottom-height, screen_bottom-height))
        place_window(self, x, y, width, height)
        self.deiconify()
        self.update_idletasks()
        self.hwnd = native_hwnd(self)
        # The toolbar deliberately has WS_EX_NOACTIVATE; the settings must not.
        style = U.GetWindowLongW(self.hwnd, -20)
        U.SetWindowLongW(self.hwnd, -20, (style | 0x80) & ~0x08000000)
        U.SetForegroundWindow(self.hwnd)
        self.focus_force()
        self._watch_focus()

    def _focus_out(self, _event):
        # Moving focus between buttons is not leaving the settings window.
        self.after_idle(self._check_focus)

    def _check_focus(self):
        if self.winfo_ismapped() and U.GetForegroundWindow() != self.hwnd:
            self.unpost()

    def _watch_focus(self):
        self.watch_timer = None
        self._check_focus()
        if self.winfo_ismapped():
            self.watch_timer = self.after(50, self._watch_focus)

    def unpost(self, _event=None):
        if self.watch_timer is not None:
            self.after_cancel(self.watch_timer)
            self.watch_timer = None
        self.withdraw()
        return 'break'
