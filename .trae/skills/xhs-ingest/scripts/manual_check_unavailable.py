"""
手动检查可疑的笔记截图
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
from xhs_progress import load_progress

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")

def main():
    print("="*70)
    print("手动检查可疑笔记")
    print("="*70)
    
    # 加载进度文件获取标题
    progress = load_progress()
    note_titles = {}
    if progress:
        for note in progress.get('notes', []):
            note_titles[note.get('note_id', '')] = note.get('title', 'Unknown')
    
    # 之前手动确认有问题的笔记ID
    suspicious_notes = [
        "637cc220000000000e0314ab",  # 3分钟精通windows沙盒Sandbox及自定义配置
        "67072e1c000000001a0231c6",  # Raptor的主要做法
    ]
    
    print("\n需要您核实的笔记（截图显示'当前笔记暂时无法浏览'）:")
    print("-"*70)
    
    unavailable_notes = []
    
    for note_id in suspicious_notes:
        title = note_titles.get(note_id, 'Unknown')
        screenshot_path = IMAGES_DIR / f"{note_id}_slide1.png"
        
        if screenshot_path.exists():
            print(f"\n❌ [{note_id}] {title}")
            print(f"   截图文件: {screenshot_path}")
            print(f"   状态: 截图显示'当前笔记暂时无法浏览'")
            unavailable_notes.append({
                'note_id': note_id,
                'title': title
            })
        else:
            print(f"\n⚠️ [{note_id}] {title}")
            print(f"   截图文件不存在")
    
    # 保存报告
    if unavailable_notes:
        report_path = Path(r"d:\mycode\gbrain\.trae\skills\xhs-ingest\scripts\unavailable_notes_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("无法浏览的笔记列表（需要核实是否已删除）\n")
            f.write("="*70 + "\n\n")
            f.write("这些笔记的截图显示'当前笔记暂时无法浏览'，可能是：\n")
            f.write("1. 笔记已被作者删除\n")
            f.write("2. 笔记被作者设为私密\n")
            f.write("3. 笔记被平台下架\n")
            f.write("4. 其他原因导致无法访问\n\n")
            f.write("请在小红书App中核实这些笔记的状态。\n\n")
            
            for i, note in enumerate(unavailable_notes, 1):
                f.write(f"{i}. [{note['note_id']}] {note['title']}\n")
            
            f.write(f"\n共计: {len(unavailable_notes)} 个笔记\n")
        
        print(f"\n报告已保存: {report_path}")
    
    print("\n" + "="*70)
    print(f"发现 {len(unavailable_notes)} 个无法浏览的笔记")
    print("="*70)

if __name__ == "__main__":
    main()
