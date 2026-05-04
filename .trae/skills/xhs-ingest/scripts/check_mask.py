"""
检查.note-detail-mask元素的具体位置和尺寸
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser, navigate_to_board, click_note_by_id, human_delay

def check_mask():
    p, browser, page = connect_browser()
    navigate_to_board(page)
    human_delay(2, 3)
    
    # Click note
    click_note_by_id(page, "637cc220000000000e0314ab")
    human_delay(2, 3)
    
    # Check mask element
    mask_info = page.evaluate("""() => {
        const mask = document.querySelector('.note-detail-mask');
        if (!mask) return {found: false};
        
        const rect = mask.getBoundingClientRect();
        const style = window.getComputedStyle(mask);
        
        return {
            found: true,
            rect: {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                top: rect.top,
                bottom: rect.bottom,
                left: rect.left,
                right: rect.right
            },
            style: {
                position: style.position,
                display: style.display,
                visibility: style.visibility,
                zIndex: style.zIndex,
                backgroundColor: style.backgroundColor
            },
            parentTag: mask.parentElement ? mask.parentElement.tagName : null,
            parentClass: mask.parentElement ? mask.parentElement.className : null
        };
    }""")
    
    print("Mask元素信息:")
    print("="*60)
    if mask_info['found']:
        print(f"位置: ({mask_info['rect']['x']:.0f}, {mask_info['rect']['y']:.0f})")
        print(f"大小: {mask_info['rect']['width']:.0f}x{mask_info['rect']['height']:.0f}")
        print(f"Style: {mask_info['style']}")
        print(f"父元素: {mask_info['parentTag']}.{mask_info['parentClass']}")
    else:
        print("未找到.mask元素")
    
    browser.close()

if __name__ == "__main__":
    check_mask()
