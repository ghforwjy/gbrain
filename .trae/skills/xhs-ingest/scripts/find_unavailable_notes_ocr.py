"""
使用OCR检查所有截图，精确找出"当前笔记暂时无法浏览"的笔记
"""
import os
import sys
from pathlib import Path
from PIL import Image

# 尝试导入 pytesseract，如果失败则使用备用方法
try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False
    print("警告: 未安装 pytesseract，使用备用检测方法")

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
from xhs_progress import load_progress

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")

def check_with_ocr(image_path):
    """使用OCR检查截图内容"""
    if not HAS_TESSERACT:
        return None, "OCR不可用"
    
    try:
        img = Image.open(image_path)
        
        # OCR识别文字
        text = pytesseract.image_to_string(img, lang='chi_sim')
        
        # 检查是否包含"无法浏览"
        if "当前笔记暂时无法浏览" in text or "无法浏览" in text:
            return True, "检测到'无法浏览'提示"
        
        # 检查是否包含"请打开小红书App扫码查看"
        if "请打开小红书App扫码查看" in text or "扫码查看" in text:
            return True, "检测到'扫码查看'提示"
        
        return False, "正常"
        
    except Exception as e:
        return None, f"OCR失败: {e}"

def check_with_pixel_analysis(image_path):
    """使用像素分析检测'无法浏览'页面"""
    try:
        img = Image.open(image_path)
        width, height = img.size
        
        # 检查中心区域是否有大量白色像素（'无法浏览'页面的特征）
        # 裁剪多个区域进行检查
        regions = [
            (width//3, height//4, width*2//3, height//2),      # 上部中心
            (width//3, height//2, width*2//3, height*3//4),    # 下部中心
        ]
        
        white_pixel_count = 0
        total_pixel_count = 0
        
        for left, top, right, bottom in regions:
            region = img.crop((left, top, right, bottom))
            gray = region.convert('L')
            
            for y in range(0, gray.height, 5):
                for x in range(0, gray.width, 5):
                    pixel = gray.getpixel((x, y))
                    total_pixel_count += 1
                    if pixel > 250:  # 接近白色
                        white_pixel_count += 1
        
        if total_pixel_count > 0:
            white_ratio = white_pixel_count / total_pixel_count
            # 如果白色像素超过90%，可能是"无法浏览"页面
            if white_ratio > 0.9:
                return True, f"白色像素比例{white_ratio:.2%}"
        
        return False, "正常"
        
    except Exception as e:
        return False, f"检测失败: {e}"

def main():
    print("="*70)
    print("使用OCR和像素分析检查'无法浏览'的笔记")
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
    if HAS_TESSERACT:
        print("使用OCR检测...")
    else:
        print("使用像素分析检测...")
    print()
    
    unavailable_notes = []
    normal_notes = []
    uncertain_notes = []
    
    for screenshot in screenshots:
        note_id = screenshot.stem.split('_slide')[0]
        title = note_titles.get(note_id, 'Unknown')
        
        # 先用OCR检测
        if HAS_TESSERACT:
            is_unavailable, message = check_with_ocr(screenshot)
            if is_unavailable is None:
                # OCR失败，使用像素分析
                is_unavailable, message = check_with_pixel_analysis(screenshot)
        else:
            # 没有OCR，使用像素分析
            is_unavailable, message = check_with_pixel_analysis(screenshot)
        
        if is_unavailable:
            unavailable_notes.append({
                'note_id': note_id,
                'title': title,
                'reason': message
            })
            print(f"❌ [{note_id}] {title}")
            print(f"   原因: {message}")
        elif is_unavailable is False:
            normal_notes.append({
                'note_id': note_id,
                'title': title
            })
        else:
            uncertain_notes.append({
                'note_id': note_id,
                'title': title,
                'reason': message
            })
    
    # 输出结果
    print("\n" + "="*70)
    print(f"检查结果:")
    print(f"  正常笔记: {len(normal_notes)}")
    print(f"  无法浏览: {len(unavailable_notes)}")
    print(f"  不确定: {len(uncertain_notes)}")
    print("="*70)
    
    if unavailable_notes:
        print("\n无法浏览的笔记列表（需要您核实）:")
        print("-"*70)
        for i, note in enumerate(unavailable_notes, 1):
            print(f"{i}. [{note['note_id']}] {note['title']}")
            print(f"   检测原因: {note['reason']}")
        
        # 保存到文件
        report_path = Path(r"d:\mycode\gbrain\.trae\skills\xhs-ingest\scripts\unavailable_notes_report.txt")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write("无法浏览的笔记列表（需要核实是否已删除）\n")
            f.write("="*70 + "\n\n")
            for i, note in enumerate(unavailable_notes, 1):
                f.write(f"{i}. [{note['note_id']}] {note['title']}\n")
                f.write(f"   检测原因: {note['reason']}\n\n")
            f.write(f"\n共计: {len(unavailable_notes)} 个笔记\n")
            f.write("\n请在小红书App中核实这些笔记是否真的已删除。\n")
        
        print(f"\n报告已保存: {report_path}")
    
    if uncertain_notes:
        print(f"\n不确定的笔记（{len(uncertain_notes)}个）:")
        for note in uncertain_notes:
            print(f"  [{note['note_id']}] {note['title']}: {note['reason']}")
    
    return unavailable_notes

if __name__ == "__main__":
    main()
