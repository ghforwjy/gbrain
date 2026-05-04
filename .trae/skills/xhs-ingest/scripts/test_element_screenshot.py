"""
测试element截图，等待元素稳定后再截图
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser, navigate_to_board, click_note_by_id, human_delay
from pathlib import Path

def test_element_screenshot():
    p, browser, page = connect_browser()
    navigate_to_board(page)
    human_delay(2, 3)
    
    # Click note
    click_note_by_id(page, "637cc220000000000e0314ab")
    human_delay(3, 5)
    
    # Find the note detail element
    element = page.query_selector('[class*="note-detail"]')
    if not element:
        print("未找到note-detail元素")
        browser.close()
        return
    
    # Wait for element to be stable
    print("等待元素稳定...")
    try:
        element.wait_for_element_state("stable", timeout=10000)
        print("元素已稳定")
    except Exception as e:
        print(f"等待稳定失败: {e}")
    
    # Take screenshot
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\test_element.png")
    
    try:
        element.screenshot(path=str(screenshot_path), timeout=30000)
        print(f"✅ Element截图成功: {screenshot_path}")
    except Exception as e:
        print(f"❌ Element截图失败: {e}")
        # Fallback to page screenshot
        try:
            page.screenshot(path=str(screenshot_path), full_page=False, timeout=30000)
            print(f"✅ Page截图成功: {screenshot_path}")
        except Exception as e2:
            print(f"❌ Page截图也失败: {e2}")
    
    browser.close()

if __name__ == "__main__":
    test_element_screenshot()
