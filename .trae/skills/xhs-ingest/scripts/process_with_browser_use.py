"""
使用 browser-use CLI 处理小红书笔记
避免 Playwright 视口问题
"""
import subprocess
import json
import time
import os
from pathlib import Path

SCREENSHOT_DIR = Path(r"d:\mycode\gbrain\.playwright-cli")

def run_browser_use(command, wait=True):
    """Run a browser-use command and return the result."""
    full_command = f"browser-use {command}"
    print(f"  执行: {full_command}")
    
    result = subprocess.run(
        full_command,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8'
    )
    
    if result.returncode != 0:
        print(f"  错误: {result.stderr}")
        return None
    
    return result.stdout

def process_note_with_browser_use(note_url):
    """Process a single note using browser-use CLI."""
    print(f"\n处理笔记: {note_url}")
    
    # 1. Open the note URL
    result = run_browser_use(f"open {note_url}")
    if not result:
        print("  ❌ 打开笔记失败")
        return False
    
    time.sleep(3)
    
    # 2. Take screenshot
    screenshot_path = SCREENSHOT_DIR / "browser_use_screenshot.png"
    result = run_browser_use(f"screenshot {screenshot_path}")
    if result:
        print(f"  ✅ 截图已保存: {screenshot_path}")
    else:
        print("  ❌ 截图失败")
        return False
    
    # 3. Get page info
    result = run_browser_use("get title")
    if result:
        print(f"  页面标题: {result.strip()}")
    
    return True

if __name__ == "__main__":
    # Test with a note URL
    note_url = "https://www.xiaohongshu.com/explore/67fdb8aa000000001b026b78"
    process_note_with_browser_use(note_url)
