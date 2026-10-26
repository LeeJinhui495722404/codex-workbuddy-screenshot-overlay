# 部署与排查

该 Skill 面向 Windows 10/11 当前用户。它不修改 Codex 或 WorkBuddy 的安装文件，而是在模型选择器旁显示独立顶置浮层。

## 前置条件

- 已安装 Codex Desktop、WorkBuddy，或两者之一。
- 可用 Python 3，并已安装 Pillow：`python -m pip install pillow`。
- 安装命令使用 PowerShell 7 (`pwsh`)；自动将截图附入输入框也需要 PowerShell 7。

安装器依次尝试指定的 `-PythonPath`、PATH 中的 `pythonw.exe` / `python.exe`，以及常见的 Conda 安装位置。运行下列命令可只安装一个平台，或指定 Python：

```powershell
pwsh -NoLogo -NoProfile -File .\scripts\Install-Screenshot-Helpers.ps1 -Target WorkBuddy
pwsh -NoLogo -NoProfile -File .\scripts\Install-Screenshot-Helpers.ps1 -PythonPath 'C:\Python312\pythonw.exe'
```

## 使用

打开目标应用并使其成为前台窗口，浮层会出现模型选择器附近。中间相机图标启动截图；右侧箭头打开设置；左侧圆点可拖动。

截图完成后，图片保存到安装目录下的 `captures` 或 `workbuddy-captures`，复制到剪贴板，并在启用默认选项时粘贴到聊天输入框。它只形成草稿。

## 常见问题

**没有显示浮层**：先打开并恢复目标应用、使其处于前台；最小化时隐藏按钮是正常行为。再确认助手进程存在、桌面快捷方式指向的真实安装目录有效，并检查该目录的 `overlay.log` 或 `workbuddy-overlay.log`。

**助手运行但按钮在窗口外**：旧版 WorkBuddy 定位只限制横向坐标，保存的 `vertical_adjust` 在窗口缩小后可能把按钮放到窗口下方。2026-10-26 修复在显示时同时约束窗口与所在显示器工作区，并保留已保存的拖动偏移。更新真实运行目录下的 `workbuddy_screenshot_overlay.py` 和 `screenshot_win32.py` 后，仅重启相应截图助手。不要终止 WorkBuddy 应用。显示器使用负坐标、不同 DPI 或任务栏占位时也适用。

只读诊断（`--install-root` 指向快捷方式实际使用的目录，省略时检查包内资源）：

```powershell
python .\scripts\diagnose_helper.py --install-root "$env:LOCALAPPDATA\CodexScreenshotHelpers" --target WorkBuddy
```

报告包含目标窗口是否最小化、助手窗口是否可见、实际坐标是否越界。诊断程序不截图、不操作窗口、不改配置。

**自动附图失败**：确认 PowerShell 7 可从 PATH 找到，并在目标输入框手动按 Ctrl+V。区域截图和剪贴板复制仍可使用。

**需要调整位置**：拖动浮层左侧圆点一次。选择“重置到模型栏附近”可以恢复默认位置。

**卸载**：先另存安装目录内需要保留的截图，再退出两个截图助手，删除安装目录、桌面的启动快捷方式以及开始菜单和 Startup 中的对应 `.lnk` 文件。删除安装目录也会删除其中的截图与配置；Codex、WorkBuddy 应用不受影响。
