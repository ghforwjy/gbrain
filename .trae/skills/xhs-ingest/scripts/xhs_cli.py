"""
Playwright-CLI 封装模块
所有浏览器操作通过 playwright-cli 命令行执行

设计约束:
- 所有输出必须使用 flush=True
- 禁止使用 Unicode 特殊字符
- 所有坐标操作必须验证在视口内
- 路径必须使用相对路径或环境变量，禁止写死绝对路径
"""

import subprocess
import json
import os
import time
import random
import re
import sys
import io
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


# ============ 路径配置（使用环境变量或相对路径） ============

def get_project_root() -> Path:
    """获取项目根目录
    
    策略:
    1. 检查 GBRAIN_HOME 环境变量
    2. 从当前文件位置推算（scripts/xhs_cli.py -> 项目根目录）
    3. 使用当前工作目录
    """
    # 1. 环境变量
    env_root = os.environ.get('GBRAIN_HOME')
    if env_root:
        return Path(env_root)
    
    # 2. 从当前文件位置推算
    # 当前文件在: <project_root>/.trae/skills/xhs-ingest/scripts/xhs_cli.py
    try:
        current_file = Path(__file__).resolve()
        # 向上回溯4级: scripts -> xhs-ingest -> skills -> .trae -> project_root
        project_root = current_file.parent.parent.parent.parent.parent
        if (project_root / '.gbrain').exists() or (project_root / 'brain').exists():
            return project_root
    except:
        pass
    
    # 3. 当前工作目录
    return Path.cwd()


# 项目根目录
PROJECT_ROOT = get_project_root()

# 认证文件路径（项目根目录下）
AUTH_FILE = PROJECT_ROOT / "xhs_auth.json"

# 截图输出目录（项目根目录下的 .playwright-cli）
SCREENSHOT_DIR = PROJECT_ROOT / ".playwright-cli"
SCREENSHOT_DIR.mkdir(exist_ok=True)

# 进度文件路径
PROGRESS_FILE = PROJECT_ROOT / ".gbrain" / "xhs_progress.json"


def log(msg: str, indent: int = 0):
    """统一日志输出，确保实时显示"""
    prefix = "  " * indent
    print(f"{prefix}{msg}", flush=True)


def random_sleep(base: float, variance: float = 0.5):
    """随机时间间隔，模拟人工操作
    
    改进:
    - 基础延迟更长 (0.3-8秒随机分布)
    - 添加随机抖动
    - 偶尔休息更长时间
    """
    # 偶尔休息更长时间（5%概率休息3-10秒）
    if random.random() < 0.05:
        sleep_time = random.uniform(3.0, 10.0)
    else:
        # 正常延迟：0.5-基础时间*2 之间随机
        min_sleep = max(0.5, base * 0.5)
        max_sleep = max(base + variance * 3, base * 2.5)
        sleep_time = random.uniform(min_sleep, max_sleep)
    
    # 添加随机抖动 (±10%)
    jitter = sleep_time * random.uniform(-0.1, 0.1)
    sleep_time += jitter
    
    time.sleep(sleep_time)


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


# ============ Playwright-CLI 路径检测 ============

