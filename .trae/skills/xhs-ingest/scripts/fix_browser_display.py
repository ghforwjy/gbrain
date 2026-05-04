"""
修复浏览器显示问题
设置正确的视口大小，确保内容正常显示
"""
import json, urllib.request, time
from playwright.sync_api import sync_playwright
from pathlib import Path

CDP_URL = "http://localhost:9223"
SCREENSHOT_DIR = Path(r"d:\mycode\gbrain\.playwright-cli")

def fix_browser_display():
    """Connect and fix viewport settings."""
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(CDP_URL)
        context = browser.contexts[0]
        page = context.pages[0]
        
        print(f"Current URL: {page.url}")
        
        # Check current viewport
        old_viewport = page.viewport_size
        print(f"Old viewport: {old_viewport}")
        
        # Set proper viewport size
        page.set_viewport_size({"width": 1500, "height": 900})
        time.sleep(1)
        
        # Verify new viewport
        new_viewport = page.viewport_size
        print(f"New viewport: {new_viewport}")
        
        # Check page dimensions
        dimensions = page.evaluate("""() => {
            return {
                windowWidth: window.innerWidth,
                windowHeight: window.innerHeight,
                documentWidth: document.documentElement.scrollWidth,
                documentHeight: document.documentElement.scrollHeight
            };
        }""")
        print(f"Page dimensions: {dimensions}")
        
        # Take screenshot to verify
        screenshot_path = SCREENSHOT_DIR / "fixed_display.png"
        page.screenshot(path=str(screenshot_path), full_page=False)
        print(f"Screenshot saved: {screenshot_path}")
        print(f"Screenshot size: {screenshot_path.stat().st_size} bytes")
        
        browser.close()
        print("\n✅ 浏览器显示已修复")
        return True

if __name__ == "__main__":
    fix_browser_display()
