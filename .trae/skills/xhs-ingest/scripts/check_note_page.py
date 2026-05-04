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
    
    # Check for slide count indicators
    fraction = page.evaluate("""() => {
        const el = document.querySelector('.fraction');
        return el ? el.textContent.trim() : 'not found';
    }""")
    print(f"Fraction: {fraction}")
    
    slider = page.evaluate("""() => {
        const el = document.querySelector('.xhs-slider-container');
        return el ? el.textContent.trim().substring(0, 50) : 'not found';
    }""")
    print(f"Slider: {slider}")
    
    pagination = page.evaluate("""() => {
        const el = document.querySelector('.pagination-list');
        return el ? el.children.length : 'not found';
    }""")
    print(f"Pagination: {pagination}")
    
    # Check for images
    images = page.evaluate("""() => {
        const imgs = document.querySelectorAll('img');
        return imgs.length;
    }""")
    print(f"Total images: {images}")
    
    # Check for swiper
    swiper = page.evaluate("""() => {
        const el = document.querySelector('.swiper-container, .swiper, [class*="swiper"]');
        return el ? el.className : 'not found';
    }""")
    print(f"Swiper: {swiper}")
    
    browser.close()
