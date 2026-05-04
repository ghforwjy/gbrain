#!/usr/bin/env python3
"""
小红书收藏导入 - 统一入口脚本
Agent只需要运行这一个脚本，其他全部自动处理。

用法:
    python xhs_ingest.py --mode auto          # 自动模式：打开下一个待处理笔记
    python xhs_ingest.py --mode search "标题"  # 搜索模式：搜索指定标题并打开
    python xhs_ingest.py --mode screenshot     # 截图模式：对当前打开的笔记截图
    python xhs_ingest.py --mode process        # 处理模式：OCR + 生成Markdown
    python xhs_ingest.py --mode close          # 关闭弹窗，回到收藏夹
    python xhs_ingest.py --mode status         # 查看当前进度

流程说明:
    处理一个笔记的完整流程 = auto -> screenshot -> process -> close
    或者 = search -> screenshot -> process -> close
"""

import sys
import os
import time
import random
import json
import base64
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
    setup_session, get_current_url, goto, eval_js_raw,
    real_click, check_popup_opened, close_popup, save_state,
    log, run_cli, click_note_by_index, screenshot_slides,
    collect_all_notes_from_board, search_note_in_board,
    random_browse_behavior
)
from xhs_progress import (
    load_progress, mark_note_completed, mark_note_failed,
    mark_note_processing, save_progress, get_progress_summary,
    get_next_pending_index
)
from xhs_ingest_v2 import process_note as xhs_process_note

BOARD_ID = "698f3a82000000002502ef57"
USER_ID = "608286f10000000001009ad1"
SCREENSHOT_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / ".playwright-cli"


def random_sleep(base: float, variance: float = 0.5):
    """随机时间间隔，模拟人工操作"""
    sleep_time = base + random.uniform(-variance, variance)
    sleep_time = max(sleep_time, 0.3)
    time.sleep(sleep_time)


# ============ 搜索相关函数 ============

def find_search_input() -> dict:
    """查找搜索输入框元素"""
    result = eval_js_raw("""
        (() => {
            const selectors = [
                'input[placeholder*="搜索"]',
                'input[placeholder*="搜"]',
                '.search-input input',
                '.search-bar input',
                'input[type="search"]',
                '#search-input',
                '.header-search input',
                'input[placeholder]'
            ];
            
            for (const selector of selectors) {
                const el = document.querySelector(selector);
                if (el && el.offsetParent !== null) {
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 50 && rect.height > 20) {
                        return JSON.stringify({
                            found: true,
                            x: Math.round(rect.left + rect.width / 2),
                            y: Math.round(rect.top + rect.height / 2),
                            placeholder: el.placeholder || ''
                        });
                    }
                }
            }
            
            const allInputs = Array.from(document.querySelectorAll('input'));
            for (const input of allInputs) {
                const rect = input.getBoundingClientRect();
                const placeholder = (input.placeholder || '').toLowerCase();
                if (rect.width > 100 && rect.height > 30 && 
                    (placeholder.includes('search') || placeholder.includes('搜索') || 
                     placeholder.includes('搜') || input.type === 'search')) {
                    return JSON.stringify({
                        found: true,
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2),
                        placeholder: input.placeholder || ''
                    });
                }
            }
            
            return JSON.stringify({found: false});
        })()
    """)
    try:
        return json.loads(result) if result else {"found": False}
    except:
        return {"found": False}


