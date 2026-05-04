"""
最终修复视口问题
确保窗口大小正确，截图不偏左
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser
from pathlib import Path

def fix_viewport():
    p, browser, page = connect_browser()
    
    # Get current window size
    window_info = page.evaluate("""() => {
        return {
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight,
            screenWidth: screen.width,
            screenHeight: screen.height
        };
    }""")
    
    current_width = window_info['innerWidth']
    current_height = window_info['innerHeight']
    
    print(f"当前窗口: {current_width}x{current_height}")
    
    # Force resize to 1500x900
    print("强制设置视口为 1500x900...")
    page.set_viewport_size({"width": 1500, "height": 900})
    
    # Wait and verify
    import time
    time.sleep(2)
    
    # Check new size
    new_info = page.evaluate("""() => {
        return {
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight
        };
    }""")
    
    print(f"新窗口: {new_info['innerWidth']}x{new_info['innerHeight']}")
    
    # Take screenshot to verify
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\viewport_fixed.png")
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"截图已保存: {screenshot_path}")
    
    browser.close()

if __name__ == "__main__":
    fix_viewport()
