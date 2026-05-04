"""
使用 playwright-cli 批量重新处理截图有问题的笔记
"""
import subprocess
import json
import time
import os
import sys
from pathlib import Path

# 配置
SCREENSHOT_DIR = Path(r"d:\mycode\gbrain\.playwright-cli")
IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")
AUTH_FILE = Path(r"d:\mycode\gbrain\.playwright-cli\xhs_auth.json")
REPORT_FILE = Path(r"d:\mycode\gbrain\.trae\skills\xhs-ingest\scripts\screenshot_quality_report.json")

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

def load_problematic_notes():
    """从报告加载有问题的笔记"""
    with open(REPORT_FILE, 'r', encoding='utf-8') as f:
        report = json.load(f)
    return report.get('problematic_notes', [])

def get_note_info_from_progress(note_id):
    """从进度文件获取笔记信息"""
    sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))
    from xhs_progress import load_progress
    
    progress = load_progress()
    if not progress:
        return None
    
    for note in progress['notes']:
        if note.get('note_id') == note_id:
            return note
    return None

def find_note_in_board(note_title):
    """在收藏夹页面找到笔记的ref"""
    # 获取页面快照
    result = run_cli("snapshot")
    if not result:
        return None
    
    # 解析快照找到笔记链接
    # 笔记标题通常出现在 link 元素中
    import re
    
    # 查找包含笔记标题的 link ref
    pattern = rf'link \[ref=(e\d+)\].*?{re.escape(note_title[:10])}'
    match = re.search(pattern, result, re.DOTALL)
    
    if match:
        return match.group(1)
    
    # 如果没找到，尝试搜索前10个字符
    if len(note_title) > 10:
        pattern = rf'link \[ref=(e\d+)\].*?{re.escape(note_title[:10])}'
        match = re.search(pattern, result, re.DOTALL)
        if match:
            return match.group(1)
    
    return None

def process_note_with_cli(note_id, note_title):
    """使用 playwright-cli 处理单个笔记
    
    关键：必须使用鼠标点击，不能直接跳转URL！
    """
    print(f"\n处理笔记: {note_title} (ID: {note_id})")
    
    # 1. 确保在收藏夹页面
    result = run_cli('goto "https://www.xiaohongshu.com/board/698f3a82000000002502ef57"')
    if not result:
        print("  ❌ 返回收藏夹失败")
        return False
    
    time.sleep(2)
    
    # 2. 在收藏夹中找到笔记并点击
    print(f"  查找笔记: {note_title}")
    note_ref = find_note_in_board(note_title)
    
    if not note_ref:
        # 如果找不到，尝试滚动页面
        print("  笔记不在当前视图，尝试滚动...")
        run_cli("mousewheel 0 1000")
        time.sleep(1)
        note_ref = find_note_in_board(note_title)
    
    if not note_ref:
        print(f"  ❌ 找不到笔记: {note_title}")
        print("  尝试在收藏夹中滚动查找...")
        # 多次滚动尝试找到笔记
        for scroll_attempt in range(5):
            run_cli("mousewheel 0 1500")
            time.sleep(1.5)
            note_ref = find_note_in_board(note_title)
            if note_ref:
                break
        
        if not note_ref:
            print("  ❌ 收藏夹中找不到笔记，跳过")
            print(f"  请手动检查笔记: {note_title}")
            return False
    
    # 3. 点击笔记
    print(f"  点击笔记 (ref={note_ref})")
    result = run_cli(f"click {note_ref}")
    if not result:
        print("  ❌ 点击失败")
        return False
    
    time.sleep(2)
    
    # 4. 截图
    screenshot_file = f"{note_id}_slide1.png"
    screenshot_path = IMAGES_DIR / screenshot_file
    
    result = run_cli(f"screenshot --filename={screenshot_path}")
    if result:
        print(f"  ✅ 截图已保存: {screenshot_path}")
    else:
        print("  ❌ 截图失败")
        return False
    
    # 5. 返回收藏夹
    result = run_cli('goto "https://www.xiaohongshu.com/board/698f3a82000000002502ef57"')
    if not result:
        print("  ⚠️ 返回收藏夹失败")
    
    time.sleep(1)
    return True

def main():
    """主流程"""
    print("="*60)
    print("批量重新处理截图有问题的笔记")
    print("使用 playwright-cli")
    print("="*60)
    
    # 1. 加载有问题的笔记
    problematic_notes = load_problematic_notes()
    print(f"找到 {len(problematic_notes)} 个有问题的笔记")
    
    # 2. 浏览器应该已经打开并登录
    print("\n假设浏览器已打开并登录...")
    print("如果浏览器未打开，请先运行:")
    print("  playwright-cli open https://www.xiaohongshu.com --headed")
    print("  playwright-cli state-load xhs_auth.json")
    
    # 3. 逐个处理
    success_count = 0
    failed_notes = []
    
    for i, item in enumerate(problematic_notes, 1):
        note_id = item['note_id']
        
        # 获取笔记标题
        note_info = get_note_info_from_progress(note_id)
        note_title = note_info.get('title', 'Unknown') if note_info else 'Unknown'
        
        print(f"\n[{i}/{len(problematic_notes)}] {note_title}")
        
        if process_note_with_cli(note_id, note_title):
            success_count += 1
        else:
            failed_notes.append(note_id)
        
        # 等待，避免风控
        time.sleep(3)
    
    # 4. 报告结果
    print("\n" + "="*60)
    print(f"处理完成: {success_count}/{len(problematic_notes)}")
    if failed_notes:
        print(f"失败笔记: {failed_notes}")
    print("="*60)

if __name__ == "__main__":
    main()