def search_note_by_title(title: str) -> str:
    """搜索笔记并打开
    
    返回: note_id 或空字符串
    """
    log("=" * 60)
    log(f"搜索笔记: {title}")
    log("=" * 60)
    
    # 1. 设置浏览器会话
    if not setup_session(headed=True):
        log("[FAIL] 无法设置浏览器会话")
        return ""
    
    # 2. 确保在小红书
    current_url = get_current_url()
    if "xiaohongshu.com" not in current_url:
        goto("https://www.xiaohongshu.com")
        random_sleep(3.0, 0.5)
    
    # 3. 点击搜索框
    log("点击搜索框...")
    pos = find_search_input()
    if not pos.get("found"):
        log("[FAIL] 未找到搜索输入框")
        return ""
    
    x, y = pos.get("x", 0), pos.get("y", 0)
    log(f"搜索框位置: ({x}, {y})", indent=1)
    
    if not real_click(x, y):
        log("[FAIL] 点击搜索框失败")
        return ""
    random_sleep(0.8, 0.3)
    
    # 4. 清空并输入（模拟人类键盘操作，避免直接设 input.value）
    log("输入搜索关键词...")
    # 用 Ctrl+A 全选 + Backspace 删除，而非 JS 直接设 input.value
    run_cli("press Control+a", timeout=2)
    random_sleep(0.1, 0.05)
    run_cli("press Backspace", timeout=2)
    random_sleep(0.3, 0.15)
    
    # 中文输入方案：使用 JS 逐字触发完整 InputEvent（含 inputType/data）
    # playwright-cli type 命令不支持中文，所以用 JS 但确保事件链完整
    # 关键区别：之前用 input.value = '整段文字'，现在逐字触发 InputEvent
    encoded_title = base64.b64encode(title.encode('utf-8')).decode('utf-8')
    eval_js_raw(f"""
        (() => {{
            const input = document.querySelector('input[placeholder*="搜索"], input[placeholder*="搜"], .search-input input, .search-bar input, input[type="search"], .header-search input');
            if (!input) return 'not_found';
            const query = atob('{encoded_title}');
            // 逐字输入，触发完整 InputEvent 事件链
            for (let i = 0; i < query.length; i++) {{
                const char = query[i];
                // 1. keydown
                input.dispatchEvent(new KeyboardEvent('keydown', {{
                    key: char, code: 'Key' + char.toUpperCase(), bubbles: true
                }}));
                // 2. beforeinput（含 inputType 和 data，这是真实打字的关键特征）
                input.dispatchEvent(new InputEvent('beforeinput', {{
                    inputType: 'insertText', data: char, bubbles: true, cancelable: true
                }}));
                // 3. 修改 value
                input.value = query.substring(0, i + 1);
                // 4. input（含 inputType 和 data）
                input.dispatchEvent(new InputEvent('input', {{
                    inputType: 'insertText', data: char, bubbles: true
                }}));
                // 5. keyup
                input.dispatchEvent(new KeyboardEvent('keyup', {{
                    key: char, code: 'Key' + char.toUpperCase(), bubbles: true
                }}));
            }}
            // 6. change
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
            return 'typed';
        }})()
    """)
    random_sleep(1.0, 0.3)
    
    # 5. 提交搜索
    log("提交搜索...")
    result = run_cli("press Enter", timeout=10)
    if not result.get("success"):
        log("[FAIL] 提交搜索失败")
        return ""
    random_sleep(2.5, 0.5)
    
    # 6. 获取搜索结果并点击第一个
    log("获取搜索结果...")
    search_result = eval_js_raw("""
        (() => {
            const cards = document.querySelectorAll('section.note-item, a[href*="/explore/"]');
            for (const card of cards) {
                const rect = card.getBoundingClientRect();
                const link = card.closest('a[href*="/explore/"]') || card;
                const href = link.href || '';
                const match = href.match(/explore\/([a-f0-9]+)/);
                const noteId = match ? match[1] : '';
                if (noteId && rect.top >= 100 && rect.top < window.innerHeight) {
                    return JSON.stringify({
                        found: true,
                        noteId: noteId,
                        x: Math.round(rect.left + rect.width / 2),
                        y: Math.round(rect.top + rect.height / 2)
                    });
                }
            }
            return JSON.stringify({found: false});
        })()
    """)
    
    try:
        target = json.loads(search_result) if search_result else {"found": False}
    except:
        target = {"found": False}
    
    if not target.get("found"):
        log("[FAIL] 未找到搜索结果")
        return ""
    
    note_id = target.get("noteId", "")
    tx, ty = target.get("x", 0), target.get("y", 0)
    log(f"找到笔记: {note_id}, 坐标: ({tx}, {ty})", indent=1)
    
    # 7. 点击打开
    if not real_click(tx, ty):
        log("[FAIL] 点击笔记失败")
        return ""
    
    random_sleep(2.0, 0.5)
    
    if check_popup_opened():
        log("[OK] 笔记弹窗已打开")
        save_state()
        return note_id
    else:
        log("[WARN] 弹窗检测失败，但可能已打开")
        save_state()
        return note_id


# ============ 自动模式 ============

