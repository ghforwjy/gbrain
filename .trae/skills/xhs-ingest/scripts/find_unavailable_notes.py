"""
检查所有截图，找出显示"当前笔记暂时无法浏览"的笔记
并记录标题和ID
"""
import os
import sys
from pathlib import Path
from PIL import Image

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
from xhs_progress import load_progress

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")

def check_if_unavailable(image_path):
    """检查截图是否显示'无法浏览'"""
    try:
        img = Image.open(image_path)
        
        # 检查中心区域（通常是提示信息的位置）
        width, height = img.size
        
        # 裁剪中心区域（提示文字通常在这里）
        left = width // 4
        top = height // 3
        right = width * 3 // 4
        bottom = height * 2 // 3
        
        center_crop = img.crop((left, top, right, bottom))
        
        # 转换为灰度图
        gray = center_crop.convert('L')
        
        # 检查平均亮度（无法浏览页面通常是白色背景）
        pixels = list(gray.getdata())
        avg_brightness = sum(pixels) / len(pixels)
        
        # 如果中心区域很亮（>240），可能是"无法浏览"页面
        if avg_brightness > 240:
            return True, f"中心区域亮度{avg_brightness:.1f}（可能是空白提示页）"
        
        return False, f"正常（亮度{avg_brightness:.1f}）"
        
    except Exception as e:
        return False, f"检查失败: {e}"

def main():
    print("="*70)
    print("检查所有截图，找出'当前笔记暂时无法浏览'的笔记")
    print("="*70)
    
    if not IMAGES_DIR.exists():
        print(f"错误: 图片目录不存在: {IMAGES_DIR}")
        return
    
    # 加载进度文件获取标题
    progress = load_progress()
    note_titles = {}
    if progress:
        for note in progress.get('notes', []):
            note_titles[note.get('note_id', '')] = note.get('title', 'Unknown')
    
    # 获取所有截图文件
    screenshots = sorted(IMAGES_DIR.glob("*_slide1.png"))
    
    print(f"\n找到 {len(screenshots)} 张截图")
    print()
    
    unavailable_notes = []
    normal_notes = []
    
    for screenshot in screenshots:
        note_id = screenshot.stem.split('_slide')[0]
        title = note_titles.get(note_id, 'Unknown')
        
        is_unavailable, message = check_if_unavailable(screenshot)
        
        if is_unavailable:
            unavailable_notes.append({
                'note_id': note_id,
                'title': title,
                'reason': message
            })
            print(f"❌ [{note_id}] {title}")
            print(f"   原因: {message}")
        else:
            normal_notes.append({
                'note_id': note_id,
                'title': title
            })
    
    # 输出结果
    print("\n" + "="*70)
    print(f"检查结果:")
    print(f"  正常笔记: {len(normal_notes)}")
    print(f"  无法浏览: {len(unavailable_notes)}")
    print("="*70)
    
    if unavailable_notes:
        print("\n无法浏览的笔记列表（需要您核实）:")
        print("-"*70)
        for i, note in enumerate(unavailable_notes, 1):
            print(f"{i}. [{note['note_id']}] {note['title']}")
        
        # 保存到文件
        report_path = Path(r"d:\mycode\gbrain\.trae\skills\xhs-ingest\scripts\unavailable_notes_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("无法浏览的笔记列表（需要核实是否已删除）\n")
            f.write("="*70 + "\n\n")
            for i, note in enumerate(unavailable_notes, 1):
                f.write(f"{i}. [{note['note_id']}] {note['title']}\n")
            f.write(f"\n共计: {len(unavailable_notes)} 个笔记\n")
        
        print(f"\n报告已保存: {report_path}")
    
    return unavailable_notes

if __name__ == "__main__":
    main()