def find_playwright_cli() -> str:
    """查找 playwright-cli 可执行文件

    搜索顺序:
    1. 环境变量 PATH 中的 playwright-cli
    2. 使用 'where' 命令查找
    3. 常见全局安装路径 (npm/bun/pnpm)
    4. 返回命令名让系统自己找

    返回: 可执行文件路径或 "playwright-cli"
    """
    # 1. 尝试直接运行（PATH 中）
    try:
        result = subprocess.run(
            "playwright-cli --version",
            shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return "playwright-cli"
    except:
        pass

    # 2. 使用 where 命令查找
    try:
        result = subprocess.run(
            "where playwright-cli",
            shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0 and result.stdout.strip():
            paths = [p.strip() for p in result.stdout.strip().split('\n') if p.strip()]
            if paths:
                return paths[0]
    except:
        pass

    # 3. 检查常见全局安装路径
    common_paths = []

    # npm 全局路径
    try:
        result = subprocess.run(
            "npm config get prefix", shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            npm_prefix = result.stdout.strip().strip()
            if npm_prefix:
                common_paths.append(Path(npm_prefix) / "playwright-cli")
                common_paths.append(Path(npm_prefix) / "node_modules" / ".bin" / "playwright-cli")
    except:
        pass

    # bun 全局路径
    bun_global = Path(os.environ.get("USERPROFILE", "")) / ".bun" / "install" / "global"
    common_paths.append(bun_global / "node_modules" / ".bin" / "playwright-cli")
    common_paths.append(bun_global / "node_modules" / "@anthropic-ai" / "playwright-cli" / "bin" / "playwright-cli")

    # pnpm 全局路径
    pnpm_global = Path(os.environ.get("LOCALAPPDATA", "")) / "pnpm"
    common_paths.append(pnpm_global / "playwright-cli")

    for p in common_paths:
        if p.exists():
            return str(p)
        # 也检查 .cmd 版本 (Windows)
        p_cmd = Path(str(p) + ".cmd")
        if p_cmd.exists():
            return str(p_cmd)

    # 4. 默认返回命令名
    return "playwright-cli"


# 全局缓存 playwright-cli 路径
_PLAYWRIGHT_CLI_PATH = None

def get_playwright_cli() -> str:
    """获取 playwright-cli 路径（带缓存）"""
    global _PLAYWRIGHT_CLI_PATH
    if _PLAYWRIGHT_CLI_PATH is None:
        _PLAYWRIGHT_CLI_PATH = find_playwright_cli()
        log(f"[INFO] playwright-cli: {_PLAYWRIGHT_CLI_PATH}")
    return _PLAYWRIGHT_CLI_PATH


def run_cli(cmd: str, timeout: int = 30) -> dict:
    """执行 playwright-cli 命令，返回解析后的结果"""
    cli_path = get_playwright_cli()
    full_cmd = f'"{cli_path}" {cmd}'
    try:
        result = subprocess.run(
            full_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace"
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "success": result.returncode == 0
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "timeout", "returncode": -1, "success": False}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1, "success": False}


def check_cli_installed() -> bool:
    """检查 playwright-cli 是否已安装"""
    result = run_cli("--help", timeout=5)
    return result["success"] and "playwright-cli" in result["stdout"]


def open_browser(url: str = "", headed: bool = True, persistent: bool = True) -> bool:
    """打开浏览器并导航到指定URL
    
    Args:
        url: 导航URL
        headed: 是否使用有头模式
        persistent: 是否使用持久化会话（保持浏览器打开）
    """
    cmd = f"open {url}"
    if not headed:
        cmd += " --headless"
    if persistent:
        cmd += " --persistent"
    result = run_cli(cmd, timeout=30)
    if result["success"]:
        log(f"[OK] 浏览器已打开: {url or 'about:blank'}")
        return True
    else:
        log(f"[FAIL] 打开浏览器失败: {result['stderr'][:100]}")
        return False


def attach_browser() -> bool:
    """附加到已打开的浏览器
    
    先检查是否有已打开的浏览器会话
    """
    # 先列出所有会话
    result = run_cli("list", timeout=5)
    if result["success"] and result.get("stdout", "").strip():
        stdout = result.get("stdout", "")
        # 解析会话名称
        session_name = None
        for line in stdout.split('\n'):
            line = line.strip()
            if line.startswith('- ') and line.endswith(':'):
                session_name = line[2:-1].strip()
                break
        
        if session_name:
            # 尝试附加到指定会话
            result = run_cli(f'attach "{session_name}"', timeout=10)
            if result["success"]:
                log(f"[OK] 已附加到浏览器会话: {session_name}")
                return True
            else:
                log(f"[WARN] 附加到会话失败: {result.get('stderr', '')[:100]}")
    
    log("[WARN] 没有可附加的浏览器会话")
    return False


def close_browser() -> bool:
    """关闭浏览器"""
    result = run_cli("close", timeout=10)
    return result["success"]


def goto(url: str) -> bool:
    """导航到指定URL"""
    log(f"导航到: {url}")
    result = run_cli(f'goto "{url}"', timeout=30)
    if result["success"]:
        log("[OK] 导航成功")
        return True
    else:
        log(f"[FAIL] 导航失败: {result['stderr'][:100]}")
        return False


def get_current_url() -> str:
    """获取当前页面URL"""
    result = run_cli("eval document.location.href", timeout=10)
    if result["success"]:
        url = result["stdout"].strip().strip('"')
        return url
    return ""


def eval_js_raw(code: str) -> str:
    """执行原始JavaScript代码并返回结果
    
    使用 base64 编码避免 PowerShell 引号转义问题
    """
    import base64
    encoded = base64.b64encode(code.encode('utf-8')).decode('utf-8')
    wrapper = f"eval(atob('{encoded}'))"
    result = run_cli(f'--raw eval "{wrapper}"', timeout=15)
    if isinstance(result, dict) and result.get("success"):
        stdout = result.get("stdout", "").strip()
        if stdout.startswith('"') and stdout.endswith('"'):
            try:
                stdout = json.loads(stdout)
            except:
                pass
        return stdout
    elif isinstance(result, str):
        return result.strip()
    else:
        return ""


def resize(w: int, h: int) -> bool:
    """调整窗口大小"""
    result = run_cli(f"resize {w} {h}", timeout=10)
    return result["success"]


def mousemove(x: int, y: int) -> bool:
    """移动鼠标到指定位置，模拟人类鼠标轨迹
    
    改进:
    - 不直线移动，添加贝塞尔曲线轨迹
    - 移动速度随机
    - 中途可能有犹豫/停顿
    """
    # 获取当前鼠标位置（如果可以）
    current_pos = None
    try:
        # 尝试从 eval_js 获取当前位置
        result = run_cli("eval document.body.scrollWidth", timeout=2)
    except:
        pass
    
    # 计算移动距离
    # 移动速度分段：开始慢，后面快
    # 使用贝塞尔曲线模拟人类移动
    def bezier_point(t, p0, p1, p2, p3):
        """三次贝塞尔曲线"""
        return (1-t)**3 * p0 + 3*(1-t)**2 * t * p1 + 3*(1-t) * t**2 * p2 + t**3 * p3
    
    # 起始点在目标点附近随机偏移（模拟从某处开始）
    start_x = x + random.randint(-100, 100)
    start_y = y + random.randint(-100, 100)
    
    # 控制点（添加随机偏移形成曲线）
    cp1_x = x + random.randint(-200, 200)
    cp1_y = start_y + random.randint(-150, 150)
    cp2_x = x + random.randint(-150, 150)
    cp2_y = y + random.randint(-100, 100)
    
    # 分10步移动，每步之间有随机延迟
    steps = 10
    for i in range(steps):
        t = i / steps
        # 添加一点随机扰动
        target_x = bezier_point(t, start_x, cp1_x, cp2_x, x)
        target_y = bezier_point(t, start_y, cp1_y, cp2_y, y)
        
        # 添加随机抖动
        jitter_x = random.randint(-5, 5)
        jitter_y = random.randint(-5, 5)
        
        target_x = int(target_x + jitter_x)
        target_y = int(target_y + jitter_y)
        
        result = run_cli(f"mousemove {target_x} {target_y}", timeout=5)
        if not result["success"]:
            # 如果精确移动失败，直接移动到目标
            result = run_cli(f"mousemove {x} {y}", timeout=5)
            break
        
        # 每步之间随机延迟（模拟人类移动速度变化）
        if i < steps - 1:
            delay = random.uniform(0.02, 0.08)  # 20-80ms
            time.sleep(delay)
    
    log(f"[OK] 鼠标移动到 ({x}, {y})")
    return True


def mousedown() -> bool:
    """鼠标按下"""
    result = run_cli("mousedown", timeout=5)
    if result["success"]:
        log("[OK] 鼠标按下")
        return True
    else:
        log("[FAIL] 鼠标按下失败")
        return False


def mouseup() -> bool:
    """鼠标释放"""
    result = run_cli("mouseup", timeout=5)
    if result["success"]:
        log("[OK] 鼠标释放")
        return True
    else:
        log("[FAIL] 鼠标释放失败")
        return False


def real_click(x: int, y: int) -> bool:
    """执行真实鼠标点击 (mousemove + mousedown + mouseup)
    
    设计约束:
    1. 坐标必须在视口内
    2. 执行顺序: mousemove -> sleep(随机) -> mousedown -> sleep(随机) -> mouseup -> sleep(随机)
    
    改进:
    - 延迟完全随机化（人类点击间隔不规律）
    - 添加鼠标悬停（hover）模拟
    """
    log(f"执行真实点击: ({x}, {y})")
    
    if not mousemove(x, y):
        return False
    
    # 移动到目标后，人类通常会有犹豫
    # 犹豫时间：0.3-2秒随机
    hover_delay = random.uniform(0.3, 2.0)
    time.sleep(hover_delay)
    
    # 按下鼠标
    if not mousedown():
        return False
    
    # 按下和释放之间：0.1-0.5秒随机（人类不会瞬间松开）
    press_delay = random.uniform(0.1, 0.5)
    time.sleep(press_delay)
    
    if not mouseup():
        return False
    
    # 点击后通常会看一下结果：1-4秒随机
    after_click_delay = random.uniform(1.0, 4.0)
    time.sleep(after_click_delay)
    
    log("[OK] 点击完成")
    return True


def check_login_status_xhs() -> bool:
    """检查小红书登录状态
    
    简化检查：只要不在登录页且能访问小红书，就认为已登录
    """
    url = get_current_url()
    if "/login" in url:
        return False
    
    # 如果能访问小红书页面，就认为已登录
    return "xiaohongshu.com" in url


def save_state() -> bool:
    """保存浏览器状态（登录态）"""
    result = run_cli(f'state-save "{AUTH_FILE}"', timeout=10)
    if result["success"]:
        log(f"[OK] 状态已保存: {AUTH_FILE}")
        return True
    else:
        log("[FAIL] 状态保存失败")
        return False


def load_state() -> bool:
    """加载浏览器状态（登录态）"""
    if not AUTH_FILE.exists():
        log("[WARN] 状态文件不存在")
        return False
    
    result = run_cli(f'state-load "{AUTH_FILE}"', timeout=10)
    if result["success"]:
        log("[OK] 状态已加载")
        return True
    else:
        log("[FAIL] 状态加载失败")
        return False


def setup_session(headed: bool = True, navigate_home: bool = True) -> bool:
    """设置浏览器会话
    
    流程:
    1. 检查 playwright-cli 是否安装
    2. 尝试附加到已有浏览器
    3. 如果失败，打开新浏览器
    4. 加载登录状态
    5. 验证登录状态
    
    Args:
        headed: 是否使用有头模式
        navigate_home: 是否导航到小红书首页验证（默认True）
                      设置为False时，附加成功后保持当前页面
    """
    log("=" * 60)
    log("设置浏览器会话")
    log("=" * 60)
    
    # 1. 检查 playwright-cli
    if not check_cli_installed():
        log("[FAIL] playwright-cli 未安装")
        log("[INFO] 请确保 playwright-cli 已安装并在 PATH 中")
        return False
    log("[OK] playwright-cli 已安装")
    
    # 2. 尝试附加到已有浏览器
    attached = attach_browser()
    if attached:
        log("[OK] 已附加到现有浏览器")
        # 如果成功附加且不需要导航首页，直接验证当前页面
        if not navigate_home:
            log("检查当前页面登录状态...")
            if check_login_status_xhs():
                log("[OK] 登录状态有效")
                return True
    else:
        log("打开新浏览器...")
        if not open_browser(headed=headed):
            return False
    
    # 3. 加载登录状态
    if AUTH_FILE.exists():
        log("加载已保存的登录状态...")
        load_state()
        if navigate_home or not attached:
            log("导航到小红书验证登录态...")
            goto("https://www.xiaohongshu.com")
            time.sleep(3)
    
    # 4. 验证登录状态
    log("检查登录状态...")
    if check_login_status_xhs():
        log("[OK] 登录状态有效")
        return True
    else:
        log("[WARN] 登录状态失效，需要重新登录")
        return False


def get_note_cards_count() -> int:
    """获取收藏夹中笔记卡片数量"""
    result = eval_js_raw("""
        (() => {
            const container = document.querySelector('.feeds-container');
            if (container) {
                return container.querySelectorAll('section.note-item').length;
            }
            return document.querySelectorAll('section.note-item').length;
        })()
    """)
    try:
        return int(result)
    except (ValueError, TypeError):
        return 0


def collect_all_notes_from_board(board_url: str) -> list:
    """翻页收集收藏夹中所有笔记的标题和索引
    
    流程:
    1. 导航到收藏夹页面
    2. 不断向下滚动，收集所有可见笔记的标题和索引
    3. 直到没有新笔记出现
    
    返回: [{index, title, noteId, author}, ...]
    """
    log("=" * 60)
    log("收集收藏夹所有笔记")
    log("=" * 60)
    
    # 导航到收藏夹
    current_url = get_current_url()
    if board_url not in current_url:
        log(f"导航到收藏夹: {board_url}")
        goto(board_url)
        random_sleep(3.0, 0.5)
    
    all_notes = []
    seen_indices = set()
    scroll_attempts = 0
    max_scroll_attempts = 200  # 防止无限滚动
    last_count = 0
    no_new_count = 0
    
    log("开始翻页收集笔记...")
    
    while scroll_attempts < max_scroll_attempts:
        # 获取当前可见的笔记
        result = eval_js_raw("""
            (() => {
                const sections = Array.from(document.querySelectorAll('.feeds-container section.note-item'));
                const notes = [];
                for (const section of sections) {
                    const idx = parseInt(section.getAttribute('data-index') || '-1');
                    if (idx < 0) continue;
                    
                    // 获取标题
                    let title = '';
                    const titleEl = section.querySelector('.title, .note-title, h3, h4, [class*="title"]');
                    if (titleEl) title = titleEl.textContent.trim();
                    
                    // 获取作者
                    let author = '';
                    const authorEl = section.querySelector('.author, .user-name, [class*="author"], [class*="user"]');
                    if (authorEl) author = authorEl.textContent.trim();
                    
                    // 获取noteId
                    let noteId = '';
                    const link = section.querySelector('a[href*="/explore/"]');
                    if (link) {
                        const match = link.href.match(/explore\/([a-f0-9]+)/);
                        if (match) noteId = match[1];
                    }
                    
                    // 获取封面图
                    let coverUrl = '';
                    const img = section.querySelector('img');
                    if (img) coverUrl = img.src || '';
                    
                    notes.push({
                        index: idx,
                        title: title,
                        author: author,
                        noteId: noteId,
                        coverUrl: coverUrl
                    });
                }
                return JSON.stringify(notes);
            })()
        """)
        
        try:
            current_notes = json.loads(result) if result else []
        except:
            current_notes = []
        
        # 添加新笔记
        new_found = 0
        for note in current_notes:
            idx = note.get('index', -1)
            if idx >= 0 and idx not in seen_indices:
                seen_indices.add(idx)
                all_notes.append(note)
                new_found += 1
        
        if new_found > 0:
            log(f"本次发现 {new_found} 个新笔记，累计: {len(all_notes)}", indent=1)
            no_new_count = 0
        else:
            no_new_count += 1
            if no_new_count >= 3:
                log("连续3次没有新笔记，收集完成", indent=1)
                break
        
        # 向下滚动
        scroll_by(800)
        random_sleep(1.5, 0.3)
        scroll_attempts += 1
        
        # 每10次滚动报告一次
        if scroll_attempts % 10 == 0:
            log(f"已滚动 {scroll_attempts} 次，收集 {len(all_notes)} 个笔记", indent=1)
    
    log(f"[OK] 收集完成，共 {len(all_notes)} 个笔记")
    return all_notes


def search_note_in_board(title_keyword: str, board_url: str) -> dict:
    """通过搜索框在收藏夹中定位笔记
    
    流程:
    1. 确保在收藏夹页面
    2. 点击搜索框
    3. 输入标题关键词
    4. 提交搜索
    5. 在搜索结果中找到匹配的笔记
    
    返回: {found, noteId, index, x, y} 或 {found: False}
    """
    log("=" * 60)
    log(f"搜索笔记: {title_keyword}")
    log("=" * 60)
    
    # 确保在收藏夹页面
    current_url = get_current_url()
    if board_url not in current_url:
        log(f"导航到收藏夹: {board_url}")
        goto(board_url)
        random_sleep(3.0, 0.5)
    
    # 查找并点击搜索框
    log("点击搜索框...")
    pos = find_search_input()
    if not pos.get("found"):
        log("[FAIL] 未找到搜索输入框")
        return {"found": False}
    
    x, y = pos.get("x", 0), pos.get("y", 0)
    log(f"搜索框位置: ({x}, {y})", indent=1)
    
    if not real_click(x, y):
        log("[FAIL] 点击搜索框失败")
        return {"found": False}
    random_sleep(0.8, 0.3)
    
    # 清空并输入关键词
    log("输入搜索关键词...")
    eval_js_raw("""
        (() => {
            const input = document.querySelector('input[placeholder*="搜索"], input[placeholder*="搜"], .search-input input, .search-bar input, input[type="search"]');
            if (input) { input.select(); input.value = ''; input.dispatchEvent(new Event('input', {bubbles: true})); return 'cleared'; }
            return 'not_found';
        })()
    """)
    random_sleep(0.5, 0.2)
    
    # 使用真实按键输入（模拟人类逐字输入）
    log("使用真实按键输入...")
    
    def type_text(text: str):
        """逐字输入，模拟人类打字行为"""
        for char in text:
            if char == ' ':
                run_cli("press Space", timeout=2)
            elif char == '\n':
                run_cli("press Enter", timeout=2)
            else:
                # 使用 playwright-cli 的 type 命令
                # 如果不支持单个字符，使用 press Key
                result = run_cli(f'type "{char}"', timeout=2)
                if not result.get("success"):
                    # 回退：使用 keyboard 命令
                    run_cli(f'keyboard "{char}"', timeout=2)
            # 打字速度随机：50-200ms 每字
            time.sleep(random.uniform(0.05, 0.2))
            # 偶尔打错然后删除（1%概率）- 模拟人类打字习惯
            if random.random() < 0.01:
                # 打错一个字符
                wrong_char = chr(random.randint(ord('a'), ord('z')))
                run_cli(f'type "{wrong_char}"', timeout=2)
                time.sleep(random.uniform(0.05, 0.1))
                # 删除
                run_cli("press Backspace", timeout=2)
                time.sleep(random.uniform(0.05, 0.15))
    
    # 先点击输入框确保聚焦
    if not real_click(x, y):
        log("[FAIL] 点击输入框失败")
        return {"found": False}
    random_sleep(0.3, 0.1)
    
    # 清空输入框（如果有内容）
    eval_js_raw("""
        (() => {
            const input = document.querySelector('input[placeholder*="搜索"], input[placeholder*="搜"], .search-input input, .search-bar input, input[type="search"]');
            if (input) { 
                input.value = ''; 
                input.dispatchEvent(new Event('input', {bubbles: true})); 
                return 'cleared'; 
            }
            return 'not_found';
        })()
    """)
    random_sleep(0.2, 0.1)
    
    # 逐字输入关键词
    type_text(title_keyword)
    random_sleep(0.3, 0.1)
    
    # 按 Enter 提交搜索
    log("提交搜索...")
    run_cli("press Enter", timeout=10)
    random_sleep(2.5, 0.5)
    
    # 获取搜索结果
    log("获取搜索结果...")
    search_result = eval_js_raw("""
        (() => {
            const cards = document.querySelectorAll('.feeds-container section.note-item, section.note-item');
            for (const card of cards) {
                const rect = card.getBoundingClientRect();
                if (rect.top < 100 || rect.top >= window.innerHeight) continue;
                
                const link = card.querySelector('a[href*="/explore/"]');
                if (!link) continue;
                
                const href = link.href || '';
                const match = href.match(/explore\/([a-f0-9]+)/);
                const noteId = match ? match[1] : '';
                
                if (!noteId) continue;
                
                // 获取标题
                let title = '';
                const titleEl = card.querySelector('.title, .note-title, h3, h4, [class*="title"]');
                if (titleEl) title = titleEl.textContent.trim();
                
                // 获取索引
                const idx = parseInt(card.getAttribute('data-index') || '-1');
                
                return JSON.stringify({
                    found: true,
                    noteId: noteId,
                    index: idx,
                    title: title,
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top + rect.height / 2)
                });
            }
            return JSON.stringify({found: false});
        })()
    """)
    
    try:
        target = json.loads(search_result) if search_result else {"found": False}
    except:
        target = {"found": False}
    
    if target.get("found"):
        log(f"[OK] 找到笔记: {target.get('noteId')}, 标题: {target.get('title', '')[:30]}", indent=1)
    else:
        log("[FAIL] 未找到搜索结果")
    
    return target


def get_visible_range() -> tuple:
    """获取当前可见笔记的索引范围
    
    返回: (min_index, max_index, count)
    """
    result = eval_js_raw("""
        (() => {
            const sections = Array.from(document.querySelectorAll('.feeds-container section.note-item'));
            if (sections.length === 0) return JSON.stringify({minIndex: 0, maxIndex: 0, count: 0});
            const visibleIndices = sections.map(s => parseInt(s.getAttribute('data-index') || -1));
            return JSON.stringify({
                minIndex: Math.min(...visibleIndices),
                maxIndex: Math.max(...visibleIndices),
                count: sections.length
            });
        })()
    """)
    try:
        data = json.loads(result)
        return (data.get('minIndex', 0), data.get('maxIndex', 0), data.get('count', 0))
    except:
        return (0, 0, 0)


def scroll_by(delta_y: int) -> bool:
    """滚动指定距离，模拟人类滚动行为
    
    改进:
    - 使用可变滚动距离（不是固定值）
    - 添加滚动减速过程
    - 偶尔"滚动过头"然后回滚一点
    """
    # 获取视口高度，用于计算相对滚动
    viewport_result = eval_js_raw("""
        (() => { return window.innerHeight; })()
    """)
    try:
        viewport_height = int(viewport_result)
    except:
        viewport_height = 800
    
    # 人类滚动特点：
    # 1. 每次滚动距离不固定（0.3-1.5个视口高度）
    # 2. 滚动速度不恒定
    # 3. 偶尔滚动过头然后微调
    
    # 计算滚动距离：视口的0.3-0.8倍
    scroll_ratio = random.uniform(0.3, 0.8)
    actual_scroll = int(viewport_height * scroll_ratio)
    
    # 偶尔滚动过头然后回滚（10%概率）
    overscroll = False
    if random.random() < 0.1:
        overscroll = True
        # 滚动过头量：多滚10-30%
        overscroll_amount = int(actual_scroll * random.uniform(0.1, 0.3))
        actual_scroll += overscroll_amount
    
    # 方向
    if delta_y < 0:
        actual_scroll = -actual_scroll
    
    # 执行滚动（分多次模拟减速）
    # 初始快一点
    fast_scroll = int(actual_scroll * random.uniform(0.6, 0.8))
    slow_scroll = actual_scroll - fast_scroll
    
    # 第一次滚动（快）
    eval_js_raw(f"(() => {{ window.scrollBy(0, {fast_scroll}); return 'ok'; }})()")
    time.sleep(random.uniform(0.05, 0.15))  # 短暂停顿
    
    # 第二次滚动（慢，模拟减速）
    eval_js_raw(f"(() => {{ window.scrollBy(0, {slow_scroll}); return 'ok'; }})()")
    
    # 如果滚动过头，微调回来
    if overscroll:
        time.sleep(random.uniform(0.2, 0.5))  # 犹豫一下
        correction = -int(overscroll_amount * random.uniform(0.5, 0.8))
        eval_js_raw(f"(() => {{ window.scrollBy(0, {correction}); return 'ok'; }})()")
    
    return True


def scroll_note_to_center(note_idx: int) -> bool:
    """将指定笔记滚动到视口中央"""
    result = eval_js_raw(f"""
        (() => {{
            const target = document.querySelector('.feeds-container section.note-item[data-index="{note_idx}"]');
            if (target) {{
                target.scrollIntoView({{behavior: 'instant', block: 'center'}});
                return 'ok';
            }}
            return 'not_found';
        }})()
    """)
    return result == "ok"


def get_note_position(note_idx: int) -> dict:
    """获取笔记的位置信息
    
    返回: {
        found: bool,
        noteId: str,
        x: int,
        y: int,
        inViewport: bool
    }
    """
    result = eval_js_raw(f"""
        (() => {{
            const target = document.querySelector('.feeds-container section.note-item[data-index="{note_idx}"]');
            if (!target) return JSON.stringify({{found: false}});
            const rect = target.getBoundingClientRect();
            const link = target.querySelector('a[href*="/explore/"]');
            const noteId = link ? (link.href.match(/explore\/([a-f0-9]+)/) || [])[1] : null;
            return JSON.stringify({{
                found: true,
                noteId: noteId,
                x: Math.round(rect.left + rect.width / 2),
                y: Math.round(rect.top + rect.height / 2),
                inViewport: rect.top >= 0 && rect.top < window.innerHeight && rect.left >= 0 && rect.left < window.innerWidth
            }});
        }})()
    """)
    try:
        return json.loads(result)
    except:
        return {"found": False}


def click_note_by_index(note_idx: int) -> str:
    """点击指定索引的笔记，返回 note_id
    
    设计约束:
    1. 使用 data-index 属性定位笔记
    2. 如果不在当前视图，智能滚动加载
    3. 滚动后必须重新获取坐标
    4. 使用真实鼠标点击 (mousemove + mousedown + mouseup)
    
    返回: note_id 或空字符串
    """
    log(f"点击笔记索引: {note_idx}")
    
    # 1. 检查当前可见范围
    min_idx, max_idx, count = get_visible_range()
    log(f"当前可见范围: {min_idx} - {max_idx} ({count} 个)", indent=1)
    
    # 2. 如果不在当前视图，滚动加载
    if not (min_idx <= note_idx <= max_idx):
        log(f"目标 {note_idx} 不在当前视图，开始滚动...", indent=1)
        
        # 确定滚动方向
        direction = 1 if note_idx > max_idx else -1
        log(f"滚动方向: {'向下' if direction == 1 else '向上'}", indent=1)
        
        # 获取卡片高度
        card_height_result = eval_js_raw("""
            (() => {
                const cards = document.querySelectorAll('.feeds-container section.note-item');
                if (cards.length === 0) return 300;
                return cards[0].getBoundingClientRect().height;
            })()
        """)
        try:
            card_height = float(card_height_result) if card_height_result else 300
        except:
            card_height = 300
        
        # 计算滚动距离
        viewport_height = 800
        scroll_distance = max(viewport_height - card_height * 2, card_height)
        if direction == -1:
            scroll_distance = -scroll_distance
        
        # 滚动查找
        last_boundary = max_idx if direction == 1 else min_idx
        no_change_count = 0
        max_attempts = 100
        
        for attempt in range(max_attempts):
            scroll_by(scroll_distance)
            time.sleep(2)
            
            new_min, new_max, new_count = get_visible_range()
            log(f"滚动 {attempt + 1}: 范围 {new_min} - {new_max}", indent=2)
            
            # 检查是否找到目标
            if new_min <= note_idx <= new_max:
                log("[OK] 找到目标范围", indent=2)
                break
            
            # 检查边界
            current_boundary = new_max if direction == 1 else new_min
            if direction == 1:
                if current_boundary > last_boundary:
                    no_change_count = 0
                    last_boundary = current_boundary
                else:
                    no_change_count += 1
            else:
                if current_boundary < last_boundary:
                    no_change_count = 0
                    last_boundary = current_boundary
                else:
                    no_change_count += 1
            
            if no_change_count >= 3:
                log("[WARN] 连续3次无变化，到达边界", indent=2)
                return ""
        else:
            log("[FAIL] 滚动100次仍未找到", indent=1)
            return ""
    
    # 3. 获取笔记位置
    pos = get_note_position(note_idx)
    if not pos.get("found"):
        log("[FAIL] 未找到笔记元素", indent=1)
        return ""
    
    note_id = pos.get("noteId", "")
    x = pos.get("x", 0)
    y = pos.get("y", 0)
    in_viewport = pos.get("inViewport", False)
    
    log(f"笔记ID: {note_id}", indent=1)
    log(f"坐标: ({x}, {y}), 在视口内: {in_viewport}", indent=1)
    
    # 4. 如果不在视口内，滚动到中央
    if not in_viewport:
        log("滚动到视口中央...", indent=1)
        if scroll_note_to_center(note_idx):
            time.sleep(1)
            # 重新获取坐标
            pos = get_note_position(note_idx)
            x = pos.get("x", 0)
            y = pos.get("y", 0)
            in_viewport = pos.get("inViewport", False)
            log(f"新坐标: ({x}, {y}), 在视口内: {in_viewport}", indent=1)
        else:
            log("[FAIL] 滚动失败", indent=1)
            return ""
    
    # 5. 验证坐标
    if x <= 0 or y <= 0 or not in_viewport:
        log("[FAIL] 坐标无效", indent=1)
        return ""
    
    # 6. 执行真实点击
    if real_click(x, y):
        return note_id
    else:
        return ""


def check_popup_opened() -> bool:
    """检查笔记详情弹窗是否已打开
    
    精确检测：必须同时满足
    1. 有遮罩层或模态框
    2. 页面中有笔记内容（图片、标题等）
    3. URL包含 explore 或当前在笔记详情页
    """
    result = eval_js_raw("""
        (() => {
            // 1. 检查是否有笔记详情弹窗的特定元素
            const noteModal = document.querySelector('.note-detail-modal, .note-modal, .note-slide');
            const hasMask = !!document.querySelector('.mask, .overlay, [class*="mask"]');
            
            // 2. 检查是否有笔记内容（图片或swiper）
            const hasNoteContent = !!(
                document.querySelector('.swiper-container, .swiper-slide, .note-content img, .detail-content img') ||
                document.querySelector('.note-text, .desc, .title')
            );
            
            // 3. 检查是否有笔记特定的关闭按钮或交互元素
            const hasCloseBtn = !!document.querySelector('.close, .close-btn, [class*="close"]');
            
            // 必须同时有遮罩/模态框 + 笔记内容
            const isNotePopup = (noteModal || hasMask) && hasNoteContent && hasCloseBtn;
            
            return JSON.stringify({
                isOpen: isNotePopup,
                hasModal: !!(noteModal || hasMask),
                hasContent: hasNoteContent,
                hasClose: hasCloseBtn
            });
        })()
    """)
    try:
        data = json.loads(result) if result else {}
        return data.get("isOpen", False)
    except:
        return False


def close_popup() -> bool:
    """关闭笔记弹窗（点击遮罩层）"""
    log("关闭弹窗...")
    # 尝试点击遮罩层
    result = eval_js_raw("""
        (() => {
            const mask = document.querySelector('.mask, .overlay, [class*="mask"]');
            if (mask) {
                mask.click();
                return 'clicked_mask';
            }
            // 尝试按ESC键
            document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', keyCode: 27}));
            return 'esc_pressed';
        })()
    """)
    time.sleep(1)
    log("[OK] 弹窗已关闭")
    return True


def screenshot_slides(note_id: str, output_dir: str = None) -> int:
    """截图笔记的所有幻灯片
    
    返回: 截图数量
    """
    if output_dir is None:
        output_dir = str(SCREENSHOT_DIR)
    
    log("开始截图...")
    
    # 获取幻灯片数量 - 使用更通用的选择器
    slides_count_result = eval_js_raw("""
        (() => {
            // 方法1: 检查swiper分页指示器
            const indicators = document.querySelectorAll('.swiper-pagination-bullet, .slide-indicator, [class*="indicator"], [class*="pagination"]');
            if (indicators.length > 0) return indicators.length;
            
            // 方法2: 检查swiper幻灯片
            const swiperSlides = document.querySelectorAll('.swiper-slide, [class*="slide"]');
            if (swiperSlides.length > 0) return swiperSlides.length;
            
            // 方法3: 检查笔记内容中的图片
            const images = document.querySelectorAll('.note-content img, .detail-content img, .note-detail img, img[class*="note"]');
            if (images.length > 0) return images.length;
            
            // 方法4: 检查所有可见的大图
            const allImages = Array.from(document.querySelectorAll('img'));
            const visibleImages = allImages.filter(img => {
                const rect = img.getBoundingClientRect();
                return rect.width > 200 && rect.height > 200 && rect.top >= 0 && rect.top < window.innerHeight;
            });
            if (visibleImages.length > 0) return visibleImages.length;
            
            return 1; // 默认至少1张
        })()
    """)
    try:
        total_slides = int(slides_count_result) if slides_count_result else 1
    except:
        total_slides = 1
    
    log(f"共 {total_slides} 张图片", indent=1)
    
    # 截图
    for i in range(total_slides):
        filename = f"{note_id}_{i+1:03d}.png"
        filepath = os.path.join(output_dir, filename)
        
        result = run_cli(f'screenshot --filename "{filepath}"', timeout=10)
        if result["success"]:
            log(f"截图 {i+1}/{total_slides}: {filename}", indent=1)
        else:
            log(f"[FAIL] 截图 {i+1} 失败: {result.get('stderr', '')[:100]}", indent=1)
        
        # 切换到下一张
        if i < total_slides - 1:
            eval_js_raw("""
                (() => {
                    const nextBtn = document.querySelector('.swiper-button-next, .next-btn, [class*="next"], [class*="right"]');
                    if (nextBtn) nextBtn.click();
                    else {
                        const container = document.querySelector('.swiper-container, .slide-container, [class*="swiper"]');
                        if (container) container.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowRight'}));
                    }
                })()
            """)
            time.sleep(1)
    
    log(f"[OK] 截图完成: {total_slides} 张")
    return total_slides