def auto_open_next_note() -> str:
    """自动打开下一个待处理笔记（翻页模式）
    
    返回: note_id 或空字符串
    """
    log("=" * 60)
    log("自动模式：打开下一个待处理笔记")
    log("=" * 60)
    
    # 1. 设置浏览器会话
    if not setup_session(headed=True):
        log("[FAIL] 无法设置浏览器会话")
        return ""
    
    # 2. 检查进度
    progress = load_progress()
    if not progress:
        log("[WARN] 没有进度记录，请先初始化")
        return ""
    
    next_idx = get_next_pending_index(progress)
    if next_idx is None:
        log("[OK] 所有笔记已处理完成！")
        return ""
    
    log(f"下一个待处理笔记索引: {next_idx}")
    
    # 3. 确保在收藏夹页面
    current_url = get_current_url()
    if "/board/" not in current_url and "tab=fav" not in current_url:
        log("导航到收藏夹...")
        goto(f"https://www.xiaohongshu.com/board/{BOARD_ID}")
        random_sleep(3.0, 0.5)
    
    # 随机浏览行为（模拟人类浏览习惯）
    random_browse_behavior()
    
    # 4. 点击笔记
    note_id = click_note_by_index(next_idx)
    if note_id:
        mark_note_processing(progress, next_idx, note_id)
        log(f"[OK] 已打开笔记 [{next_idx}]: {note_id}")
        save_state()
        return note_id
    else:
        log(f"[FAIL] 无法打开笔记 [{next_idx}]")
        mark_note_failed(progress, next_idx, "无法打开笔记")
        return ""


# ============ 截图模式 ============

def do_screenshot() -> int:
    """对当前打开的笔记截图
    
    返回: 截图数量
    """
    log("=" * 60)
    log("截图模式")
    log("=" * 60)
    
    # 1. 设置浏览器会话（截图模式不需要导航首页，保持当前页面）
    if not setup_session(headed=True, navigate_home=False):
        log("[FAIL] 无法设置浏览器会话")
        return 0
    
    # 2. 检查是否有弹窗
    if not check_popup_opened():
        log("[WARN] 笔记弹窗未打开，尝试重新打开当前笔记...")
        
        # 查找当前处理中的笔记
        progress = load_progress()
        current_note = None
        if progress:
            for note in progress.get('notes', []):
                if note.get('status') == 'processing':
                    current_note = note
                    break
        
        if current_note:
            note_idx = current_note['index']
            note_id_saved = current_note.get('note_id', '')
            log(f"尝试重新打开笔记 [{note_idx}]: {note_id_saved}...")
            
            # 确保在收藏夹页面
            current_url = get_current_url()
            if "/board/" not in current_url and "tab=fav" not in current_url:
                goto(f"https://www.xiaohongshu.com/board/{BOARD_ID}")
                random_sleep(3.0, 0.5)
            
            # 点击笔记
            note_id = click_note_by_index(note_idx)
            if note_id:
                log(f"[OK] 已重新打开笔记 [{note_idx}]: {note_id}")
                random_sleep(2.0, 0.5)
            else:
                log("[FAIL] 无法重新打开笔记")
                return 0
        else:
            log("[FAIL] 没有找到处理中的笔记，请先运行 auto 或 search 模式")
            return 0
    
    # 3. 再次检查弹窗
    if not check_popup_opened():
        log("[FAIL] 确认没有笔记弹窗")
        return 0
    
    # 4. 获取note_id
    note_id_result = eval_js_raw("""
        (() => {
            const link = document.querySelector('a[href*="/explore/"]');
            if (link) {
                const match = link.href.match(/explore\/([a-f0-9]+)/);
                return match ? match[1] : '';
            }
            return '';
        })()
    """)
    note_id = note_id_result or "unknown"
    log(f"笔记ID: {note_id}")
    
    # 5. 截图
    total = screenshot_slides(note_id, str(SCREENSHOT_DIR))
    log(f"[OK] 截图完成: {total} 张")
    
    # 6. 更新进度
    progress = load_progress()
    if progress:
        for note in progress.get('notes', []):
            if note.get('note_id') == note_id:
                from xhs_progress import update_phase
                update_phase(progress, note['index'], 'phase2_screenshot', 'completed',
                           total_slides=total, screenshot_dir=str(SCREENSHOT_DIR))
                break
    
    save_state()
    return total


# ============ 处理模式 ============

