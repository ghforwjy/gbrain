"""
小红书收藏导入 - 状态驱动自动化脚本 v2
根据当前状态自动决定下一步操作
"""

import os
import sys
import time
import json
import urllib.request
import subprocess
from playwright.sync_api import sync_playwright

# 导入状态机
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from state_machine import determine_state, print_state, State
from xhs_progress import (
    load_progress, init_progress, mark_note_processing,
    mark_note_completed, mark_note_failed, get_next_pending_index,
    get_progress_summary
)

DEFAULT_CDP_PORT = 9222
BOARD_ID = "698f3a82000000002502ef57"


def get_cdp_port():
    """获取CDP端口"""
    return int(os.environ.get("XHS_CDP_PORT", DEFAULT_CDP_PORT))


def get_cdp_url(port: int) -> str:
    """动态获取CDP WebSocket URL"""
    req = urllib.request.Request(f"http://localhost:{port}/json/version")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        return data.get("webSocketDebuggerUrl", "")


def start_chrome(cdp_port: int):
    """原子操作：启动Chrome并开启CDP"""
    print("\n[原子操作] 启动Chrome并开启CDP...")

    # 检查端口是否被占用
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', cdp_port))
        sock.close()
        if result == 0:
            print(f"端口 {cdp_port} 已被占用，尝试查找可用端口...")
            # 查找可用端口
            for p in range(cdp_port + 1, cdp_port + 10):
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                r = sock.connect_ex(('127.0.0.1', p))
                sock.close()
                if r != 0:
                    cdp_port = p
                    print(f"使用端口: {cdp_port}")
                    break
    except Exception:
        pass

    # 使用新的用户数据目录避免锁定问题
    user_data_dir = os.path.expanduser(r"~\AppData\Local\Google\Chrome\User Data\CDPProfile")
    cmd = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        f"--remote-debugging-port={cdp_port}",
        f"--user-data-dir={user_data_dir}",
        "--no-first-run",
        "--no-default-browser-check"
    ]

    print(f"启动命令: {' '.join(cmd)}")
    subprocess.Popen(cmd)

    # 等待Chrome启动
    print("等待Chrome启动...")
    for i in range(30):
        time.sleep(1)
        try:
            req = urllib.request.Request(f"http://localhost:{cdp_port}/json/version")
            with urllib.request.urlopen(req, timeout=2) as resp:
                data = json.loads(resp.read().decode())
                print(f"✅ Chrome已启动: {data.get('Browser', 'Unknown')}")
                return cdp_port
        except Exception:
            print(f"  等待中... ({i+1}/30)")
            continue

    print("❌ Chrome启动超时")
    return None


def restart_chrome(cdp_port: int):
    """原子操作：关闭并重启Chrome"""
    print("\n[原子操作] 关闭并重启Chrome...")
    subprocess.run('taskkill /F /IM chrome.exe', shell=True, capture_output=True)
    time.sleep(2)
    return start_chrome(cdp_port)


def connect_browser(cdp_port: int):
    """原子操作：连接浏览器"""
    cdp_url = get_cdp_url(cdp_port)
    print(f"连接CDP: {cdp_url[:60]}...")
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    return browser, page


def navigate_to_xhs(page):
    """原子操作：导航到小红书首页"""
    print("\n[原子操作] 导航到小红书首页...")
    page.goto("https://www.xiaohongshu.com", timeout=30000, wait_until="domcontentloaded")
    time.sleep(3)
    print(f"✅ 当前页面: {page.url}")
    return page.url


def navigate_to_board(page):
    """原子操作：导航到收藏夹页面"""
    print(f"\n[原子操作] 导航到收藏夹页面...")
    url = f"https://www.xiaohongshu.com/board/{BOARD_ID}?source=web_user_page"
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    time.sleep(3)
    print(f"✅ 当前页面: {page.url}")
    return page.url


def check_login_status(page) -> bool:
    """原子操作：检查登录状态"""
    print("\n[原子操作] 检查登录状态...")

    # 截图查看当前状态
    screenshot_path = ".playwright-cli/check_login.png"
    page.screenshot(path=screenshot_path, full_page=True)
    print(f"✅ 已截图: {screenshot_path}")

    # 检查URL
    if "/login" in page.url:
        print("❌ 需要登录（URL包含/login）")
        return False

    # 检查页面元素
    has_login_btn = page.evaluate("""() => {
        const loginBtn = document.querySelector('button.login-button, .login-btn, [class*="login"]');
        return !!loginBtn;
    }""")

    if has_login_btn:
        print("❌ 需要登录（页面有登录按钮）")
        return False

    print("✅ 已登录")
    return True


