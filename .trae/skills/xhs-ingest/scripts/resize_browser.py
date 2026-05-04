"""
调整浏览器窗口大小为桌面版尺寸
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser

def resize_browser():
    """Resize browser window to desktop size."""
    p, browser, page = connect_browser()
    
    # Get current size
    current = page.evaluate("""() => {
        return {
            width: window.innerWidth,
            height: window.innerHeight
        };
    }""")
    
    print(f"当前窗口: {current['width']}x{current['height']}")
    
    # Set viewport to desktop size
    target_width = 1500
    target_height = 900
    
    print(f"设置视口: {target_width}x{target_height}")
    page.set_viewport_size({"width": target_width, "height": target_height})
    
    # Wait and verify
    import time
    time.sleep(2)
    
    new_size = page.evaluate("""() => {
        return {
            width: window.innerWidth,
            height: window.innerHeight
        };
    }""")
    
    print(f"新窗口: {new_size['width']}x{new_size['height']}")
    
    # Take screenshot to verify
    from pathlib import Path
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\resized_browser.png")
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"截图已保存: {screenshot_path}")
    
    browser.close()

if __name__ == "__main__":
    resize_browser()
