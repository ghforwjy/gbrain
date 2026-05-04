"""
检查小红书笔记弹窗的DOM结构，找到正确的截图选择器
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
        
        # Inspect popup structure
        popup_info = page.evaluate("""() => {
            // Find the main popup/modal container
            const selectors = [
                '.note-detail',
                '.note-content',
                '.interaction-container',
                '[class*="popup"]',
                '[class*="modal"]',
                '[class*="drawer"]',
                '.swiper-container',
                '.swiper-wrapper',
                '.swiper-slide-active'
            ];
            
            const results = {};
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el) {
                    const rect = el.getBoundingClientRect();
                    results[sel] = {
                        exists: true,
                        rect: {
                            x: rect.x, y: rect.y, 
                            width: rect.width, height: rect.height,
                            top: rect.top, bottom: rect.bottom,
                            left: rect.left, right: rect.right
                        },
                        className: el.className,
                        parentClass: el.parentElement ? el.parentElement.className : null
                    };
                } else {
                    results[sel] = {exists: false};
                }
            }
            
            // Also check for the main content wrapper
            const mainContent = document.querySelector('main, .main, #app, .app');
            if (mainContent) {
                const rect = mainContent.getBoundingClientRect();
                results['mainContent'] = {
                    exists: true,
                    rect: {
                        x: rect.x, y: rect.y,
                        width: rect.width, height: rect.height
                    },
                    className: mainContent.className
                };
            }
            
            return results;
        }""")
        
        print("\n弹窗DOM结构分析:")
        print("="*60)
        for sel, info in popup_info.items():
            if info.get('exists'):
                rect = info['rect']
                print(f"\n{sel}:")
                print(f"  位置: ({rect['x']:.0f}, {rect['y']:.0f})")
                print(f"  大小: {rect['width']:.0f}x{rect['height']:.0f}")
                print(f"  类名: {info.get('className', 'N/A')}")
                if info.get('parentClass'):
                    print(f"  父类: {info['parentClass']}")
            else:
                print(f"\n{sel}: 不存在")
        
        # Take a screenshot to verify
        screenshot_path = Path(r"d:\mycode\gbrain\.playwright-cli\inspect_popup.png")
        page.screenshot(path=str(screenshot_path), full_page=False)
        print(f"\n截图已保存: {screenshot_path}")
        
        browser.close()

if __name__ == "__main__":
    inspect_popup()