def wait_for_login(page):
    """原子操作：等待用户登录"""
    print("\n" + "=" * 60)
    print("需要登录小红书")
    print("=" * 60)
    print("请在浏览器中完成登录（扫码或手机号）")
    print("登录成功后，在此按 Enter 键继续...")
    print("=" * 60)
    input()

    # 再次检查
    return check_login_status(page)


def check_board_loaded(page) -> tuple:
    """原子操作：检查收藏夹是否加载完成"""
    print("\n[原子操作] 检查收藏夹加载状态...")

    # 检查是否有笔记卡片
    note_cards = page.evaluate("""() => {
        return document.querySelectorAll('section.note-item').length;
    }""")

    print(f"找到 {note_cards} 个笔记卡片")

    if note_cards > 0:
        return True, note_cards
    return False, 0


def click_note(page, note_idx: int, max_retries: int = 3) -> str:
    """原子操作：点击指定索引的笔记，带重试机制"""
    print(f"\n[原子操作] 点击笔记 [{note_idx}]...")

    for attempt in range(max_retries):
        if attempt > 0:
            print(f"\n🔄 第 {attempt + 1}/{max_retries} 次尝试...")
            time.sleep(2)

        # 获取笔记信息
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

        if note_idx >= len(note_cards):
            print(f"❌ 笔记索引 {note_idx} 超出范围 (总数: {len(note_cards)})")
            return None

        target = note_cards[note_idx]
        print(f"目标笔记: {target['noteId']}")

        # 滚动到可见
        if not target['visible']:
            print("滚动到目标笔记...")
            page.evaluate(f"""() => {{
                const sections = document.querySelectorAll('section.note-item');
                const target = sections[{note_idx}];
                if (target) target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
            }}""")
            time.sleep(1)
            # 重新获取位置
            target = page.evaluate(f"""() => {{
                const section = document.querySelectorAll('section.note-item')[{note_idx}];
                const rect = section.getBoundingClientRect();
                return {{
                    x: rect.left + rect.width / 2,
                    y: rect.top + rect.height / 2,
                    visible: rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.top < window.innerHeight
                }};
            }}""")

        # 确保位置有效
        if target['y'] < 0 or target['y'] > 1000:
            print(f"⚠️ 位置异常 ({target['x']}, {target['y']})，重新滚动...")
            page.evaluate(f"""() => {{
                const sections = document.querySelectorAll('section.note-item');
                const target = sections[{note_idx}];
                if (target) target.scrollIntoView({{behavior: 'auto', block: 'center'}});
            }}""")
            time.sleep(1)

        # 点击
        print(f"点击位置: ({target['x']}, {target['y']})")
        page.mouse.click(target['x'], target['y'])
        time.sleep(3)  # 增加等待时间

        # 检查弹框
        has_popup = page.evaluate("""() => {
            const selectors = ['.note-detail', '.note-popup', '[class*="note-detail"]', '[class*="popup"]', '.interaction-container'];
            for (const sel of selectors) {
                const el = document.querySelector(sel);
                if (el && el.offsetParent !== null) return true;
            }
            return false;
        }""")

        if has_popup:
            print("✅ 弹框已打开")
            return target['noteId']
        else:
            print(f"❌ 弹框未打开 (尝试 {attempt + 1}/{max_retries})")

    print(f"❌ 点击笔记 [{note_idx}] 失败，已重试 {max_retries} 次")
    return None