def do_process() -> bool:
    """OCR + 生成Markdown
    
    返回: 是否成功
    """
    log("=" * 60)
    log("处理模式：OCR + 生成Markdown")
    log("=" * 60)
    
    progress = load_progress()
    if not progress:
        log("[WARN] 没有进度记录")
        return False
    
    # 找到当前处理中的笔记
    current_note = None
    for note in progress.get('notes', []):
        if note.get('status') == 'processing':
            current_note = note
            break
    
    if not current_note:
        log("[WARN] 没有处理中的笔记")
        return False
    
    note_id = current_note.get('note_id', '')
    title = current_note.get('title', f'笔记_{current_note["index"]}')
    author = current_note.get('author', '未知')
    
    if not note_id:
        log("[FAIL] 笔记没有note_id")
        return False
    
    # 查找截图
    screenshots = sorted(SCREENSHOT_DIR.glob(f"{note_id}_*.png"))
    if not screenshots:
        log(f"[FAIL] 没有找到截图文件: {SCREENSHOT_DIR}/{note_id}_*.png")
        return False
    
    total_slides = len(screenshots)
    log(f"找到 {total_slides} 张截图")
    
    # OCR处理
    result = xhs_process_note(
        note_id=note_id,
        title=title,
        author=author,
        total_slides=total_slides,
        screenshot_dir=str(SCREENSHOT_DIR),
    )
    
    if result:
        md_file, slug, slides_data = result
        log(f"[OK] Markdown已保存: {md_file}")
        
        # 标记完成
        mark_note_completed(progress, current_note['index'])
        save_progress(progress)
        log(f"[OK] 笔记处理完成")
        return True
    else:
        log("[FAIL] OCR处理失败")
        return False


# ============ 关闭模式 ============

def do_close() -> bool:
    """关闭弹窗，回到收藏夹"""
    log("=" * 60)
    log("关闭弹窗，回到收藏夹")
    log("=" * 60)
    
    if not setup_session(headed=True, navigate_home=False):
        log("[FAIL] 无法设置浏览器会话")
        return False
    
    close_popup()
    random_sleep(1.0, 0.3)
    
    # 回到收藏夹
    current_url = get_current_url()
    if "/board/" not in current_url and "tab=fav" not in current_url:
        goto(f"https://www.xiaohongshu.com/board/{BOARD_ID}")
        random_sleep(2.0, 0.3)
    
    save_state()
    log("[OK] 已回到收藏夹")
    return True


# ============ 状态模式 ============

def do_status():
    """查看当前进度"""
    print(get_progress_summary())


# ============ 主入口 ============

