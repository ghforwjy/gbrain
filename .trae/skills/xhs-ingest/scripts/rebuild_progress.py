import json

with open("d:/mycode/gbrain/.gbrain/xhs_all_notes.json", "r", encoding="utf-8") as f:
    data = json.load(f)

imported_ids = set(data["imported_ids"])
notes = data["notes"]

progress = {
    "board_id": "698f3a82000000002502ef57",
    "board_name": "AI概念学习",
    "total_notes": len(notes),
    "notes": [],
    "pending_notes": [],
    "last_updated": "2026-05-02",
    "chrome_pid": None,
    "cdp_port": 9223
}

for note in notes:
    idx = note["index"]
    note_id = note["noteId"]
    title = note["title"]
    is_imported = note_id in imported_ids

    note_entry = {
        "index": idx,
        "note_id": note_id,
        "title": title,
        "author": None,
        "status": "completed" if is_imported else "pending",
        "phases": {}
    }

    for phase in ["phase2_screenshot", "phase3_ocr", "phase4_vision", "phase5_import", "phase6_verify"]:
        note_entry["phases"][phase] = {"status": "completed" if is_imported else "pending"}

    progress["notes"].append(note_entry)

    if not is_imported:
        progress["pending_notes"].append({"index": idx, "note_id": note_id, "status": "pending"})

print(f"Total notes: {len(notes)}")
print(f"Already imported: {len(imported_ids)}")
print(f"Pending: {len(progress['pending_notes'])}")

with open("d:/mycode/gbrain/.gbrain/xhs_progress.json", "w", encoding="utf-8") as f:
    json.dump(progress, f, ensure_ascii=False, indent=2)
print("Progress file updated")
