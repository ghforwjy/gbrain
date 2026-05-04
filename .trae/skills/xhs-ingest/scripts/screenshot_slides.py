import time
import os
import sys
import json
import urllib.request
from playwright.sync_api import sync_playwright

CDP_PORT = int(os.environ.get("XHS_CDP_PORT", "9222"))
CDP_ENDPOINT = f"http://localhost:{CDP_PORT}"
SCREENSHOT_DIR = "d:/mycode/gbrain/.playwright-cli"

# 确保截图目录存在
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# 获取CDP URL
req = urllib.request.Request(f"{CDP_ENDPOINT}/json/version")
with urllib.request.urlopen(req, timeout=5) as resp:
    cdp_info = json.loads(resp.read().decode())
    cdp_url = cdp_info.get("webSocketDebuggerUrl", "")

print(f"CDP URL: {cdp_url[:60]}...")

with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    print(f"Current URL: {page.url}")
    print(f"Title: {page.title()}")

    # 获取总页数
    slide_info = page.evaluate("""() => {
        const fraction = document.querySelector('.fraction');
        if (fraction) {
            const text = fraction.textContent.trim();
            const match = text.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
            if (match) {
                return {current: parseInt(match[1]), total: parseInt(match[2])};
            }
        }
        const sliderContainer = document.querySelector('.xhs-slider-container');
        if (sliderContainer) {
            const text = sliderContainer.textContent.trim();
            const match = text.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
            if (match) {
                return {current: parseInt(match[1]), total: parseInt(match[2])};
            }
        }
        const paginationList = document.querySelector('.pagination-list');
        if (paginationList) {
            return {current: 1, total: paginationList.children.length};
        }
        const bullets = document.querySelectorAll('.swiper-pagination-bullet');
        if (bullets.length > 0) {
            return {current: 1, total: bullets.length};
        }
        return {current: 1, total: 1};
    }""")

    current = slide_info.get('current', 1)
    total = slide_info.get('total', 1)
    print(f"\nSlides: {current}/{total}")

    # 截图所有图片
    for i in range(current, total + 1):
        screenshot_path = f"{SCREENSHOT_DIR}/page-{i:03d}.png"
        print(f"\nScreenshot {i}/{total}...")

        # 等待图片加载
        time.sleep(1)

        # 截图
        page.screenshot(path=screenshot_path, full_page=False)
        print(f"Saved: {screenshot_path}")

        # 如果不是最后一张，按ArrowRight切换
        if i < total:
            print("Pressing ArrowRight...")
            page.keyboard.press("ArrowRight")
            time.sleep(1)

    print(f"\n{'='*50}")
    print(f"All {total} screenshots saved to {SCREENSHOT_DIR}")
    print(f"{'='*50}")

    browser.close()
