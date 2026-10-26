---
name: screenshot-overlay-helper
description: 在 Windows 上部署、配置或排查 Codex 与 WorkBuddy 的伴随截图浮层：区域/窗口截图、可选隐藏应用界面、截图自动作为草稿附入聊天输入框。
---

# Codex / WorkBuddy 截图浮层

当用户希望在 Codex 或 WorkBuddy 的模型选择器旁使用伴随截图按钮时，使用本 Skill。它不适用于普通系统截图工具或非 Windows 平台。

## 部署

先阅读 [部署与排查说明](references/deployment.md)。将本 Skill 安装到目标电脑的 `.codex/skills` 目录后，执行：

```powershell
pwsh -NoLogo -NoProfile -File .\scripts\Install-Screenshot-Helpers.ps1
```

安装器把可执行文件复制到当前用户的 LocalAppData，创建桌面、开始菜单和登录自启动入口；不需要管理员权限。默认同时安装 Codex 和 WorkBuddy，可用 `-Target Codex` 或 `-Target WorkBuddy` 限定平台。

## 运行时行为

- 截图主按钮按当前默认模式执行；右侧下拉打开设置，可选“隐藏界面后截图”或“保留界面截图”。
- 截图方式支持拖拽框选；单击一个可识别窗口会选取该窗口。
- 默认自动把图片粘贴为聊天输入框中的草稿，且不会发送消息。
- 设置浮窗失焦、单击其外部或按 Escape 时应立即关闭。若这一行为回归，优先检查 `assets/helper/screenshot_settings.py` 是否被部署。
- WorkBuddy 的保存偏移量必须受窗口边界和实际显示器工作区约束；缩小窗口、切换显示器或 DPI 后不能让按钮落到屏幕外。不要只限制横向坐标。

## 按钮消失的排查

先区分助手未启动、目标应用最小化/非前台，以及位置越界。使用 [部署与排查说明](references/deployment.md) 的流程；可运行 `scripts/diagnose_helper.py --install-root <实际运行目录> --target WorkBuddy` 获取只读窗口诊断。不要因为界面看不到按钮就重装或清空全部设置。

## 修改与验证

保留 `assets/helper` 内的文件作为一个整体：两个平台共用 `screenshot_settings.py`、`screenshot_selector.py`、`screenshot_win32.py` 和 `attach_capture.ps1`。修改后至少执行：

```powershell
Get-ChildItem .\assets\helper\*.py | ForEach-Object { python -m py_compile $_.FullName }
python .\tests\verify_overlay.py
```

对浮层位置的改动应按 DPI 缩放计算。WorkBuddy 的默认位置应保持在模型选择器左侧约 15 像素的间隔；用户拖动后，保存的偏移量优先于默认值。
