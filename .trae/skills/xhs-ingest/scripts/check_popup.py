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
    
    # Check for popup
    has_popup = page.evaluate("""() => {
        const selectors = ['.note-detail', '.note-popup', '[class*="note-detail"]', '[class*="popup"]', '.interaction-container', '.preview-modal'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) {
                return {found: true, selector: sel, className: el.className};
            }
        }
        return {found: false};
    }""")
    
    print(f"Popup check: {has_popup}")
    
    # Check note cards
    note_count = page.evaluate("document.querySelectorAll('section.note-item').length")
    print(f"Note cards: {note_count}")
    
    browser.close()
