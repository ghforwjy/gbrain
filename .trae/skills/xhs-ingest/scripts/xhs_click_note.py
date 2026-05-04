import time
import os
import sys
import json
import socket
import subprocess
import urllib.request
from playwright.sync_api import sync_playwright

# 导入进度模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_progress import (
    load_progress, init_progress, mark_note_processing,
    mark_note_completed, mark_note_failed, get_next_pending_index,
    get_progress_summary
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CDP_FILE = os.path.join(BASE_DIR, ".gbrain", "xhs_cdp.txt")
DEFAULT_CDP_PORT = 9222


def find_available_port(start_port=9222, max_port=9230):
    """查找可用的CDP端口"""
    for port in range(start_port, max_port + 1):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            if result != 0:
                return port
        except Exception:
            pass
    return None


def check_port_status(port):
    """检查端口状态，返回 (是否被占用, 是否是FIN_WAIT状态)"""
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        output = result.stdout
        if not output:
            return False, False
        
        # 检查是否有FIN_WAIT或CLOSE_WAIT状态
        has_fin_wait = 'FIN_WAIT' in output or 'CLOSE_WAIT' in output
        return True, has_fin_wait
    except Exception:
        return False, False


def run():
    # 临时移除代理，避免连接本地CDP时走代理
    old_proxy = os.environ.pop("HTTP_PROXY", None)
    old_proxy_s = os.environ.pop("HTTPS_PROXY", None)
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"

    browser = None
    cdp_port = DEFAULT_CDP_PORT

    try:
        # 显示当前进度
        print(get_progress_summary())

        # 获取CDP端口（从环境变量或默认）
        cdp_port = int(os.environ.get("XHS_CDP_PORT", DEFAULT_CDP_PORT))
        
        # 检查默认端口状态（仅当使用默认端口时）
        if cdp_port == DEFAULT_CDP_PORT:
            port_occupied, is_fin_wait = check_port_status(DEFAULT_CDP_PORT)
            
            if port_occupied and is_fin_wait:
                print("\n" + "=" * 60)
                print(f"警告: 端口 {DEFAULT_CDP_PORT} 被占用（FIN_WAIT状态）")
                print("=" * 60)
                print("这是Chrome进程被kill后TCP连接未完全释放导致的。")
                print("\n解决方案（选一个）：")
                print("  方案1: 等待2-4分钟，让Windows自动释放端口")
                print("  方案2: 使用其他端口启动Chrome")
                
                # 尝试找可用端口
                available_port = find_available_port(DEFAULT_CDP_PORT + 1)
                if available_port:
                    print(f"\n推荐: 使用端口 {available_port} 启动Chrome:")
                    print(f'  & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" `')
                    print(f'      --remote-debugging-port={available_port} `')
                    print(f'      --user-data-dir="C:\\Users\\wangjunyu\\AppData\\Local\\Google\\Chrome\\User Data" `')
                    print(f'      --profile-directory="Default"')
                    print(f"\n然后设置环境变量再运行脚本:")
                    print(f"  $env:XHS_CDP_PORT=\"{available_port}\"")
                    print(f"  python scripts/xhs-ingest/xhs_click_note.py")
                print("=" * 60)
                return 1
        cdp_endpoint = f"http://localhost:{cdp_port}"

        # 先检查CDP是否可用
        import urllib.request
        try:
            req = urllib.request.Request(f"{cdp_endpoint}/json/version")
            with urllib.request.urlopen(req, timeout=5) as resp:
                cdp_info = json.loads(resp.read().decode())
                cdp_url = cdp_info.get("webSocketDebuggerUrl", "")
                if not cdp_url:
                    print("ERROR: CDP未返回WebSocket URL")
                    return 1
        except Exception as e:
            print(f"ERROR: 无法连接CDP ({cdp_endpoint}): {e}")
            print("\n" + "=" * 60)
            print("浏览器未启动或CDP未开启！")
            print("=" * 60)
            print("\n可能的原因：")
            print("  1. Chrome未启动")
            print("  2. Chrome启动了但没有 --remote-debugging-port 参数")
            print("  3. Chrome被关闭了（登录态丢失）")
            print("  4. 端口被占用（见上方警告）")
            print("\n解决步骤：")
            print("  1. 重新启动Chrome（带CDP）：")
            print(f'     & "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" `')
            print(f'         --remote-debugging-port={cdp_port} `')
            print(f'         --user-data-dir="C:\\Users\\wangjunyu\\AppData\\Local\\Google\\Chrome\\User Data" `')
            print(f'         --profile-directory="Default"')
            print("  2. 登录小红书（如果需要）")
            print("  3. 重新运行此脚本")
            print("\n" + "=" * 60)
            print("当前进度（已保存，不会丢失）：")
            print(get_progress_summary())
            print("=" * 60)
            return 1

        print(f"Connecting to CDP: {cdp_url[:60]}...")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            board_id = "698f3a82000000002502ef57"

            # 获取笔记索引：从环境变量或进度文件
            note_idx_env = os.environ.get("XHS_NOTE_IDX")
            if note_idx_env is not None:
                note_idx = int(note_idx_env)
                print(f"使用环境变量指定的索引: {note_idx}")
            else:
                # 从进度文件获取下一个待处理
                note_idx = get_next_pending_index()
                if note_idx is None:
                    print("所有笔记已处理完成！")
                    return 0
                print(f"从进度文件获取下一个待处理: {note_idx}")

            # 检查进度文件是否需要初始化
            progress = load_progress()
            if not progress:
                print("初始化进度文件...")
                # 先获取总笔记数
                page.goto(
                    f"https://www.xiaohongshu.com/board/{board_id}?source=web_user_page",
                    timeout=30000,
                    wait_until="domcontentloaded"
                )
                time.sleep(3)

                note_cards = page.evaluate("""() => {
                    return document.querySelectorAll('section.note-item').length;
                }""")
                progress = init_progress(board_id, "AI概念学习", note_cards)
                print(f"初始化完成: 共{note_cards}个笔记")

                # 重新获取下一个待处理
                note_idx = get_next_pending_index()
                if note_idx is None:
                    print("所有笔记已处理完成！")
                    return 0

            print(f"Navigating to board {board_id}...")
            page.goto(
                f"https://www.xiaohongshu.com/board/{board_id}?source=web_user_page",
                timeout=30000,
                wait_until="domcontentloaded"
            )
            time.sleep(3)

            # 检查是否需要登录
            if "/login" in page.url:
                print("\n" + "=" * 50)
                print("需要登录小红书")
                print("=" * 50)
                print("请在浏览器中完成登录（扫码或手机号登录）")
                print("登录成功后，在此按 Enter 键继续...")
                print("=" * 50)
                input()  # 等待用户按Enter

                # 再次检查
                page.goto(
                    f"https://www.xiaohongshu.com/board/{board_id}?source=web_user_page",
                    timeout=30000,
                    wait_until="domcontentloaded"
                )
                time.sleep(3)

                if "/login" in page.url:
                    print("ERROR: 仍未登录，请检查登录状态后重试。")
                    return 1

            print("登录确认成功，继续加载笔记...")

            # 获取所有可见的笔记卡片（section.note-item）
            note_cards = page.evaluate("""() => {
                const sections = Array.from(document.querySelectorAll('section.note-item'));
                return sections.map((section, index) => {
                    const rect = section.getBoundingClientRect();
                    const link = section.querySelector('a[href*="/explore/"]');
                    return {
                        index: index,
                        noteId: link ? link.href.match(/\\/explore\\/([a-f0-9]+)/)?.[1] : null,
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2,
                        width: rect.width,
                        height: rect.height,
                        visible: rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < window.innerHeight
                    };
                });
            }""")

            visible_cards = [c for c in note_cards if c['visible']]
            print(f"Found {len(note_cards)} note cards, {len(visible_cards)} visible")

            if note_idx >= len(note_cards):
                print(f"ERROR: note index {note_idx} out of range (total: {len(note_cards)})")
                return 1

            target_card = note_cards[note_idx]
            print(f"\nTarget note [{note_idx}]: {target_card['noteId']}")

            # 如果目标卡片不可见，滚动到它
            if not target_card['visible']:
                print("Target not visible, scrolling...")
                page.evaluate(f"""() => {{
                    const sections = document.querySelectorAll('section.note-item');
                    const target = sections[{note_idx}];
                    if (target) target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
                }}""")
                time.sleep(1)

                # 重新获取位置
                target_card = page.evaluate(f"""() => {{
                    const section = document.querySelectorAll('section.note-item')[{note_idx}];
                    const rect = section.getBoundingClientRect();
                    return {{
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2,
                        width: rect.width,
                        height: rect.height,
                        visible: rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < window.innerHeight
                    }};
                }}""")

            print(f"Position: ({target_card['x']}, {target_card['y']}), Size: {target_card['width']}x{target_card['height']}")

            if not target_card['visible']:
                print("WARNING: Target still not visible after scrolling.")
                print("Please manually scroll and click the note.")
                print("Press Ctrl+C to exit.")
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\nExiting...")
                return 1

            # 点击笔记卡片中心
            print(f"Clicking at ({target_card['x']}, {target_card['y']})...")
            page.mouse.click(target_card["x"], target_card["y"])
            time.sleep(2)

            # 检查是否打开了弹框
            current_url = page.url
            print(f"Current URL after click: {current_url}")

            # 检查是否有弹框出现
            has_popup = page.evaluate("""() => {
                const selectors = [
                    '.note-detail',
                    '.note-popup',
                    '[class*="note-detail"]',
                    '[class*="popup"]',
                    '.interaction-container',
                    '.note-content'
                ];
                for (const sel of selectors) {
                    const el = document.querySelector(sel);
                    if (el && el.offsetParent !== null) {
                        return {found: true, selector: sel};
                    }
                }
                return {found: false};
            }""")

            print(f"Popup check result: {has_popup}")

            if has_popup.get("found"):
                # 标记为处理中
                mark_note_processing(note_idx, target_card.get('noteId'))

                print("\n" + "=" * 50)
                print("POPUP OPENED SUCCESSFULLY")
                print("=" * 50)
                print("The popup is now open. Please check the browser.")
                print("DO NOT close the popup or press Escape.")
                print("DO NOT close the browser window.")
                print("\nNext steps:")
                print("  1. Run 'python scripts/xhs-ingest/screenshot_slides.py' to screenshot each slide")
                print("  2. Run 'python scripts/xhs-ingest/xhs_ingest_v2.py --note {note_idx}' for OCR")
                print("  3. Agent writes vision descriptions")
                print("  4. Import to GBrain")
                print("  5. Press Ctrl+C here to exit this script")
                print("\n⚠️  IMPORTANT: Do NOT close the browser window!")
                print("   If you close it, you'll need to re-login and may trigger风控.")
                print("=" * 50 + "\n")

                # 保持运行，不关闭浏览器
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\nExiting... (browser kept alive)")
            else:
                print("WARNING: Popup may not have opened correctly.")
                mark_note_failed(note_idx, "Popup not opened")
                print("Please check the browser.")
                print("If the popup is open, you can proceed with 'playwright-cli snapshot'")
                print("If not, please manually click the note.")
                print("\nPress Ctrl+C to exit this script.")

                # 保持运行，让用户手动操作
                try:
                    while True:
                        time.sleep(60)
                except KeyboardInterrupt:
                    print("\nExiting... (browser kept alive)")

        return 0

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1

    finally:
        # 恢复代理设置
        if old_proxy:
            os.environ["HTTP_PROXY"] = old_proxy
        if old_proxy_s:
            os.environ["HTTPS_PROXY"] = old_proxy_s
        os.environ.pop("NO_PROXY", None)

        # 注意：不关闭browser！保持浏览器运行！
        # browser.close() 被移除了！


if __name__ == "__main__":
    sys.exit(run())
