import os, sys, json, time, urllib.request

CDP_PORT = int(os.environ.get("XHS_CDP_PORT", "9223"))
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

req = urllib.request.Request(f"http://localhost:{CDP_PORT}/json/version")
with urllib.request.urlopen(req, timeout=5) as resp:
    data = json.loads(resp.read().decode())
    cdp_url = data.get("webSocketDebuggerUrl", "")

from playwright.sync_api import sync_playwright
p = sync_playwright().start()
browser = p.chromium.connect_over_cdp(cdp_url)
context = browser.contexts[0]
page = context.pages[0]

# Reload fresh
print("Reloading board page...")
page.goto("https://www.xiaohongshu.com/board/698f3a82000000002502ef57?source=web_user_page",
          timeout=30000, wait_until="domcontentloaded")
time.sleep(5)

all_notes = {}
prev_count = 0
stable_rounds = 0

# Collect notes while scrolling - virtual scrolling means DOM elements come and go
print("Scrolling and collecting all notes...")
for i in range(200):
    # Collect current visible notes
    visible_notes = page.evaluate("""() => {
        const sections = Array.from(document.querySelectorAll('section.note-item'));
        return sections.map((section, index) => {
            const link = section.querySelector('a[href*="/explore/"]');
            const noteId = link ? link.href.match(/\\/explore\\/([a-f0-9]+)/)?.[1] : null;
            const title = section.querySelector('.title, .note-title, [class*="title"]')?.textContent?.trim() || null;
            return noteId ? {noteId: noteId, title: title} : null;
        }).filter(n => n !== null);
    }""")
    
    for note in visible_notes:
        if note["noteId"] not in all_notes:
            all_notes[note["noteId"]] = note["title"]
    
    current_total = len(all_notes)
    if i % 10 == 0:
        dom_count = page.evaluate("document.querySelectorAll('section.note-item').length")
        print(f"  Step {i}: DOM={dom_count}, Collected={current_total}")
    
    if current_total != prev_count:
        stable_rounds = 0
        prev_count = current_total
    else:
        stable_rounds += 1
    
    if stable_rounds >= 10:
        print(f"  No new notes after 10 scrolls, stopping. Total collected: {current_total}")
        break
    
    # Scroll down
    page.evaluate("window.scrollBy(0, 800)")
    time.sleep(1)

# Convert to list
note_list = []
for idx, (note_id, title) in enumerate(all_notes.items()):
    note_list.append({"index": idx, "noteId": note_id, "title": title})

print(f"\nTotal unique notes collected: {len(note_list)}")
for card in note_list:
    t = (card["title"] or "N/A")[:50]
    print(f"  [{card['index']:2d}] {card['noteId']}  {t}")

# Check imported
imported_ids = set()
from pathlib import Path
xhs_dir = Path("d:/mycode/gbrain/brain/sources/xhs")
for md_file in xhs_dir.glob("xhs-*.md"):
    note_id = md_file.stem.replace("xhs-", "")
    imported_ids.add(note_id)

new_notes = [c for c in note_list if c["noteId"] not in imported_ids]
print(f"\nAlready imported: {len(imported_ids)}")
print(f"New notes to import: {len(new_notes)}")
for card in new_notes:
    t = (card["title"] or "N/A")[:50]
    print(f"  [{card['index']:2d}] {card['noteId']}  {t}")

# Save
with open("d:/mycode/gbrain/.gbrain/xhs_all_notes.json", "w", encoding="utf-8") as f:
    json.dump({"total": len(note_list), "notes": note_list, "imported_ids": list(imported_ids)}, f, ensure_ascii=False, indent=2)
print(f"\nSaved to .gbrain/xhs_all_notes.json")

p.stop()
