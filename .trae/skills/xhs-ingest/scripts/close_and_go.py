import json, urllib.request
from playwright.sync_api import sync_playwright

CDP_URL = "http://localhost:9223"
BOARD_ID = "698f3a82000000002502ef57"

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
    
    # Close popup by pressing Escape
    page.keyboard.press("Escape")
    page.wait_for_timeout(1000)
    
    # Navigate to board
    page.goto(f"https://www.xiaohongshu.com/board/{BOARD_ID}?source=web_user_page",
              wait_until="domcontentloaded", timeout=15000)
    page.wait_for_timeout(2000)
    
    print(f"Navigated to: {page.url}")
    
    note_count = page.evaluate("document.querySelectorAll('section.note-item').length")
    print(f"Note cards: {note_count}")
    
    browser.close()
