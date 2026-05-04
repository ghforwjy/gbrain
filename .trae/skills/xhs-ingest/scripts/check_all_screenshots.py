"""
批量检查所有已保存截图的质量
识别出有问题的截图，需要重新获取
"""
import os
import sys
from pathlib import Path
from PIL import Image
import json

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
from xhs_progress import load_progress

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")

def check_screenshot_quality(screenshot_path):
    """检查单张截图质量，返回 (is_valid, issues, note_id)"""
    issues = []
    note_id = None
    
    # Extract note_id from filename (e.g., 637cc220000000000e0314ab_slide1.png)
    try:
        note_id = screenshot_path.stem.split('_slide')[0]
    except:
        pass
    
    try:
        img = Image.open(screenshot_path)
        width, height = img.size
        
        # Check 1: Size validation
        if width < 400 or height < 400:
            issues.append(f"尺寸过小 ({width}x{height})")
        
        # Check 2: Check if it's mostly white/blank
        gray = img.convert('L')
        pixels = list(gray.getdata())
        avg_brightness = sum(pixels) / len(pixels)
        
        if avg_brightness > 245:
            issues.append(f"mostly_blank (亮度{avg_brightness:.1f})")
        
        if avg_brightness < 20:
            issues.append(f"mostly_black (亮度{avg_brightness:.1f})")
        
        # Check 3: Aspect ratio (too wide = includes background)
        aspect_ratio = width / height
        if aspect_ratio > 3:
            issues.append(f"宽高比异常 ({aspect_ratio:.2f})")
        
        # Check 4: File size
        file_size = screenshot_path.stat().st_size
        if file_size < 5000:
            issues.append(f"文件过小 ({file_size} bytes)")
        
        # Check 5: Check if bottom part has content (not just white)
        # Sample pixels from bottom 20% of image
        bottom_samples = []
        for y in range(int(height * 0.8), height, max(1, (height - int(height * 0.8)) // 10)):
            for x in range(0, width, max(1, width // 10)):
                try:
                    pixel = gray.getpixel((x, y))
                    bottom_samples.append(pixel)
                except:
                    pass
        
        if bottom_samples:
            bottom_avg = sum(bottom_samples) / len(bottom_samples)
            if bottom_avg > 250:  # Bottom is mostly white - might be incomplete
                issues.append(f"底部空白 (亮度{bottom_avg:.1f})")
        
        is_valid = len(issues) == 0
        return is_valid, issues, note_id
        
    except Exception as e:
        return False, [f"无法打开: {e}"], note_id


def check_all_screenshots():
    """检查所有截图，返回有问题的笔记列表"""
    print("="*70)
    print("批量检查截图质量")
    print("="*70)
    
    if not IMAGES_DIR.exists():
        print(f"错误: 图片目录不存在: {IMAGES_DIR}")
        return []
    
    # Group screenshots by note_id
    note_screenshots = {}
    
    for screenshot_file in sorted(IMAGES_DIR.glob("*_slide*.png")):
        note_id = screenshot_file.stem.split('_slide')[0]
        if note_id not in note_screenshots:
            note_screenshots[note_id] = []
        note_screenshots[note_id].append(screenshot_file)
    
    print(f"找到 {len(note_screenshots)} 个笔记的截图")
    print()
    
    # Check each note's screenshots
    problematic_notes = []
    
    for note_id, screenshots in sorted(note_screenshots.items()):
        note_issues = []
        
        for screenshot in sorted(screenshots):
            is_valid, issues, _ = check_screenshot_quality(screenshot)
            if not is_valid:
                note_issues.append({
                    'file': screenshot.name,
                    'issues': issues
                })
        
        if note_issues:
            problematic_notes.append({
                'note_id': note_id,
                'total_screenshots': len(screenshots),
                'problematic_screenshots': len(note_issues),
                'details': note_issues
            })
    
    # Print results
    print(f"检查结果:")
    print(f"  总笔记数: {len(note_screenshots)}")
    print(f"  有问题笔记: {len(problematic_notes)}")
    print(f"  正常笔记: {len(note_screenshots) - len(problematic_notes)}")
    print()
    
    if problematic_notes:
        print("有问题笔记列表:")
        print("-"*70)
        
        # Load progress to get titles
        progress = load_progress()
        note_titles = {}
        if progress:
            for note in progress.get('notes', []):
                note_titles[note.get('note_id', '')] = note.get('title', 'Unknown')
        
        for item in problematic_notes:
            note_id = item['note_id']
            title = note_titles.get(note_id, 'Unknown')
            print(f"\n笔记ID: {note_id}")
            print(f"标题: {title}")
            print(f"问题截图: {item['problematic_screenshots']}/{item['total_screenshots']}")
            for detail in item['details']:
                print(f"  - {detail['file']}: {', '.join(detail['issues'])}")
    
    # Save report
    report_path = Path(r"d:\mycode\gbrain\.trae\skills\xhs-ingest\scripts\screenshot_quality_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump({
            'total_notes': len(note_screenshots),
            'problematic_notes_count': len(problematic_notes),
            'problematic_notes': problematic_notes
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n详细报告已保存: {report_path}")
    
    return problematic_notes


if __name__ == "__main__":
    problematic = check_all_screenshots()
    
    if problematic:
        print(f"\n⚠️ 发现 {len(problematic)} 个笔记需要重新截图")
        sys.exit(1)
    else:
        print("\n✅ 所有截图质量正常")
        sys.exit(0)
