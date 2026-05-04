"""
简单验证截图质量（不依赖OCR）
检查文件大小和尺寸
"""
from pathlib import Path
from PIL import Image

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")

def verify_screenshot(image_path):
    """验证单张截图"""
    try:
        # Open image
        img = Image.open(image_path)
        width, height = img.size
        
        # Check size
        if width < 800 or height < 600:
            return False, f"尺寸过小 ({width}x{height})"
        
        # Check file size
        file_size = image_path.stat().st_size
        if file_size < 10000:  # Less than 10KB
            return False, f"文件过小 ({file_size} bytes)"
        
        # Check if mostly white (blank page)
        # Convert to grayscale and check average brightness
        gray = img.convert('L')
        # Sample center area
        center_x = width // 2
        center_y = height // 2
        sample_size = min(100, width // 4, height // 4)
        
        total_brightness = 0
        pixel_count = 0
        
        for y in range(center_y - sample_size, center_y + sample_size, 10):
            for x in range(center_x - sample_size, center_x + sample_size, 10):
                if 0 <= x < width and 0 <= y < height:
                    total_brightness += gray.getpixel((x, y))
                    pixel_count += 1
        
        if pixel_count > 0:
            avg_brightness = total_brightness / pixel_count
            if avg_brightness > 250:  # Mostly white
                return False, f"mostly_blank (亮度{avg_brightness:.1f})"
        
        return True, f"正常 ({width}x{height}, {file_size/1024:.1f}KB)"
        
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
