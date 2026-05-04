import json
from pathlib import Path

PROGRESS_FILE = Path(r"d:\mycode\gbrain\.gbrain\xhs_progress.json")
XHS_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs")

with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

existing_md = set()
for md_file in XHS_DIR.glob("xhs-*.md"):
    note_id = md_file.stem.replace("xhs-", "")
    existing_md.add(note_id)

fixed = 0
still_processing = []
for note in data['notes']:
    if note['status'] == 'processing':
        note_id = note.get('note_id', '')
        if note_id in existing_md:
            note['status'] = 'completed'
            for phase in note.get('phases', {}).values():
                phase['status'] = 'completed'
            fixed += 1
            print(f"  ✅ [{note['index']}] {note.get('title', 'N/A')} -> completed (md exists)")
        else:
            still_processing.append(note)

for note in list(still_processing):
    note['status'] = 'pending'
    note.pop('fail_reason', None)
    for phase in note.get('phases', {}).values():
        if phase.get('status') != 'completed':
            phase['status'] = 'pending'
    if note['index'] not in [n['index'] for n in data['pending_notes']]:
        data['pending_notes'].append({"index": note['index'], "note_id": note.get('note_id'), "status": "pending"})
    print(f"  ⏳ [{note['index']}] {note.get('title', 'N/A')} -> pending (no md)")

for note in data['notes']:
    if note['status'] == 'failed':
        note_id = note.get('note_id', '')
        if note_id in existing_md:
            note['status'] = 'completed'
            for phase in note.get('phases', {}).values():
                phase['status'] = 'completed'
            fixed += 1
            print(f"  ✅ [{note['index']}] {note.get('title', 'N/A')} -> completed (md exists, was failed)")
        else:
            note['status'] = 'pending'
            note.pop('fail_reason', None)
            for phase in note.get('phases', {}).values():
                if phase.get('status') != 'completed':
                    phase['status'] = 'pending'
            if note['index'] not in [n['index'] for n in data['pending_notes']]:
                data['pending_notes'].append({"index": note['index'], "note_id": note.get('note_id'), "status": "pending"})
            print(f"  ⏳ [{note['index']}] {note.get('title', 'N/A')} -> pending (was failed)")

completed_indices = set()
for note in data['notes']:
    if note['status'] == 'completed':
        completed_indices.add(note['index'])

data['pending_notes'] = [n for n in data['pending_notes'] if n['index'] not in completed_indices]
data['pending_notes'].sort(key=lambda n: n['index'])

completed = len([n for n in data['notes'] if n['status'] == 'completed'])
pending = len(data.get('pending_notes', []))

print(f"\nFixed {fixed} notes to completed")
print(f"Total completed: {completed}")
print(f"Total pending: {pending}")

with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Done")
