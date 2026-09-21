# Codex / WorkBuddy Screenshot Overlay Helper

Windows 上的 Codex Skill，用于部署一个跟随模型选择器的截图浮层，支持 Codex 与腾讯 WorkBuddy。

## 功能

- 拖拽选区截图，或单击识别到的窗口截图。
- 可选截图时隐藏目标应用界面。
- 默认自动把截图加入聊天输入框作为草稿，不发送消息。
- 提供桌面、开始菜单与登录自启动入口。
- 设置窗口在点击外部、失去焦点或按 Escape 时自动关闭。

## 安装

将目录放入 Codex 的 Skills 目录后，在该目录运行：

```powershell
pwsh -NoLogo -NoProfile -File .\scripts\Install-Screenshot-Helpers.ps1
```

需要 Windows 10/11、Python 3、Pillow 和 PowerShell 7。详情请查看 [部署与排查说明](references/deployment.md)。

## 验证

```powershell
Get-ChildItem .\assets\helper\*.py | ForEach-Object { python -m py_compile $_.FullName }
python .\tests\verify_overlay.py
```
