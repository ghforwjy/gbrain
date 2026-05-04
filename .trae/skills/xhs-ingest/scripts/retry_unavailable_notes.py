"""
重新获取"无法浏览"笔记的截图
正确做法：从收藏夹列表点击笔记，绝不直接跳转URL！
"""
import subprocess
import time
import sys
import os
from pathlib import Path

IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")
BOARD_ID = "698f3a82000000002502ef57"

def run_cli(command, timeout=30):
    """运行 playwright-cli 命令"""
    full_command = f"playwright-cli {command}"

    result = subprocess.run(
        full_command,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=timeout
    )

    if result.returncode != 0:
        print(f"  错误: {result.stderr[:200]}")
        return None

    return result.stdout

def find_note_in_board(note_title):
    """在收藏夹页面找到笔记的ref"""
    result = run_cli("snapshot")
    if not result:
        return None

    import re

    # 查找包含笔记标题的 link ref
    pattern = rf'link \[ref=(e\d+)\].*?{re.escape(note_title[:10])}'
    match = re.search(pattern, result, re.DOTALL)

    if match:
        return match.group(1)

    return None

def retry_note_from_board(note_id, note_title):
    """从收藏夹点击笔记重新获取截图（正确做法）"""
    print(f"\n重新获取: {note_title} (ID: {note_id})")

    # 1. 确保在收藏夹页面
    print("  返回收藏夹...")
    result = run_cli(f'goto "https://www.xiaohongshu.com/board/{BOARD_ID}"')
    if not result:
        print("  ❌ 返回收藏夹失败")
        return False

    time.sleep(2)

    # 2. 在收藏夹中查找笔记
    print(f"  查找笔记: {note_title}")
    note_ref = find_note_in_board(note_title)

    if not note_ref:
        # 尝试滚动查找
        for i in range(5):
            print(f"  滚动查找 (尝试 {i+1}/5)...")
            run_cli("mousewheel 0 1500")
            time.sleep(1.5)
            note_ref = find_note_in_board(note_title)
            if note_ref:
                break

    if not note_ref:
        print(f"  ❌ 收藏夹中找不到笔记: {note_title}")
        print("  请手动确认该笔记是否在收藏夹中")
        return False

    # 3. 点击笔记（使用鼠标点击，不是直接跳转URL！）
    print(f"  点击笔记 (ref={note_ref})")
    result = run_cli(f"click {note_ref}")
    if not result:
        print("  ❌ 点击失败")
        return False

    time.sleep(3)

    # 4. 检查是否仍然显示"无法浏览"
    result = run_cli("eval \"document.body.innerText.substring(0, 200)\"")
    if result and ("无法浏览" in result or "扫码" in result):
        print("  ⚠️ 笔记显示无法浏览，记录到待确认列表")
        # 记录到文件
        with open("unavailable_notes_confirm.txt", "a", encoding="utf-8") as f:
            f.write(f"{note_title}\t{note_id}\n")
        return False

    # 5. 截图
    screenshot_file = f"{note_id}_slide1.png"
    screenshot_path = IMAGES_DIR / screenshot_file

    result = run_cli(f"screenshot --filename={screenshot_path}")
    if result:
        print(f"  ✅ 截图已保存: {screenshot_path}")
        return True
    else:
        print("  ❌ 截图失败")
        return False

def main():
    """主流程"""
    print("="*60)
    print("重新获取'无法浏览'笔记的截图")
    print("使用正确方法：从收藏夹点击，绝不直接跳转URL！")
    print("="*60)

    # 需要重新获取的笔记
    notes_to_retry = [
        {"id": "637cc220000000000e0314ab", "title": "3分钟精通windows沙盒Sandbox及自定义配置"},
        {"id": "67072e1c000000001a0231c6", "title": "Raptor的主要做法"},
    ]

    # 确保浏览器已打开
    print("\n确保浏览器已打开...")
    result = run_cli("eval \"window.location.href\"")
    if not result:
        print("浏览器未打开，请先运行:")
        print("  playwright-cli open https://www.xiaohongshu.com --headed")
        print("  playwright-cli state-load xhs_auth.json")
        return

    print(f"当前页面: {result.strip()}")

    # 逐个重试
    success_count = 0
    failed_notes = []

    for note in notes_to_retry:
        if retry_note_from_board(note["id"], note["title"]):
            success_count += 1
        else:
            failed_notes.append(note)

        # 等待一段时间，避免风控
        time.sleep(3)

    print("\n" + "="*60)
    print(f"重试完成: {success_count}/{len(notes_to_retry)}")
    if failed_notes:
        print("\n仍然无法获取的笔记（请手动确认）:")
        for note in failed_notes:
            print(f"  - {note['title']} ({note['id']})")
    print("="*60)

if __name__ == "__main__":
    main()
