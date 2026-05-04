"""
Fix browser viewport size for proper screenshot.
Usage: python fix_viewport.py
"""
import json, urllib.request
from playwright.sync_api import sync_playwright

CDP_URL = "http://localhost:9223"

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

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(CDP_URL)
    context = browser.contexts[0]
    page = context.pages[0]
    
    print(f"Current URL: {page.url}")
    
    # Set viewport to a reasonable size
    page.set_viewport_size({"width": 1280, "height": 800})
    print("Viewport set to 1280x800")
    
    # Reload page to apply viewport
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2000)
    
    # Check new dimensions
    dimensions = page.evaluate("""() => {
        return {
            windowWidth: window.innerWidth,
            windowHeight: window.innerHeight,
            documentWidth: document.documentElement.scrollWidth,
            documentHeight: document.documentElement.scrollHeight
        };
    }""")
    print(f"New dimensions: {dimensions}")
    
    # Check content area
    content_area = page.evaluate("""() => {
        const el = document.querySelector('.note-content');
        if (el) {
            const rect = el.getBoundingClientRect();
            return {
                rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                visible: rect.top >= 0 && rect.bottom <= window.innerHeight
            };
        }
        return null;
    }""")
    print(f"Content area: {content_area}")
    
    browser.close()
