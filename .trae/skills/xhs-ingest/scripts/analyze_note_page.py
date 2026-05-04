"""
打开笔记并分析页面源码结构
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser, navigate_to_board, click_note_by_id, human_delay

def analyze_note_page(note_id):
    # Connect and navigate
    p, browser, page = connect_browser()
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
    
    # Get full HTML
    html = page.content()
    with open(r"d:\mycode\gbrain\.playwright-cli\note_page_source.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"HTML已保存，长度: {len(html)} 字符")
    
    # Extract all elements with their classes and positions
    elements = page.evaluate("""() => {
        const results = [];
        const allElements = document.querySelectorAll('*');
        
        for (const el of allElements) {
            if (el.className && typeof el.className === 'string') {
                const rect = el.getBoundingClientRect();
                // Only include visible elements with reasonable size
                if (rect.width > 200 && rect.height > 200 && rect.top >= 0 && rect.left >= 0) {
                    results.push({
                        tagName: el.tagName,
                        className: el.className,
                        id: el.id,
                        rect: {
                            x: Math.round(rect.x),
                            y: Math.round(rect.y),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height)
                        },
                        childCount: el.children.length,
                        parentClass: el.parentElement ? el.parentElement.className : null
                    });
                }
            }
        }
        
        // Sort by area (largest first)
        results.sort((a, b) => (b.rect.width * b.rect.height) - (a.rect.width * a.rect.height));
        
        return results.slice(0, 30); // Top 30 largest elements
    }""")
    
    print(f"\n找到 {len(elements)} 个大元素 (按面积排序):")
    print("="*80)
    
    for i, el in enumerate(elements, 1):
        area = el['rect']['width'] * el['rect']['height']
        print(f"\n{i}. {el['tagName']}#{el['id']}.{el['className']}")
        print(f"   位置: ({el['rect']['x']}, {el['rect']['y']})")
        print(f"   大小: {el['rect']['width']}x{el['rect']['height']} (面积: {area})")
        print(f"   子元素: {el['childCount']}")
        if el['parentClass']:
            print(f"   父类: {el['parentClass'][:50]}...")
    
    # Also check for specific note-related selectors
    note_selectors = page.evaluate("""() => {
        const selectors = [
            '.note-detail',
            '.note-content', 
            '.interaction-container',
            '.note-container',
            '.content-container',
            '.main-content',
            '.swiper-container',
            '.swiper-wrapper',
            '.swiper-slide',
            '.swiper-slide-active',
            '[class*="note-detail"]',
            '[class*="note-content"]',
            '[class*="interaction"]'
        ];
        
        const results = {};
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                const rect = el.getBoundingClientRect();
                results[sel] = {
                    exists: true,
                    rect: {
                        x: Math.round(rect.x),
                        y: Math.round(rect.y),
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }
                };
            } else {
                results[sel] = {exists: false};
            }
        }
        return results;
    }""")
    
    print(f"\n\n特定选择器检查结果:")
    print("="*80)
    for sel, info in note_selectors.items():
        if info['exists']:
            print(f"{sel}: ({info['rect']['x']}, {info['rect']['y']}) {info['rect']['width']}x{info['rect']['height']}")
        else:
            print(f"{sel}: 不存在")
    
    browser.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python analyze_note_page.py <note_id>")
        sys.exit(1)
    
    note_id = sys.argv[1]
    analyze_note_page(note_id)