def run_state_machine():
    """主状态机循环"""
    print("\n" + "=" * 60)
    print("小红书收藏导入 - 状态驱动自动化")
    print("=" * 60)

    # 显示进度
    print(get_progress_summary())

    cdp_port = get_cdp_port()
    browser = None
    page = None

    try:
        # 移除代理
        os.environ.pop("HTTP_PROXY", None)
        os.environ.pop("HTTPS_PROXY", None)
        os.environ["NO_PROXY"] = "localhost,127.0.0.1"

        while True:
            # 检测当前状态
            state = determine_state(cdp_port)
            print_state(state)

            # ===== Phase 0: 浏览器/CDP状态 =====
            if state.state == State.BROWSER_NOT_RUNNING:
                new_port = start_chrome(cdp_port)
                if new_port:
                    cdp_port = new_port
                    os.environ["XHS_CDP_PORT"] = str(cdp_port)
                else:
                    print("❌ 无法启动Chrome，退出")
                    return 1

            elif state.state == State.BROWSER_RUNNING_NO_CDP:
                print("Chrome运行中但CDP不可用，需要重启...")
                new_port = restart_chrome(cdp_port)
                if new_port:
                    cdp_port = new_port
                    os.environ["XHS_CDP_PORT"] = str(cdp_port)
                else:
                    print("❌ 无法重启Chrome，退出")
                    return 1

            elif state.state == State.CDP_PORT_FIN_WAIT:
                print(f"端口 {cdp_port} FIN_WAIT，尝试使用新端口...")
                new_port = cdp_port + 1
                os.environ["XHS_CDP_PORT"] = str(new_port)
                cdp_port = new_port
                # 重新检测状态
                continue

            elif state.state == State.CDP_READY_NO_PAGE:
                if not page:
                    browser, page = connect_browser(cdp_port)
                navigate_to_xhs(page)

            # ===== Phase 1: 小红书页面状态 =====
            elif state.state == State.XHS_NOT_OPENED:
                if not page:
                    browser, page = connect_browser(cdp_port)
                navigate_to_xhs(page)

            elif state.state == State.XHS_LOGIN_REQUIRED:
                if not page:
                    browser, page = connect_browser(cdp_port)
                success = wait_for_login(page)
                if not success:
                    print("❌ 登录失败，请重试")
                    return 1

            elif state.state == State.XHS_LOGGED_IN_HOME:
                if not page:
                    browser, page = connect_browser(cdp_port)
                navigate_to_board(page)

            elif state.state == State.XHS_LOGGED_IN_OTHER:
                # 在笔记页面或其他页面，导航到收藏夹
                if not page:
                    browser, page = connect_browser(cdp_port)
                print("当前在笔记页面，导航到收藏夹...")
                navigate_to_board(page)

            # ===== Phase 2: 收藏夹状态 =====
            elif state.state == State.BOARD_NOT_OPENED:
                if not page:
                    browser, page = connect_browser(cdp_port)
                navigate_to_board(page)

            elif state.state == State.BOARD_LOADING:
                if not page:
                    browser, page = connect_browser(cdp_port)

                loaded, count = check_board_loaded(page)
                if loaded:
                    print(f"✅ 收藏夹加载完成，共 {count} 个笔记")
                    # 初始化进度
                    progress = load_progress()
                    if not progress:
                        init_progress(BOARD_ID, "AI概念学习", count)

                    # 获取下一个待处理笔记
                    note_idx = get_next_pending_index()
                    if note_idx is None:
                        print("🎉 所有笔记已处理完成！")
                        return 0

                    print(f"下一个待处理笔记: [{note_idx}]")
                    # 点击笔记（带重试）
                    note_id = click_note(page, note_idx, max_retries=3)
                    if note_id:
                        progress = load_progress()
                        mark_note_processing(progress, note_idx, note_id)
                        print("\n" + "=" * 60)
                        print("笔记弹框已打开！")
                        print("=" * 60)
                        print("接下来请运行: python scripts/xhs-ingest/screenshot_slides.py")
                        print("=" * 60)
                        return 0  # 成功打开笔记，退出等待截图
                    else:
                        print(f"\n❌ 笔记 [{note_idx}] 打开失败，将在最后重试")
                        progress = load_progress()
                        mark_note_failed(progress, note_idx, "无法打开弹框（将在最后重试）")
                else:
                    print("❌ 收藏夹未加载，可能需要登录")
                    # 检查登录状态
                    if not check_login_status(page):
                        wait_for_login(page)

            elif state.state == State.BOARD_LOADED:
                # 已经加载完成，直接点击笔记
                if not page:
                    browser, page = connect_browser(cdp_port)

                note_idx = get_next_pending_index()
                if note_idx is None:
                    print("🎉 所有笔记已处理完成！")
                    return 0

                note_id = click_note(page, note_idx)
                if note_id:
                    progress = load_progress()
                    mark_note_processing(progress, note_idx, note_id)
                    print("\n" + "=" * 60)
                    print("笔记弹框已打开！")
                    print("=" * 60)
                    print("接下来请运行: python scripts/xhs-ingest/screenshot_slides.py")
                    print("=" * 60)
                    return 0

            else:
                print(f"未处理的状态: {state.state.name}")
                print("等待2秒后重新检测...")
                time.sleep(2)

            time.sleep(2)

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        # 不关闭浏览器！
        pass

    return 0


if __name__ == "__main__":
    sys.exit(run_state_machine())
