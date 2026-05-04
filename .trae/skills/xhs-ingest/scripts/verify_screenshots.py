"""
验证所有截图的质量
检查是否有"无法浏览"的笔记
"""
import os
from pathlib import Path
from PIL import Image
import pytesseract

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")

def verify_screenshot(image_path):
    """验证单张截图"""
    try:
        # Open image
        img = Image.open(image_path)
        
        # Use OCR to check content
        text = pytesseract.image_to_string(img, lang='chi_sim')
        
        # Check if it's a "cannot view" page
        if "当前笔记暂时无法浏览" in text or "无法浏览" in text:
            return False, "笔记无法浏览"
        
        # Check if content is too short
        if len(text.strip()) < 10:
            return False, "内容太短"
        
        return True, "正常"
        
    except Exception as e:
        return False, f"验证失败: {e}"

def verify_all_screenshots():
    """验证所有截图"""
    print("="*60)
    print("验证截图质量")
    print("="*60)
    
    if not IMAGES_DIR.exists():
        print(f"错误: 图片目录不存在: {IMAGES_DIR}")
        return
    
    # Get all screenshot files
    screenshots = sorted(IMAGES_DIR.glob("*_slide1.png"))
    
    print(f"找到 {len(screenshots)} 张截图")
    print()
    
    valid_count = 0
    invalid_count = 0
    invalid_notes = []
    
    for screenshot in screenshots:
        note_id = screenshot.stem.split('_slide')[0]
        is_valid, message = verify_screenshot(screenshot)
        
        if is_valid:
            valid_count += 1
            print(f"✅ {note_id}: {message}")
        else:
            invalid_count += 1
            invalid_notes.append(note_id)
            print(f"❌ {note_id}: {message}")
    
    print()
    print("="*60)
    print(f"验证结果:")
    print(f"  正常: {valid_count}")
    print(f"  异常: {invalid_count}")
    if invalid_notes:
        print(f"  异常笔记: {invalid_notes}")
    print("="*60)

if __name__ == "__main__":
    verify_all_screenshots()
