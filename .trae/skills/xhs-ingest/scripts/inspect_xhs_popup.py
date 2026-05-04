"""
检查小红书笔记弹窗的DOM结构，找到正确的选择器
"""
import json, urllib.request, time
from playwright.sync_api import sync_playwright
from pathlib import Path

CDP_URL = "http://localhost:9223"

def inspect_popup():
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        page = context.pages[0]
        
        print(f"Current URL: {page.url}")
        
        # Check if we're on a note page
        if '/explore/' not in page.url:
            print("不在笔记页面，请先打开一个笔记")
            browser.close()
            return
        
        # Inspect popup structure with more detailed selectors
        popup_info = page.evaluate("""() => {
            // Try to find the main content container
            const results = {};
            
            // Method 1: Look for the main note detail container
            const noteDetail = document.querySelector('.note-detail');
            if (noteDetail) {
                const rect = noteDetail.getBoundingClientRect();
                results['.note-detail'] = {
                    exists: true,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                    className: noteDetail.className,
                    childCount: noteDetail.children.length
                };
            }
            
            // Method 2: Look for interaction container
            const interaction = document.querySelector('.interaction-container');
            if (interaction) {
                const rect = interaction.getBoundingClientRect();
                results['.interaction-container'] = {
                    exists: true,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                    className: interaction.className,
                    childCount: interaction.children.length
                };
            }
            
            // Method 3: Look for swiper container
            const swiper = document.querySelector('.swiper-container');
            if (swiper) {
                const rect = swiper.getBoundingClientRect();
                results['.swiper-container'] = {
                    exists: true,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                    className: swiper.className,
                    childCount: swiper.children.length
                };
            }
            
            // Method 4: Find all elements with class containing 'note' or 'detail'
            const allElements = document.querySelectorAll('*');
            const noteElements = [];
            for (const el of allElements) {
                if (el.className && typeof el.className === 'string') {
                    if (el.className.includes('note') || el.className.includes('detail')) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 200 && rect.height > 200) {
                            noteElements.push({
                                className: el.className,
                                tagName: el.tagName,
                                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
                            });
                        }
                    }
                }
            }
            results['noteElements'] = noteElements.slice(0, 10); // Limit to 10
            
            // Method 5: Find the largest visible element (likely the popup)
            let largestElement = null;
            let largestArea = 0;
            for (const el of allElements) {
                const rect = el.getBoundingClientRect();
                const area = rect.width * rect.height;
                if (area > largestArea && rect.width > 300 && rect.height > 300 && rect.width < window.innerWidth * 0.9) {
                    largestArea = area;
                    largestElement = {
                        tagName: el.tagName,
                        className: el.className,
                        rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                        area: area
                    };
                }
            }
            results['largestElement'] = largestElement;
            
            return results;
        }""")
        
        print("\n弹窗DOM结构分析:")
        print("="*60)
        
        for key, info in popup_info.items():
            if key == 'noteElements':
                print(f"\n{key} (前10个):")
                for el in info:
                    print(f"  {el['tagName']}.{el['className']}: ({el['rect']['x']:.0f}, {el['rect']['y']:.0f}) {el['rect']['width']:.0f}x{el['rect']['height']:.0f}")
            elif key == 'largestElement' and info:
                print(f"\n{key}:")
                print(f"  {info['tagName']}.{info['className']}")
                print(f"  位置: ({info['rect']['x']:.0f}, {info['rect']['y']:.0f})")
                print(f"  大小: {info['rect']['width']:.0f}x{info['rect']['height']:.0f}")
                print(f"  面积: {info['area']:.0f}")
            elif info and info.get('exists'):
                print(f"\n{key}:")
                print(f"  位置: ({info['rect']['x']:.0f}, {info['rect']['y']:.0f})")
                print(f"  大小: {info['rect']['width']:.0f}x{info['rect']['height']:.0f}")
                print(f"  类名: {info.get('className', 'N/A')}")
                print(f"  子元素: {info.get('childCount', 'N/A')}")
            else:
                print(f"\n{key}: 不存在")
        
        browser.close()

if __name__ == "__main__":
    inspect_popup()
