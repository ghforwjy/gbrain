import json
from pathlib import Path

PROGRESS_FILE = Path(r"d:\mycode\gbrain\.gbrain\xhs_progress.json")

with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

completed = len([n for n in data['notes'] if n['status'] == 'completed'])
processing = len([n for n in data['notes'] if n['status'] == 'processing'])
failed = len([n for n in data['notes'] if n['status'] == 'failed'])
pending = len(data.get('pending_notes', []))

print(f"总笔记数: {data['total_notes']}")
print(f"已完成: {completed}")
print(f"处理中: {processing}")
print(f"待处理: {pending}")
print(f"失败: {failed}")

if failed > 0:
    print("\n失败笔记:")
    for n in data['notes']:
        if n['status'] == 'failed':
            print(f"  [{n['index']}] {n.get('title', 'N/A')} - {n.get('fail_reason', '')}")

if processing > 0:
    print("\n处理中笔记:")
    for n in data['notes']:
        if n['status'] == 'processing':
            print(f"  [{n['index']}] {n.get('title', 'N/A')}")

next_pending = [n for n in data.get('pending_notes', [])][:5]
if next_pending:
    print(f"\n下5个待处理: {[n['index'] for n in next_pending]}")
