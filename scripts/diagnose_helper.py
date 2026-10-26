# -*- coding: utf-8 -*-
"""Read-only, target-scoped diagnostics; never captures or operates windows."""
import argparse
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', choices=['Codex', 'WorkBuddy'], default='WorkBuddy')
    parser.add_argument('--install-root', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'assets' / 'helper')
    args = parser.parse_args()
    sys.path.insert(0, str(args.install_root.resolve()))
    import screenshot_win32 as win
    win.enable_dpi()
    process = 'workbuddy.exe' if args.target == 'WorkBuddy' else None
    targets, helpers = [], []
    for hwnd in win.all_windows():
        title = win.window_title(hwnd)
        if title == f'{args.target} 截图助手':
            helpers.append(dict(hwnd=hwnd, pid=win.window_pid(hwnd), rect=win.window_rect(hwnd),
                                visible=bool(win.U.IsWindowVisible(hwnd))))
        elif args.target.lower() in title.lower() or (args.target == 'Codex' and title == 'ChatGPT'):
            name = win.process_name(win.window_pid(hwnd))
            if name not in ((process,) if process else ('chatgpt.exe', 'codex.exe')):
                continue
            rect = win.window_rect(hwnd)
            minimized = bool(win.U.IsIconic(hwnd))
            target = dict(hwnd=hwnd, rect=rect, minimized=minimized,
                          visible=bool(win.U.IsWindowVisible(hwnd)))
            if rect and not minimized:
                target['work_area'] = win.monitor_work_area(rect)
            targets.append(target)
    for helper in helpers:
        rect = helper['rect']
        helper['inside_a_target_window'] = bool(rect and any(
            not target['minimized'] and target['rect'] and
            target['rect'][0] <= rect[0] and target['rect'][1] <= rect[1] and
            rect[2] <= target['rect'][2] and rect[3] <= target['rect'][3]
            for target in targets))
    print(json.dumps(dict(target=args.target, install_root=str(args.install_root.resolve()),
                          foreground=win.U.GetForegroundWindow(),
                          target_windows=targets, helper_windows=helpers), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
