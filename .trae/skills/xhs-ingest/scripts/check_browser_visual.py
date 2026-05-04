"""
视觉检查浏览器状态 - 截图查看页面是否正常
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser
from pathlib import Path

def check_browser_visual():
    """Take a screenshot to visually check browser state."""
    p, browser, page = connect_browser()
    
    print(f"Current URL: {page.url}")
    
    # Take screenshot
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\browser_state_check.png")
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"截图已保存: {screenshot_path}")
    
    # Check if page is blank/white
    page_info = page.evaluate("""() => {
        const body = document.body;
        const html = document.documentElement;
        return {
            bodyBackground: window.getComputedStyle(body).backgroundColor,
            bodyInnerHTML: body.innerHTML.substring(0, 200),
            documentHeight: html.scrollHeight,
            visibleElements: document.querySelectorAll('*').length
        };
    }""")
    
    print(f"\n页面状态:")
    print(f"  背景色: {page_info['bodyBackground']}")
    print(f"  文档高度: {page_info['documentHeight']}")
    print(f"  可见元素数: {page_info['visibleElements']}")
    print(f"  Body内容: {page_info['bodyInnerHTML']}...")
    
    browser.close()
    return screenshot_path

if __name__ == "__main__":
    check_browser_visual()
