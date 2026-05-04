"""
Check current browser page and screenshot quality.
Usage: python check_screenshot.py
"""
import json, urllib.request
from playwright.sync_api import sync_playwright
from pathlib import Path

CDP_URL = "http://localhost:9223"
SCREENSHOT_DIR = Path(r"d:\mycode\gbrain\.playwright-cli")

# Get page via CDP
req = urllib.request.Request(f'{CDP_URL}/json/list')
with urllib.request.urlopen(req, timeout=5) as resp:
    pages = json.loads(resp.read().decode())

target = None
for p in pages:
    if 'xiaohongshu.com' in p.get('url', ''):
        target = p
        break

if not target:
    print("No xiaohongshu page found")
    exit(1)

print(f"Current URL: {target['url']}")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]
    page = context.pages[0]
    
    # Check viewport size
    viewport = page.viewport_size
    print(f"Viewport: {viewport}")
    
    # Check page dimensions
    dimensions = page.evaluate("""() => {
        return {
            windowWidth: window.innerWidth,
            windowHeight: window.innerHeight,
            documentWidth: document.documentElement.scrollWidth,
            documentHeight: document.documentElement.scrollHeight,
            screenWidth: screen.width,
            screenHeight: screen.height
        };
    }""")
    print(f"Page dimensions: {dimensions}")
    
    # Check for note content area
    content_area = page.evaluate("""() => {
        const selectors = ['.note-content', '.content', '.note-detail', '.interaction-container'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el) {
                const rect = el.getBoundingClientRect();
                return {
                    selector: sel,
                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                    visible: rect.top >= 0 && rect.bottom <= window.innerHeight
                };
            }
        }
        return null;
    }""")
    print(f"Content area: {content_area}")
    
    # Check for bottom bar
    bottom_bar = page.evaluate("""() => {
        const bar = document.querySelector('.bottom-bar, .tab-bar, .nav-bar, [class*="bottom"], [class*="tab"]');
        if (bar) {
            const rect = bar.getBoundingClientRect();
            return {
                className: bar.className,
                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height}
            };
        }
        return null;
    }""")
    print(f"Bottom bar: {bottom_bar}")
    
    # Take a screenshot to check
    screenshot_path = SCREENSHOT_DIR / "check_page.png"
    page.screenshot(path=str(screenshot_path), full_page=False)
    print(f"Screenshot saved: {screenshot_path}")
    print(f"Screenshot size: {screenshot_path.stat().st_size} bytes")
    
    browser.close()
