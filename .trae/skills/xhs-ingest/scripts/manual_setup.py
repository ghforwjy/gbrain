"""
手动设置浏览器 - 调整窗口大小并导航到小红书
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser
from pathlib import Path
import time

def manual_setup():
    print("连接浏览器...")
    p, browser, page = connect_browser()
    
    print(f"当前页面: {page.url}")
    print(f"当前窗口大小: {page.viewport_size}")
    
    # Set viewport to 1500x900
    print("设置视口为 1500x900...")
    page.set_viewport_size({"width": 1500, "height": 900})
    time.sleep(1)
    
    # Navigate to Xiaohongshu
    print("导航到小红书...")
    page.goto("https://www.xiaohongshu.com")
    time.sleep(3)
    
    print(f"当前页面: {page.url}")
    print("\n请手动登录小红书，然后按Enter继续...")
    input()
    
    # Navigate to board
    print("导航到收藏夹...")
    page.goto("https://www.xiaohongshu.com/board/698f3a82000000002502ef57")
    time.sleep(3)
    
    print(f"当前页面: {page.url}")
    
    # Take screenshot
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\manual_setup.png")
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"截图已保存: {screenshot_path}")
    
    browser.close()
    print("设置完成")

if __name__ == "__main__":
    manual_setup()
