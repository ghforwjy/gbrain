"""
查找 note_id 对应的笔记索引
"""
import sys
from xhs_progress import load_progress

def find_note_index(note_id):
    progress = load_progress()
    if not progress:
        print("错误: 无法加载进度文件")
        return None
    
    for note in progress['notes']:
        if note.get('note_id') == note_id:
            idx = note.get('index')
            title = note.get('title', 'Unknown')
            print(f"找到笔记: [{idx}] {note_id} - {title}")
            return idx
    
    print(f"未找到 note_id: {note_id}")
    return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python find_note_index.py <note_id>")
        sys.exit(1)
    
    note_id = sys.argv[1]
    find_note_index(note_id)
