"""
分析小红书笔记页面的完整HTML源码结构
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser

def analyze_page_source():
    p, browser, page = connect_browser()
    
    print(f"Current URL: {page.url}")
    
    # Get full HTML
    html = page.content()
    
    # Save HTML for analysis
    with open(r"d:\mycode\gbrain\.playwright-cli\page_source.html", "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"HTML已保存，长度: {len(html)} 字符")
    
    # Extract key elements
    elements = page.evaluate("""() => {
        const results = [];
        
        // Find all divs with class containing 'note', 'detail', 'content'
        const allDivs = document.querySelectorAll('div');
        for (const div of allDivs) {
            if (div.className && typeof div.className === 'string') {
                const className = div.className.toLowerCase();
                if (className.includes('note') || className.includes('detail') || 
                    className.includes('content') || className.includes('slide') ||
                    className.includes('swiper') || className.includes('popup') ||
                    className.includes('modal') || className.includes('drawer')) {
                    
                    const rect = div.getBoundingClientRect();
                    if (rect.width > 100 && rect.height > 100) {
                        results.push({
                            tagName: div.tagName,
                            className: div.className,
                            id: div.id,
                            rect: {
                                x: Math.round(rect.x),
                                y: Math.round(rect.y),
                                width: Math.round(rect.width),
                                height: Math.round(rect.height)
                            },
                            childCount: div.children.length,
                            html: div.outerHTML.substring(0, 200) // First 200 chars
                        });
                    }
                }
            }
        }
        
        return results;
    }""")
    
    print(f"\n找到 {len(elements)} 个相关元素:")
    print("="*80)
    
    for i, el in enumerate(elements[:20], 1):  # Show first 20
        print(f"\n{i}. {el['tagName']}#{el['id']}.{el['className']}")
        print(f"   位置: ({el['rect']['x']}, {el['rect']['y']})")
        print(f"   大小: {el['rect']['width']}x{el['rect']['height']}")
        print(f"   子元素: {el['childCount']}")
        print(f"   HTML: {el['html']}...")
    
    browser.close()

if __name__ == "__main__":
    analyze_page_source()
