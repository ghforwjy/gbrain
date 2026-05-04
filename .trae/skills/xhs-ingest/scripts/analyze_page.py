"""
分析小红书笔记页面的DOM结构
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser
from pathlib import Path

def analyze_page():
    p, browser, page = connect_browser()
    
    print(f"Current URL: {page.url}")
    
    # Get page structure
    structure = page.evaluate("""() => {
        const results = {
            windowSize: {width: window.innerWidth, height: window.innerHeight},
            bodySize: {width: document.body.scrollWidth, height: document.body.scrollHeight}
        };
        
        // Find main content areas
        const mainContent = document.querySelector('main, .main, #app');
        if (mainContent) {
            const rect = mainContent.getBoundingClientRect();
            results.mainContent = {
                className: mainContent.className,
                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
            };
        }
        
        // Find all direct children of body
        const bodyChildren = [];
        for (const child of document.body.children) {
            const rect = child.getBoundingClientRect();
            bodyChildren.push({
                tagName: child.tagName,
                className: child.className,
                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
            });
        }
        results.bodyChildren = bodyChildren;
        
        // Find elements with high z-index (likely popups/modals)
        const allElements = document.querySelectorAll('*');
        const highZIndex = [];
        for (const el of allElements) {
            const style = window.getComputedStyle(el);
            const zIndex = parseInt(style.zIndex);
            if (zIndex > 100) {
                const rect = el.getBoundingClientRect();
                highZIndex.push({
                    tagName: el.tagName,
                    className: el.className,
                    zIndex: zIndex,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                });
            }
        }
        results.highZIndex = highZIndex.slice(0, 10);
        
        return results;
    }""")
    
    print("\n页面结构分析:")
    print("="*60)
    print(f"窗口大小: {structure['windowSize']['width']}x{structure['windowSize']['height']}")
    print(f"页面大小: {structure['bodySize']['width']}x{structure['bodySize']['height']}")
    
    if structure.get('mainContent'):
        mc = structure['mainContent']
        print(f"\n主内容区:")
        print(f"  类名: {mc['className']}")
        print(f"  位置: ({mc['rect']['x']:.0f}, {mc['rect']['y']:.0f})")
        print(f"  大小: {mc['rect']['width']:.0f}x{mc['rect']['height']:.0f}")
    
    print(f"\nBody直接子元素:")
    for child in structure['bodyChildren']:
        print(f"  {child['tagName']}.{child['className']}: ({child['rect']['x']:.0f}, {child['rect']['y']:.0f}) {child['rect']['width']:.0f}x{child['rect']['height']:.0f}")
    
    print(f"\n高z-index元素 (前10个):")
    for el in structure['highZIndex']:
        print(f"  {el['tagName']}.{el['className']}: z={el['zIndex']} ({el['rect']['x']:.0f}, {el['rect']['y']:.0f}) {el['rect']['width']:.0f}x{el['rect']['height']:.0f}")
    
    browser.close()

if __name__ == "__main__":
    analyze_page()
