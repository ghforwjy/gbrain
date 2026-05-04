"""
修复Chrome窗口大小，确保是桌面版尺寸
"""
import subprocess
import time
import os

def fix_chrome_window():
    """Resize Chrome window to desktop size."""
    # Use PowerShell to resize Chrome window
    ps_script = """
    Add-Type @"
    using System;
    using System.Runtime.InteropServices;
    public class WinAPI {
        [DllImport("user32.dll")]
        public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);
        
        [DllImport("user32.dll")]
        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
        
        [DllImport("user32.dll")]
        public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);
    }
    "@
    
    # Find Chrome window
    $hwnd = [WinAPI]::FindWindow("Chrome_WidgetWin_1", $null)
    if ($hwnd -ne 0) {
        # Resize to 1500x900 (desktop size)
        [WinAPI]::SetWindowPos($hwnd, 0, 0, 0, 1500, 900, 0x40)
        Write-Host "Chrome window resized to 1500x900"
    } else {
        Write-Host "Chrome window not found"
    }
    """
    
    # Execute PowerShell script
    result = subprocess.run(
        ["powershell", "-Command", ps_script],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(f"Error: {result.stderr}")
    
    time.sleep(2)
    print("Chrome窗口已调整")

if __name__ == "__main__":
    fix_chrome_window()
