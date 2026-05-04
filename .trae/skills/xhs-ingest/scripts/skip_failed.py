"""
Skip failed notes by moving them to the end of pending list.
Usage: python skip_failed.py
"""
import json
from pathlib import Path

PROGRESS_FILE = Path(r"d:\mycode\gbrain\.gbrain\xhs_progress.json")

with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

failed_notes = []
for note in data['notes']:
    if note['status'] == 'failed':
        failed_notes.append(note)
        note['status'] = 'pending'
        note.pop('fail_reason', None)
        for phase in note.get('phases', {}).values():
            if phase.get('status') != 'completed':
                phase['status'] = 'pending'

# Remove failed notes from pending list
pending_indices = {n['index'] for n in data.get('pending_notes', [])}
for note in failed_notes:
    if note['index'] in pending_indices:
        data['pending_notes'] = [n for n in data['pending_notes'] if n['index'] != note['index']]

# Add failed notes to the end of pending list
for note in failed_notes:
    data['pending_notes'].append({
        "index": note['index'],
        "note_id": note.get('note_id'),
        "status": "pending"
    })

# Sort pending notes: non-failed first, then failed
failed_indices = {n['index'] for n in failed_notes}
data['pending_notes'].sort(key=lambda n: (n['index'] in failed_indices, n['index']))

completed = len([n for n in data['notes'] if n['status'] == 'completed'])
pending = len(data.get('pending_notes', []))
failed = len([n for n in data['notes'] if n['status'] == 'failed'])

print(f"总笔记数: {data['total_notes']}")
print(f"已完成: {completed}")
print(f"待处理: {pending}")
print(f"失败: {failed}")

if failed_notes:
    print(f"\n已跳过 {len(failed_notes)} 个失败笔记，移到队列末尾:")
    for note in failed_notes:
        print(f"  [{note['index']}] {note.get('title', 'N/A')}")

with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("\nDone")
