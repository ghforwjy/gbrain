"""
测试clip截图是否工作
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser, navigate_to_board, click_note_by_id, human_delay
from pathlib import Path

def test_clip():
    p, browser, page = connect_browser()
    navigate_to_board(page)
    human_delay(2, 3)
    
    # Click note
    click_note_by_id(page, "637cc220000000000e0314ab")
    human_delay(2, 3)
    
    # Try clip screenshot with smaller area
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\test_clip.png")
    
    try:
        # Use smaller clip area (exclude sidebar)
        page.screenshot(
            path=str(screenshot_path),
            full_page=False,
            clip={
                "x": 356,
                "y": 0,
                "width": 800,
                "height": 900
            },
            timeout=30000
        )
        print(f"✅ Clip截图成功: {screenshot_path}")
    except Exception as e:
        print(f"❌ Clip截图失败: {e}")
    
    browser.close()

if __name__ == "__main__":
    test_clip()
