"""
单笔记处理脚本 (playwright-cli 版)
每次处理1个笔记：点击 -> 截图 -> OCR -> 导入GBrain

设计约束:
- 所有输出必须使用 flush=True
- 禁止使用 Unicode 特殊字符
- 必须通过 xhs_cli.py 调用浏览器操作
"""

import sys
import os
import time
from pathlib import Path

# 修复Windows控制台中文显示
if sys.platform == 'win32':
    import codecs
    try:
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer)
            sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer)
    except:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_cli import (
    setup_session, get_current_url, click_note_by_index,
    check_popup_opened, close_popup, screenshot_slides,
    save_state, goto, log
)
from xhs_progress import (
    load_progress, mark_note_completed, mark_note_failed,
    mark_note_processing, save_progress
)
from xhs_ingest_v2 import process_note as xhs_process_note

BOARD_ID = "698f3a82000000002502ef57"
USER_ID = "608286f10000000001009ad1"

# 截图目录使用项目根目录下的 .playwright-cli，自动检测
from xhs_cli import PROJECT_ROOT
SCREENSHOT_DIR = PROJECT_ROOT / ".playwright-cli"


def process_single_note_by_index(note_idx):
    """处理单个笔记的完整流程
    
    状态机:
    1. 设置浏览器会话
    2. 检查当前位置
    3. 点击笔记
    4. 检查弹窗
    5. 截图
    6. OCR处理
    7. 关闭弹窗
    8. 保存状态
    """
    log("=" * 60)
    log(f"处理笔记 [{note_idx}]")
    log("=" * 60)
    
    # 1. 设置浏览器会话
    log("[Step 1] 设置浏览器会话...")
    if not setup_session(headed=True):
        log("[FAIL] 无法设置浏览器会话")
        return False
    
    # 2. 检查当前位置
    log("[Step 2] 检查当前页面位置...")
    current_url = get_current_url()
    log(f"当前页面: {current_url}", indent=1)
    
    if "/board/698f3a82000000002502ef57" in current_url:
        log("[OK] 当前已在专辑页面", indent=1)
    elif "/explore/" in current_url:
        log("当前在笔记详情页，关闭弹窗...", indent=1)
        close_popup()
        time.sleep(1)
        goto("https://www.xiaohongshu.com/board/698f3a82000000002502ef57")
        time.sleep(3)
    else:
        log("导航到专辑页面...", indent=1)
        goto("https://www.xiaohongshu.com/board/698f3a82000000002502ef57")
        time.sleep(3)
    
    # 3. 点击笔记
    log("[Step 3] 点击笔记...")
    note_id = click_note_by_index(note_idx)
    if not note_id:
        log("[FAIL] 点击笔记失败")
        return False
    
    # 4. 检查弹窗
    log("[Step 4] 检查笔记弹窗...")
    time.sleep(2)
    if not check_popup_opened():
        log("[FAIL] 笔记弹窗未打开")
        return False
    log("[OK] 笔记内容已加载", indent=1)
    
    # 5. 截图
    log("[Step 5] 截图...")
    total_slides = screenshot_slides(note_id, str(SCREENSHOT_DIR))
    log(f"共 {total_slides} 张图片", indent=1)
    
    # 6. OCR处理
    log("[Step 6] OCR处理...")
    title = f"笔记_{note_idx}"
    author = "未知"
    
    result = xhs_process_note(
        note_id=note_id,
        title=title,
        author=author,
        total_slides=total_slides,
        screenshot_dir=str(SCREENSHOT_DIR),
    )
    
    if result:
        md_file, slug, slides_data = result
        log(f"[OK] Markdown已保存: {md_file}", indent=1)
        
        # 标记完成
        progress = load_progress()
        mark_note_completed(progress, note_idx)
        save_progress(progress)
        log(f"[OK] 笔记 [{note_idx}] 处理完成", indent=1)
    else:
        log("[FAIL] OCR处理失败")
        return False
    
    # 7. 关闭弹窗
    log("[Step 7] 关闭弹窗...")
    close_popup()
    
    # 8. 保存状态
    log("[Step 8] 保存浏览器状态...")
    save_state()
    
    log("=" * 60)
    log(f"[OK] 笔记 [{note_idx}] 全部完成")
    log("=" * 60)
    
    return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python process_one_note_cli.py <note_index>")
        sys.exit(1)
    
    note_idx = int(sys.argv[1])
    success = process_single_note_by_index(note_idx)
    sys.exit(0 if success else 1)
