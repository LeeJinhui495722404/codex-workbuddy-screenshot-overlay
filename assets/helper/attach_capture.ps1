param(
    [Parameter(Mandatory=$true)][long]$TargetHwnd,
    [Parameter(Mandatory=$true)][uint32]$ClipboardSequence
)
# UTF-8. Focus the one visible chat composer, paste once, never submit the message.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class ScreenshotPaste {
    [StructLayout(LayoutKind.Sequential)] public struct KEYBDINPUT {
        public ushort vk, scan; public uint flags, time; public UIntPtr extra;
    }
    [StructLayout(LayoutKind.Sequential)] public struct MOUSEINPUT {
        public int dx, dy; public uint data, flags, time; public UIntPtr extra;
    }
    [StructLayout(LayoutKind.Explicit)] public struct UNION {
        [FieldOffset(0)] public KEYBDINPUT keyboard;
        [FieldOffset(0)] public MOUSEINPUT mouse;
    }
    [StructLayout(LayoutKind.Sequential)] public struct INPUT { public uint type; public UNION value; }
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] public static extern uint GetClipboardSequenceNumber();
    [DllImport("user32.dll")] public static extern short GetAsyncKeyState(int key);
    [DllImport("user32.dll", SetLastError=true)] public static extern uint SendInput(uint count, INPUT[] inputs, int size);
    static INPUT Key(ushort vk, bool up) {
        INPUT i = new INPUT(); i.type = 1; i.value.keyboard.vk = vk;
        i.value.keyboard.flags = up ? 2u : 0u; return i;
    }
    public static bool Paste() {
        INPUT[] keys = { Key(0x11,false), Key(0x56,false), Key(0x56,true), Key(0x11,true) };
        uint sent = SendInput((uint)keys.Length, keys, Marshal.SizeOf(typeof(INPUT)));
        if (sent != 4) {
            INPUT[] release = { Key(0x56,true), Key(0x11,true) };
            SendInput(2, release, Marshal.SizeOf(typeof(INPUT)));
        }
        return sent == 4;
    }
}
'@

try {
    $target = [IntPtr]$TargetHwnd
    $root = [System.Windows.Automation.AutomationElement]::FromHandle($target)
    if ($null -eq $root) { throw '找不到原来的目标应用窗口。' }
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::Edit)
    $processName = (Get-Process -Id $root.Current.ProcessId).ProcessName
    $lowerHalf = $root.Current.BoundingRectangle.Top + $root.Current.BoundingRectangle.Height / 2
    $editors = @($root.FindAll([System.Windows.Automation.TreeScope]::Descendants, $condition) | Where-Object {
        $candidate = $_.Current
        if (-not $candidate.IsEnabled -or $candidate.IsOffscreen -or $candidate.BoundingRectangle.Top -le $lowerHalf) { return $false }
        if ($processName -ieq 'ChatGPT') {
            return $candidate.ClassName -match '(^|\s)ProseMirror(\s|$)'
        }
        if ($processName -ieq 'WorkBuddy') {
            return $candidate.Name -eq '编辑'
        }
        return $false
    })
    if ($editors.Count -ne 1) { throw '无法唯一确定聊天输入框，图片仍保留在剪贴板。' }
    $editor = $editors[0]
    if ([ScreenshotPaste]::GetClipboardSequenceNumber() -ne $ClipboardSequence) {
        throw '剪贴板内容已被其他操作修改，已跳过自动粘贴。'
    }
    # Do not override another application if the user switched away during capture completion.
    if ([ScreenshotPaste]::GetForegroundWindow() -ne $target) { throw 'Codex 已不在前台，已跳过自动粘贴。' }
    $editor.SetFocus()
    Start-Sleep -Milliseconds 70
    $focused = [System.Windows.Automation.AutomationElement]::FocusedElement
    if (-not [System.Windows.Automation.Automation]::Compare($editor, $focused)) {
        throw '聊天输入框未获得焦点，已跳过自动粘贴。'
    }
    foreach ($key in @(0x10,0x11,0x12,0x5B,0x5C)) {
        if (([ScreenshotPaste]::GetAsyncKeyState($key) -band 0x8000) -ne 0) {
            throw '检测到按住的修饰键，已跳过自动粘贴。'
        }
    }
    if ([ScreenshotPaste]::GetForegroundWindow() -ne $target -or
        [ScreenshotPaste]::GetClipboardSequenceNumber() -ne $ClipboardSequence) {
        throw '窗口或剪贴板已变化，已跳过自动粘贴。'
    }
    if (-not [ScreenshotPaste]::Paste()) { throw 'Windows 未能完成粘贴，图片仍保留在剪贴板。' }
    @{ ok=$true; action='pasted_to_composer'; submitted=$false } | ConvertTo-Json -Compress
} catch {
    @{ ok=$false; error=$_.Exception.Message; submitted=$false } | ConvertTo-Json -Compress
    exit 1
}
