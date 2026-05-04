"""
等待Chrome完全启动后检查状态
"""
import time
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser
from pathlib import Path

def wait_and_check():
    print("等待Chrome完全启动...")
    time.sleep(10)  # Wait longer for Chrome to be ready
    
    print("连接浏览器...")
    p, browser, page = connect_browser()
    
    print(f"Current URL: {page.url}")
    
    # Try to take screenshot with longer timeout
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\browser_state_after_wait.png")
    
    try:
        page.screenshot(path=str(screenshot_path), full_page=False, timeout=60000)
        print(f"✅ 截图成功: {screenshot_path}")
    except Exception as e:
        print(f"❌ 截图失败: {e}")
    
    browser.close()

if __name__ == "__main__":
    wait_and_check()
