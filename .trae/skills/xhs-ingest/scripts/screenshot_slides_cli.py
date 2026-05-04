"""
笔记截图脚本 (playwright-cli 版)
截图笔记弹框中的所有图片

用法:
    python screenshot_slides_cli.py [note_id]
    # 如果不提供 note_id，自动从当前 URL 提取
"""

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_cli import (
    run_cli, get_current_url, eval_js_raw, check_cli_installed, PROJECT_ROOT
)

SCREENSHOT_DIR = PROJECT_ROOT / ".playwright-cli"


def get_slide_count() -> int:
    """获取笔记图片数量"""
    result = eval_js_raw("""
        (() => {
            const indicators = document.querySelectorAll('.swiper-pagination-bullet, .slide-indicator, [class*="indicator"]');
            if (indicators.length > 0) return indicators.length;
            const images = document.querySelectorAll('.swiper-slide img, .note-content img, .detail-content img');
            return images.length;
        })()
    """)
    try:
        return int(result) if result else 1
    except:
        return 1


def screenshot(filepath: str) -> bool:
    """截图当前页面"""
    result = run_cli(f'screenshot "{filepath}"', timeout=10)
    return result.get("success", False)


def press(key: str) -> bool:
    """按键"""
    result = run_cli(f"press {key}", timeout=5)
    return result.get("success", False)


def screenshot_slides(note_id: str = None, output_dir: str = None) -> int:
    """截图笔记的所有图片"""
    out_dir = Path(output_dir or SCREENSHOT_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    # 检查 CLI
    if not check_cli_installed():
        print("[FAIL] playwright-cli 未安装")
        return 0

    # 获取当前URL，提取note_id
    if not note_id:
        url = get_current_url()
        if "/explore/" in url:
            note_id = url.split("/explore/")[-1].split("?")[0]
        else:
            print("[FAIL] 无法从URL获取笔记ID")
            return 0

    print(f"[INFO] 笔记ID: {note_id}")

    # 获取总页数
    total = get_slide_count()
    print(f"[INFO] 共 {total} 张图片")

    if total == 0:
        print("[WARN] 未检测到图片，将截图1张")
        total = 1

    # 截图所有图片
    for i in range(1, total + 1):
        filename = out_dir / f"{note_id}_{i:03d}.png"
        print(f"\n[Step] 截图 {i}/{total}...")

        if screenshot(str(filename)):
            print(f"  [OK] 已保存: {filename}")
        else:
            print(f"  [FAIL] 截图失败")

        # 如果不是最后一张，切换到下一张
        if i < total:
            print("  [INFO] 切换到下一张...")
            press("ArrowRight")
            time.sleep(1.5)

    print(f"\n{'='*50}")
    print(f"[OK] 共截图 {total} 张，保存到: {out_dir}")
    print(f"{'='*50}")

    return total


if __name__ == "__main__":
    note_id = sys.argv[1] if len(sys.argv) > 1 else None
    count = screenshot_slides(note_id)
    sys.exit(0 if count > 0 else 1)
