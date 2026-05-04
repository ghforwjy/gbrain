"""
小红书导入状态机 v2
完善的状态检测，覆盖所有边界情况
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Tuple, List
import os
import json
import socket
import subprocess
import urllib.request
import time

class State(Enum):
    """所有可能的状态"""
    # Phase 0: 浏览器/CDP相关
    BROWSER_NOT_RUNNING = auto()      # Chrome未启动
    BROWSER_RUNNING_NO_CDP = auto()   # Chrome运行但没有CDP
    CDP_PORT_FIN_WAIT = auto()        # 端口被占用（FIN_WAIT状态）
    CDP_READY_NO_PAGE = auto()        # CDP可用但没有页面
    CDP_READY = auto()                # CDP可用，有页面

    # Phase 1: 小红书页面相关
    XHS_NOT_OPENED = auto()           # 浏览器打开但不在小红书
    XHS_LOGIN_REQUIRED = auto()       # 在小红书登录页面
    XHS_LOGGED_IN_HOME = auto()       # 已登录，在小红书首页
    XHS_LOGGED_IN_OTHER = auto()      # 已登录，在小红书其他页面

    # Phase 2: 收藏夹相关
    BOARD_NOT_OPENED = auto()         # 未打开收藏夹页面
    BOARD_LOADING = auto()            # 收藏夹页面加载中/无笔记
    BOARD_LOADED = auto()             # 收藏夹页面加载完成，有笔记卡片

    # Phase 3: 笔记相关
    NOTE_NOT_SELECTED = auto()        # 未选择笔记
    NOTE_POPUP_OPENED = auto()        # 笔记弹框已打开
    NOTE_POPUP_CLOSED = auto()        # 笔记弹框已关闭

    # Phase 4-6: 后续状态
    SLIDES_NOT_SCREENSHOTTED = auto() # 未截图
    SLIDES_SCREENSHOTTED = auto()     # 已截图
    OCR_NOT_DONE = auto()             # 未OCR
    OCR_DONE = auto()                 # 已OCR
    NOT_IMPORTED = auto()             # 未导入GBrain
    IMPORTED = auto()                 # 已导入


@dataclass
class SystemState:
    """系统当前状态"""
    state: State
    details: dict
    message: str
    next_action: str


def check_browser_running() -> Tuple[bool, List[int]]:
    """检查Chrome是否运行，返回进程ID列表"""
    try:
        result = subprocess.run(
            'tasklist /FI "IMAGENAME eq chrome.exe" /NH /FO CSV',
            shell=True, capture_output=True, text=True
        )
        pids = []
        for line in result.stdout.strip().split('\n'):
            if 'chrome.exe' in line:
                parts = line.split('","')
                if len(parts) >= 2:
                    try:
                        pid = int(parts[1])
                        pids.append(pid)
                    except ValueError:
                        pass
        return len(pids) > 0, pids
    except Exception as e:
        return False, []


def check_port_status(port: int) -> Tuple[bool, bool, str]:
    """
    检查端口状态
    返回: (是否被占用, 是否是FIN_WAIT, 详细信息)
    """
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        output = result.stdout.strip()
        if not output:
            return False, False, "端口空闲"

        # 检查状态
        has_listening = 'LISTENING' in output
        has_established = 'ESTABLISHED' in output
        has_fin_wait = 'FIN_WAIT' in output or 'CLOSE_WAIT' in output

        if has_listening or has_established:
            return True, False, f"端口正常: {output[:100]}"
        elif has_fin_wait:
            return True, True, f"端口FIN_WAIT: {output[:100]}"
        else:
            return True, False, f"端口其他状态: {output[:100]}"
    except Exception as e:
        return False, False, f"检查出错: {e}"


def check_cdp_available(port: int) -> Tuple[bool, str, Optional[str]]:
    """
    检查CDP是否可用
    返回: (是否可用, 消息, WebSocket URL)
    """
    try:
        req = urllib.request.Request(f"http://localhost:{port}/json/version")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            browser = data.get('Browser', 'Unknown')
            ws_url = data.get('webSocketDebuggerUrl', '')
            return True, f"CDP可用: {browser}", ws_url
    except urllib.error.URLError as e:
        if "ConnectionRefusedError" in str(e) or "10061" in str(e):
            return False, "CDP连接被拒绝（Chrome可能未开启CDP）", None
        return False, f"CDP不可用: {e}", None
    except Exception as e:
        return False, f"CDP检查出错: {e}", None


def check_current_page(port: int) -> Tuple[Optional[str], Optional[str], str]:
    """
    检查当前页面URL和标题
    返回: (url, title, 消息)
    """
    try:
        req = urllib.request.Request(f"http://localhost:{port}/json/list")
        with urllib.request.urlopen(req, timeout=3) as resp:
            pages = json.loads(resp.read().decode())
            if pages:
                page = pages[0]
                url = page.get('url', '')
                title = page.get('title', '')
                return url, title, f"找到 {len(pages)} 个页面"
            return None, None, "没有页面"
    except Exception as e:
        return None, None, f"获取页面信息失败: {e}"


def determine_state(cdp_port: int = 9222) -> SystemState:
    """
    确定当前系统状态 - 完善版
    严格按照优先级检测，不漏掉任何状态
    """
    details = {}
    details['cdp_port'] = cdp_port
    details['timestamp'] = time.strftime('%Y-%m-%d %H:%M:%S')

    # ===== Step 1: 检查Chrome是否运行 =====
    browser_running, pids = check_browser_running()
    details['browser_running'] = browser_running
    details['browser_pids'] = pids

    if not browser_running:
        return SystemState(
            state=State.BROWSER_NOT_RUNNING,
            details=details,
            message="Chrome浏览器未启动",
            next_action="启动Chrome并开启CDP"
        )

    # ===== Step 2: 检查端口状态 =====
    port_occupied, is_fin_wait, port_msg = check_port_status(cdp_port)
    details['port_occupied'] = port_occupied
    details['port_fin_wait'] = is_fin_wait
    details['port_msg'] = port_msg

    if is_fin_wait:
        return SystemState(
            state=State.CDP_PORT_FIN_WAIT,
            details=details,
            message=f"端口 {cdp_port} 被占用（FIN_WAIT状态）",
            next_action="等待端口释放或使用其他端口启动Chrome"
        )

    # ===== Step 3: 检查CDP是否可用 =====
    cdp_available, cdp_msg, ws_url = check_cdp_available(cdp_port)
    details['cdp_available'] = cdp_available
    details['cdp_msg'] = cdp_msg
    details['cdp_ws_url'] = ws_url[:50] if ws_url else None

    if not cdp_available:
        # Chrome在运行但CDP不可用
        return SystemState(
            state=State.BROWSER_RUNNING_NO_CDP,
            details=details,
            message="Chrome运行中但CDP不可用（可能启动时未加--remote-debugging-port参数）",
            next_action="关闭Chrome并使用正确的参数重新启动"
        )

    # ===== Step 4: 检查当前页面 =====
    url, title, page_msg = check_current_page(cdp_port)
    details['current_url'] = url
    details['current_title'] = title
    details['page_msg'] = page_msg

    if url is None:
        return SystemState(
            state=State.CDP_READY_NO_PAGE,
            details=details,
            message="CDP可用但没有打开的页面",
            next_action="导航到小红书首页"
        )

    if not url or 'xiaohongshu.com' not in url:
        return SystemState(
            state=State.XHS_NOT_OPENED,
            details=details,
            message=f"浏览器打开但不在小红书 (当前: {url[:60] if url else 'empty'}...)",
            next_action="导航到小红书首页"
        )

    # ===== Step 5: 检查是否需要登录 =====
    if '/login' in url or (title and 'login' in title.lower()):
        return SystemState(
            state=State.XHS_LOGIN_REQUIRED,
            details=details,
            message="在小红书登录页面",
            next_action="等待用户完成登录（扫码或手机号）"
        )

    # ===== Step 6: 检查是否在收藏夹页面 =====
    if '/board/' in url:
        return SystemState(
            state=State.BOARD_LOADING,
            details=details,
            message="在收藏夹页面，需要检查是否加载完成",
            next_action="检查收藏夹页面加载状态（通过JS查询笔记卡片数量）"
        )

    # ===== Step 7: 在小红书其他页面 =====
    if '/explore/' in url:
        # 可能在笔记详情页或弹框
        return SystemState(
            state=State.XHS_LOGGED_IN_OTHER,
            details=details,
            message=f"已登录小红书，当前在笔记页面: {url[:80]}...",
            next_action="检查是否是弹框状态，或导航到收藏夹"
        )

    return SystemState(
        state=State.XHS_LOGGED_IN_HOME,
        details=details,
        message=f"已登录小红书，当前在首页: {url}",
        next_action="导航到收藏夹页面"
    )


def print_state(state: SystemState):
    """打印当前状态"""
    print("\n" + "=" * 60)
    print("当前状态检测")
    print("=" * 60)
    print(f"状态: {state.state.name}")
    print(f"消息: {state.message}")
    print(f"建议操作: {state.next_action}")
    print("-" * 60)
    print("详细信息:")
    for key, value in state.details.items():
        if key == 'browser_pids' and isinstance(value, list):
            print(f"  {key}: {value}")
        elif isinstance(value, str) and len(value) > 100:
            print(f"  {key}: {value[:100]}...")
        else:
            print(f"  {key}: {value}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    port = int(os.environ.get("XHS_CDP_PORT", "9222"))
    state = determine_state(port)
    print_state(state)
