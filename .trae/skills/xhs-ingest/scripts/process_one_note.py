"""
单笔记处理脚本 - 每次处理1个笔记，检查界面状态
用法: python process_one_note.py [note_index]
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import (
    connect_browser, close_popup, click_note_by_id, screenshot_all_slides,
    navigate_to_board, human_delay, load_progress, save_progress, update_phase
)
from xhs_progress import mark_note_completed, mark_note_failed, mark_note_processing
from xhs_ingest_v2 import process_note as xhs_process_note
from pathlib import Path

BOARD_ID = "698f3a82000000002502ef57"
SCREENSHOT_DIR = Path(r"d:\mycode\gbrain\.playwright-cli")

def process_single_note_by_index(note_idx):
    """Process a single note by index, with full UI checks."""
    progress = load_progress()
    if not progress:
        print("错误: 没有进度文件")
        return False

    # Get note info
    note_info = None
    for note in progress['notes']:
        if note['index'] == note_idx:
            note_info = note
            break

    if not note_info:
        print(f"错误: 笔记 [{note_idx}] 不存在")
        return False

    note_id = note_info.get('note_id')
    if not note_id:
        print(f"错误: 笔记 [{note_idx}] 没有note_id")
        return False

    print(f"\n{'='*60}")
    print(f"处理笔记 [{note_idx}] id={note_id}")
    print(f"标题: {note_info.get('title', 'Unknown')}")
    print(f"{'='*60}")

    # Connect to browser
    print("\n[Step 1] 连接浏览器...")
    p, browser, page = connect_browser()
    print(f"  当前页面: {page.url}")

    # Check if on error page
    if '/404' in page.url or 'error' in page.url:
        print("  ⚠️ 当前在错误页面，导航到收藏夹...")
        navigate_to_board(page)
        human_delay(2, 3)

    # If on note page, close popup and go to board
    if '/explore/' in page.url:
        print("  当前在笔记页面，关闭弹框...")
        close_popup(page)
        human_delay(1, 2)

    # Navigate to board
    print("\n[Step 2] 导航到收藏夹...")
    navigate_to_board(page)
    human_delay(2, 3)

    # Check board loaded
    note_count = page.evaluate("document.querySelectorAll('section.note-item').length")
    print(f"  收藏夹已加载，共 {note_count} 个笔记卡片")

    if note_count == 0:
        print("  ❌ 收藏夹为空，可能需要登录")
        browser.close()
        return False

    # Click note
    print(f"\n[Step 3] 点击笔记 {note_id}...")
    clicked_id, title, author = click_note_by_id(page, note_id)

    # Check current URL after click
    current_url = page.url
    print(f"  点击后URL: {current_url}")

    if not clicked_id:
        if '/404' in current_url:
            print("  ❌ 笔记无法访问(404)")
            mark_note_failed(progress, note_idx, "笔记无法访问(404)")
            save_progress(progress)
            browser.close()
            return False
        elif '/explore/' in current_url and note_id in current_url:
            # Page navigated directly to note (not popup)
            print("  ✅ 页面已导航到笔记详情页")
            # Get title from page
            title = page.evaluate("document.querySelector('h1, .title, [class*=\"title\"]')?.textContent?.trim() || 'Unknown'")
            author = page.evaluate("document.querySelector('.author, .name, [class*=\"author\"]')?.textContent?.trim() || 'Unknown'")
        else:
            print("  ❌ 无法打开笔记")
            mark_note_failed(progress, note_idx, "笔记不在当前视图")
            save_progress(progress)
            browser.close()
            return False
    else:
        print(f"  ✅ 弹框已打开: {title}")

    # Check if popup or note content is present
    has_content = page.evaluate("""() => {
        const selectors = ['.note-detail', '.note-popup', '[class*="note-detail"]', '[class*="popup"]', '.interaction-container', '.content', '.note-content'];
        for (const sel of selectors) {
            const el = document.querySelector(sel);
            if (el && el.offsetParent !== null) return true;
        }
        return false;
    }""")

    if not has_content:
        print("  ❌ 笔记内容未正确加载")
        mark_note_failed(progress, note_idx, "笔记内容未加载")
        save_progress(progress)
        browser.close()
        return False

    print("  ✅ 笔记内容确认已加载")

    # Screenshot
    print(f"\n[Step 4] 截图...")
    total_slides = screenshot_all_slides(page, note_id)
    print(f"  共 {total_slides} 张图片")

    # OCR
    print(f"\n[Step 5] OCR处理...")
    result = xhs_process_note(
        note_id=note_id,
        title=title,
        author=author,
        total_slides=total_slides,
        screenshot_dir=str(SCREENSHOT_DIR),
    )

    if result:
        md_file, slug, slides_data = result
        print(f"  ✅ Markdown已保存: {md_file}")

        # Mark as completed
        mark_note_completed(progress, note_idx)
        for note in progress['notes']:
            if note['index'] == note_idx:
                note['title'] = title
                note['author'] = author
                break
        save_progress(progress)
        print(f"\n✅ 笔记 [{note_idx}] 《{title}》处理完成！")

        # Close popup
        print("\n[Step 6] 关闭弹框...")
        close_popup(page)
        print("  ✅ 弹框已关闭")

        browser.close()
        return True
    else:
        print("  ❌ OCR处理失败")
        mark_note_failed(progress, note_idx, "OCR处理失败")
        save_progress(progress)
        browser.close()
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        note_idx = int(sys.argv[1])
    else:
        # Get next pending note
        progress = load_progress()
        note_idx = None
        for n in progress.get('pending_notes', []):
            note_idx = n['index']
            break
        if note_idx is None:
            print("没有待处理的笔记")
            sys.exit(1)

    success = process_single_note_by_index(note_idx)
    sys.exit(0 if success else 1)
