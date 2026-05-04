"""
重新处理所有截图有问题的笔记
逐个处理，每个都验证截图质量
"""
import os
import sys
import json
from pathlib import Path

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
from xhs_progress import load_progress, mark_note_processing, mark_note_failed
from process_one_note import process_single_note_by_index

def get_note_index_by_id(note_id):
    """Get note index from progress file by note_id."""
    progress = load_progress()
    if not progress:
        return None
    
    for note in progress['notes']:
        if note.get('note_id') == note_id:
            return note.get('index')
    return None

def reprocess_notes():
    """Reprocess all problematic notes."""
    # Load report
    report_path = Path(__file__).parent / "screenshot_quality_report.json"
    with open(report_path, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    problematic_notes = report.get('problematic_notes', [])
    total = len(problematic_notes)
    
    print("="*70)
    print(f"重新处理截图有问题的笔记")
    print(f"共 {total} 个笔记需要重新处理")
    print("="*70)
    
    success_count = 0
    failed_notes = []
    
    for i, item in enumerate(problematic_notes, 1):
        note_id = item['note_id']
        note_idx = get_note_index_by_id(note_id)
        
        if note_idx is None:
            print(f"\n[{i}/{total}] 错误: 找不到 note_id={note_id} 对应的索引")
            failed_notes.append(note_id)
            continue
        
        print(f"\n{'='*70}")
        print(f"[{i}/{total}] 重新处理笔记 [{note_idx}] id={note_id}")
        print(f"{'='*70}")
        
        # Mark as processing
        mark_note_processing(note_idx)
        
        # Process the note
        try:
            result = process_single_note_by_index(note_idx)
            if result:
                print(f"✅ 笔记 [{note_idx}] 重新处理成功")
                success_count += 1
            else:
                print(f"❌ 笔记 [{note_idx}] 重新处理失败")
                failed_notes.append(note_id)
        except Exception as e:
            print(f"❌ 笔记 [{note_idx}] 处理异常: {e}")
            failed_notes.append(note_id)
        
        # Wait between notes to avoid风控
        if i < total:
            print(f"\n等待 5-10 秒后处理下一个...")
            import time
            import random
            time.sleep(random.uniform(5, 10))
    
    print(f"\n{'='*70}")
    print(f"重新处理完成")
    print(f"成功: {success_count}/{total}")
    print(f"失败: {len(failed_notes)}")
    if failed_notes:
        print(f"失败的笔记: {failed_notes}")
    print(f"{'='*70}")

if __name__ == "__main__":
    reprocess_notes()