def main():
    if len(sys.argv) < 2:
        print("""
小红书收藏导入 - 统一入口

用法:
    # 方式1：all 模式（推荐，一次完成所有操作）
    python xhs_ingest.py --mode all

    # 方式2：collect + search-open 模式（高效，先收集再搜索定位）
    python xhs_ingest.py --mode collect                    # 翻页收集所有笔记标题
    python xhs_ingest.py --mode search-open "笔记标题关键词"  # 搜索并打开指定笔记
    python xhs_ingest.py --mode screenshot                 # 截图
    python xhs_ingest.py --mode process                    # OCR + 生成Markdown
    python xhs_ingest.py --mode close                      # 关闭弹窗

    # 方式3：分步操作（旧方式）
    python xhs_ingest.py --mode auto          # 自动模式：打开下一个待处理笔记
    python xhs_ingest.py --mode search "标题"  # 搜索模式：搜索指定标题并打开
    python xhs_ingest.py --mode screenshot     # 截图模式
    python xhs_ingest.py --mode process        # 处理模式
    python xhs_ingest.py --mode close          # 关闭弹窗
    python xhs_ingest.py --mode status         # 查看当前进度

高效流程（推荐）:
    1. 先收集所有笔记标题：
       python xhs_ingest.py --mode collect
    
    2. 查看笔记列表，选择要处理的笔记
    
    3. 通过搜索定位并打开：
       python xhs_ingest.py --mode search-open "笔记标题关键词"
    
    4. 截图：
       python xhs_ingest.py --mode screenshot
    
    5. OCR处理：
       python xhs_ingest.py --mode process
    
    6. 关闭弹窗：
       python xhs_ingest.py --mode close

完整流程（自动）：
    python xhs_ingest.py --mode all
""")
        sys.exit(0)
    
    # 解析参数
    mode = None
    search_title = None
    
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == '--mode' and i + 1 < len(sys.argv):
            mode = sys.argv[i + 1]
            i += 2
        elif sys.argv[i].startswith('--'):
            # 其他选项，跳过
            i += 1
        else:
            # 非选项参数，作为搜索标题
            if search_title is None:
                search_title = sys.argv[i]
            i += 1
    
    # 如果没有 --mode，根据参数推断
    if mode is None:
        if search_title:
            mode = 'search'
        else:
            mode = 'auto'
    
    # 执行对应模式
    if mode == 'auto':
        note_id = auto_open_next_note()
        sys.exit(0 if note_id else 1)
    
    elif mode == 'search':
        if not search_title:
            print("错误: 搜索模式需要提供标题")
            print("用法: python xhs_ingest.py --mode search \"笔记标题\"")
            sys.exit(1)
        note_id = search_note_by_title(search_title)
        sys.exit(0 if note_id else 1)
    
    elif mode == 'screenshot':
        count = do_screenshot()
        sys.exit(0 if count > 0 else 1)
    
    elif mode == 'process':
        success = do_process()
        sys.exit(0 if success else 1)
    
    elif mode == 'close':
        success = do_close()
        sys.exit(0 if success else 1)
    
    elif mode == 'collect':
        # 翻页收集所有笔记标题
        log("=" * 60)
        log("收集模式：翻页获取所有笔记标题")
        log("=" * 60)
        
        if not setup_session(headed=True):
            log("[FAIL] 无法设置浏览器会话")
            sys.exit(1)
        
        board_url = f"https://www.xiaohongshu.com/board/{BOARD_ID}"
        notes = collect_all_notes_from_board(board_url)
        
        if not notes:
            log("[WARN] 未收集到任何笔记")
            sys.exit(1)
        
        # 保存到进度文件
        progress = load_progress()
        if not progress:
            progress = {"notes": []}
        
        # 更新或添加笔记信息
        existing_indices = {n.get('index'): n for n in progress.get('notes', [])}
        for note in notes:
            idx = note.get('index', -1)
            if idx < 0:
                continue
            if idx in existing_indices:
                # 更新现有记录
                existing_indices[idx]['title'] = note.get('title', '')
                existing_indices[idx]['author'] = note.get('author', '')
                existing_indices[idx]['note_id'] = note.get('noteId', '')
            else:
                # 添加新记录
                progress['notes'].append({
                    'index': idx,
                    'title': note.get('title', ''),
                    'author': note.get('author', ''),
                    'note_id': note.get('noteId', ''),
                    'status': 'pending',
                    'phases': {}
                })
        
        # 按索引排序
        progress['notes'].sort(key=lambda x: x.get('index', 0))
        save_progress(progress)
        
        log(f"[OK] 已保存 {len(notes)} 个笔记到进度文件")
        
        # 打印前20个笔记供参考
        log("\n笔记列表（前20个）：")
        for note in notes[:20]:
            idx = note.get('index', -1)
            title = note.get('title', '')[:40]
            author = note.get('author', '')[:15]
            log(f"  [{idx}] {title} - @{author}")
        
        if len(notes) > 20:
            log(f"  ... 还有 {len(notes) - 20} 个笔记")
        
        sys.exit(0)
    
    elif mode == 'search-open':
        # 搜索并打开笔记（在同一个浏览器会话中完成）
        if not search_title:
            print("错误: search-open 模式需要提供标题关键词")
            print("用法: python xhs_ingest.py --mode search-open \"笔记标题关键词\"")
            sys.exit(1)
        
        log("=" * 60)
        log(f"搜索并打开: {search_title}")
        log("=" * 60)
        
        # 1. 设置浏览器会话
        if not setup_session(headed=True):
            log("[FAIL] 无法设置浏览器会话")
            sys.exit(1)
        
        # 2. 搜索笔记
        board_url = f"https://www.xiaohongshu.com/board/{BOARD_ID}"
        result = search_note_in_board(search_title, board_url)
        
        if not result.get("found"):
            log("[FAIL] 未找到笔记")
            sys.exit(1)
        
        note_id = result.get("noteId", "")
        note_idx = result.get("index", -1)
        tx, ty = result.get("x", 0), result.get("y", 0)
        
        log(f"点击打开笔记: {note_id}")
        if not real_click(tx, ty):
            log("[FAIL] 点击笔记失败")
            sys.exit(1)
        
        random_sleep(2.0, 0.5)
        
        # 3. 检查弹窗
        if check_popup_opened():
            log("[OK] 笔记弹窗已打开")
        else:
            log("[WARN] 弹窗检测失败，但可能已打开")
        
        # 4. 更新进度
        progress = load_progress()
        if progress and note_idx >= 0:
            mark_note_processing(progress, note_idx, note_id)
        
        save_state()
        sys.exit(0)
    
    elif mode == 'all':
        # 完整流程：在同一个浏览器会话中完成 auto -> screenshot -> close
        log("=" * 60)
        log("完整流程模式：打开 -> 截图 -> 关闭")
        log("=" * 60)
        
        # 1. 设置浏览器会话（只设置一次）
        if not setup_session(headed=True):
            log("[FAIL] 无法设置浏览器会话")
            sys.exit(1)
        
        # 2. 检查进度
        progress = load_progress()
        if not progress:
            log("[WARN] 没有进度记录")
            sys.exit(1)
        
        next_idx = get_next_pending_index(progress)
        if next_idx is None:
            log("[OK] 所有笔记已处理完成！")
            sys.exit(0)
        
        log(f"下一个待处理笔记索引: {next_idx}")
        
        # 3. 确保在收藏夹页面
        current_url = get_current_url()
        if "/board/" not in current_url and "tab=fav" not in current_url:
            log("导航到收藏夹...")
            goto(f"https://www.xiaohongshu.com/board/{BOARD_ID}")
            random_sleep(3.0, 0.5)
        
        # 4. 点击笔记
        note_id = click_note_by_index(next_idx)
        if not note_id:
            log(f"[FAIL] 无法打开笔记 [{next_idx}]")
            mark_note_failed(progress, next_idx, "无法打开笔记")
            sys.exit(1)
        
        mark_note_processing(progress, next_idx, note_id)
        log(f"[OK] 已打开笔记 [{next_idx}]: {note_id}")
        save_state()
        
        # 5. 截图（在同一个会话中）
        log("=" * 60)
        log("截图模式")
        log("=" * 60)
        
        # 检查弹窗
        if not check_popup_opened():
            log("[WARN] 弹窗未检测到，等待...")
            random_sleep(2.0, 0.5)
        
        screenshots_taken = 0
        if check_popup_opened():
            total = screenshot_slides(note_id, str(SCREENSHOT_DIR))
            log(f"[OK] 截图完成: {total} 张")
            screenshots_taken = total
            
            # 更新进度
            for note in progress.get('notes', []):
                if note.get('note_id') == note_id:
                    from xhs_progress import update_phase
                    update_phase(progress, note['index'], 'phase2_screenshot', 'completed',
                               total_slides=total, screenshot_dir=str(SCREENSHOT_DIR))
                    break
        else:
            log("[WARN] 弹窗未打开，跳过截图")
        
        # 6. 关闭弹窗（在同一个会话中）
        log("=" * 60)
        log("关闭弹窗，回到收藏夹")
        log("=" * 60)
        
        close_popup()
        random_sleep(1.0, 0.3)
        
        # 回到收藏夹
        current_url = get_current_url()
        if "/board/" not in current_url and "tab=fav" not in current_url:
            goto(f"https://www.xiaohongshu.com/board/{BOARD_ID}")
            random_sleep(2.0, 0.3)
        
        save_state()
        log("[OK] 已回到收藏夹")
        
        # 7. OCR 处理（不需要浏览器）
        if screenshots_taken > 0:
            log("=" * 60)
            log("OCR 处理模式")
            log("=" * 60)
            
            # 查找当前笔记的信息
            current_note_info = None
            for note in progress.get('notes', []):
                if note.get('index') == next_idx:
                    current_note_info = note
                    break
            
            note_title = current_note_info.get('title', f'笔记_{next_idx}') if current_note_info else f'笔记_{next_idx}'
            note_author = current_note_info.get('author', '未知') if current_note_info else '未知'
            
            result = xhs_process_note(
                note_id=note_id,
                title=note_title,
                author=note_author,
                total_slides=screenshots_taken,
                screenshot_dir=str(SCREENSHOT_DIR),
            )
            
            if result:
                md_file, slug, slides_data = result
                log(f"[OK] Markdown已保存: {md_file}")
                
                # 标记完成
                mark_note_completed(progress, next_idx)
                save_progress(progress)
                log(f"[OK] 笔记 [{next_idx}] 处理完成")
            else:
                log("[FAIL] OCR处理失败")
        
        sys.exit(0)
    
    elif mode == 'status':
        do_status()
        sys.exit(0)
    
    else:
        print(f"错误: 未知模式 '{mode}'")
        print("可用模式: auto, search, search-open, screenshot, process, close, collect, status, all")
        sys.exit(1)


if __name__ == "__main__":
    main()
