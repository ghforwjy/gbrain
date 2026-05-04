"""
打开指定笔记并检查弹窗DOM结构
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser, navigate_to_board, click_note_by_id, human_delay

def open_and_inspect(note_id):
    # Connect to browser
    p, browser, page = connect_browser()
    
    # Navigate to board
    navigate_to_board(page)
    human_delay(2, 3)
    
    # Click note
    clicked_id, title, author = click_note_by_id(page, note_id)
    if not clicked_id:
        print("点击笔记失败")
        browser.close()
        return
    
    print(f"已打开笔记: {title}")
    human_delay(2, 3)
    
    # Inspect popup structure
    popup_info = page.evaluate("""() => {
        const results = {};
        
        // Check various selectors
        const selectors = [
            '.note-detail',
            '.interaction-container', 
            '.note-content',
            '.swiper-container',
            '.swiper-wrapper',
            '.swiper-slide-active',
            '[class*="note-detail"]',
            '[class*="interaction-container"]'
        ];
        
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                const rect = el.getBoundingClientRect();
                results[sel] = {
                    exists: true,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                    className: el.className
                };
            } else {
                results[sel] = {exists: false};
            }
        }
        
        // Find largest element
        const allElements = document.querySelectorAll('*');
        let largestElement = null;
        let largestArea = 0;
        
        for (const el of allElements) {
            const rect = el.getBoundingClientRect();
            const area = rect.width * rect.height;
            // Look for elements that are large but not the full page
            if (area > largestArea && 
                rect.width > 400 && rect.height > 400 && 
                rect.width < window.innerWidth * 0.8 &&
                rect.height < window.innerHeight * 0.9) {
                largestArea = area;
                largestElement = {
                    tagName: el.tagName,
                    className: el.className,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                };
            }
        }
        results['largestElement'] = largestElement;
        
        return results;
    }""")
    
    print("\n弹窗结构分析:")
    print("="*60)
    for sel, info in popup_info.items():
        if sel == 'largestElement' and info:
            print(f"\n最大元素:")
            print(f"  {info['tagName']}.{info['className']}")
            print(f"  位置: ({info['rect']['x']:.0f}, {info['rect']['y']:.0f})")
            print(f"  大小: {info['rect']['width']:.0f}x{info['rect']['height']:.0f}")
        elif info.get('exists'):
            print(f"\n{sel}:")
            print(f"  位置: ({info['rect']['x']:.0f}, {info['rect']['y']:.0f})")
            print(f"  大小: {info['rect']['width']:.0f}x{info['rect']['height']:.0f}")
            print(f"  类名: {info.get('className', 'N/A')}")
        else:
            print(f"\n{sel}: 不存在")
    
    # Take a screenshot to verify
    from pathlib import Path
    screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\inspect_result.png")
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"\n截图已保存: {screenshot_path}")
    
    browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python open_and_inspect.py <note_id>")
        sys.exit(1)
    
    note_id = sys.argv[1]
    open_and_inspect(note_id)
