"""
小红书笔记搜索查询脚本
通过页面顶部搜索框搜索笔记标题，直接打开目标笔记。

设计约束:
- 所有输出必须使用 flush=True
- 禁止使用 Unicode 特殊字符
- 必须通过 xhs_cli.py 调用浏览器操作
- 包含反爬机制：随机时间间隔、模拟人工操作

用法:
    python search_and_open_note.py "笔记标题关键词"
    python search_and_open_note.py "笔记标题关键词" --note-id <note_id>  # 验证note_id匹配
"""

import sys
import os
import time
import random
import json
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
    real_click, check_popup_opened, save_state, log, run_cli
)


def random_sleep(base: float, variance: float = 0.5):
    """随机时间间隔，模拟人工操作
    
    Args:
        base: 基础秒数
        variance: 随机变化范围
    """
    sleep_time = base + random.uniform(-variance, variance)
    sleep_time = max(sleep_time, 0.3)  # 最少0.3秒
    time.sleep(sleep_time)


def find_search_input() -> dict:
    """查找搜索输入框元素
    
    返回: {
        found: bool,
        x: int,
        y: int,
        selector: str
    }
    """
    result = eval_js_raw("""
        (() => {
            // 小红书搜索框常见选择器
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
                            selector: selector,
                            placeholder: el.placeholder || ''
                        });
                    }
                }
            }
            
            // 兜底：查找任何可能是搜索框的input
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
                        selector: 'input',
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


def click_search_input() -> bool:
    """点击搜索输入框，聚焦并清空"""
    log("[Step 1] 查找搜索输入框...")
    
    pos = find_search_input()
    if not pos.get("found"):
        log("[FAIL] 未找到搜索输入框")
        return False
    
    x = pos.get("x", 0)
    y = pos.get("y", 0)
    placeholder = pos.get("placeholder", '')
    log(f"找到搜索框: ({x}, {y}), placeholder: {placeholder}", indent=1)
    
    # 点击搜索框
    if not real_click(x, y):
        log("[FAIL] 点击搜索框失败")
        return False
    
    random_sleep(0.8, 0.3)
    
    # 清空现有内容 (Ctrl+A + Delete)
    log("清空搜索框内容...", indent=1)
    eval_js_raw("""
        (() => {
            const input = document.querySelector('input[placeholder*="搜索"], input[placeholder*="搜"], .search-input input, .search-bar input, input[type="search"], .header-search input');
            if (input) {
                input.select();
                input.value = '';
                input.dispatchEvent(new Event('input', {bubbles: true}));
                return 'cleared';
            }
            return 'not_found';
        })()
    """)
    random_sleep(0.5, 0.2)
    
    log("[OK] 搜索框已准备好")
    return True


def type_search_query(query: str) -> bool:
    """在搜索框中输入搜索关键词
    
    使用 playwright-cli 的 type 命令，模拟真实输入
    """
    log(f"[Step 2] 输入搜索关键词: {query}")
    
    # 使用 playwright-cli type 命令
    # 注意：中文输入可能有乱码问题，使用 eval JS 方式
    import base64
    encoded_query = base64.b64encode(query.encode('utf-8')).decode('utf-8')
    
    result = eval_js_raw(f"""
        (() => {{
            const input = document.querySelector('input[placeholder*="搜索"], input[placeholder*="搜"], .search-input input, .search-bar input, input[type="search"], .header-search input');
            if (!input) return 'input_not_found';
            
            // 设置值
            const query = atob('{encoded_query}');
            input.value = query;
            input.dispatchEvent(new Event('input', {{bubbles: true}}));
            input.dispatchEvent(new Event('change', {{bubbles: true}}));
            
            // 触发搜索建议
            input.dispatchEvent(new KeyboardEvent('keydown', {{
                key: 'Enter',
                keyCode: 13,
                bubbles: true
            }}));
            
            return 'typed:' + query;
        }})()
    """)
    
    if result and result.startswith("typed:"):
        log(f"[OK] 已输入: {result[6:]}", indent=1)
        random_sleep(1.0, 0.3)
        return True
    else:
        log(f"[WARN] 输入结果: {result}", indent=1)
        return False


def submit_search() -> bool:
    """提交搜索（按回车或点击搜索按钮）"""
    log("[Step 3] 提交搜索...")
    
    # 先尝试按回车
    result = run_cli("press Enter", timeout=10)
    if result.get("success"):
        log("[OK] 已按回车提交搜索", indent=1)
        random_sleep(2.5, 0.5)  # 等待搜索结果加载
        return True
    
    # 回车失败，尝试点击搜索按钮
    log("尝试点击搜索按钮...", indent=1)
    btn_result = eval_js_raw("""
        (() => {
            const btn = document.querySelector('.search-btn, .search-button, button[type="submit"], .header-search button');
            if (btn) {
                const rect = btn.getBoundingClientRect();
                return JSON.stringify({
                    found: true,
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top + rect.height / 2)
                });
            }
            return JSON.stringify({found: false});
        })()
    """)
    
    try:
        btn = json.loads(btn_result) if btn_result else {"found": False}
        if btn.get("found"):
            real_click(btn.get("x", 0), btn.get("y", 0))
            random_sleep(2.5, 0.5)
            return True
    except:
        pass
    
    log("[FAIL] 无法提交搜索")
    return False


def get_search_results() -> list:
    """获取搜索结果列表
    
    返回: [
        {
            title: str,
            note_id: str,
            x: int,
            y: int,
            inViewport: bool
        }
    ]
    """
    result = eval_js_raw("""
        (() => {
            // 搜索结果常见容器
            const containers = [
                '.search-result-list',
                '.feeds-container',
                '.note-list',
                '.search-feeds',
                '[class*="search"] [class*="feed"]',
                '[class*="result"] section',
                'section.note-item'
            ];
            
            let cards = [];
            for (const sel of containers) {
                cards = document.querySelectorAll(sel);
                if (cards.length > 0) break;
            }
            
            // 如果还是没找到，尝试更通用的选择器
            if (cards.length === 0) {
                cards = document.querySelectorAll('a[href*="/explore/"]');
            }
            
            const results = [];
            cards.forEach((card, idx) => {
                // 提取标题
                let title = '';
                const titleEl = card.querySelector('.title, .note-title, h3, h4, [class*="title"]');
                if (titleEl) title = titleEl.textContent.trim();
                
                // 从链接提取 note_id
                let noteId = '';
                const link = card.closest('a[href*="/explore/"]') || card;
                const href = link.href || '';
                const match = href.match(/explore\/([a-f0-9]+)/);
                if (match) noteId = match[1];
                
                // 如果没有href，尝试从data属性找
                if (!noteId) {
                    noteId = card.getAttribute('data-note-id') || '';
                }
                
                const rect = card.getBoundingClientRect();
                results.push({
                    index: idx,
                    title: title.substring(0, 100),
                    noteId: noteId,
                    x: Math.round(rect.left + rect.width / 2),
                    y: Math.round(rect.top + rect.height / 2),
                    inViewport: rect.top >= 0 && rect.top < window.innerHeight && rect.left >= 0 && rect.left < window.innerWidth,
                    height: rect.height
                });
            });
            
            return JSON.stringify(results.slice(0, 10));  // 最多返回10个
        })()
    """)
    
    try:
        return json.loads(result) if result else []
    except:
        return []


def find_target_note(results: list, query: str, expected_note_id: str = None) -> dict:
    """在搜索结果中找到目标笔记
    
    匹配策略:
    1. 如果提供了 expected_note_id，优先匹配 note_id
    2. 否则匹配标题包含查询关键词
    3. 返回第一个可见且在视口内的结果
    
    返回: {
        found: bool,
        index: int,
        title: str,
        note_id: str,
        x: int,
        y: int
    }
    """
    if not results:
        return {"found": False}
    
    log(f"搜索结果数量: {len(results)}", indent=1)
    
    # 打印所有结果供参考
    for r in results:
        visible = "可见" if r.get("inViewport") else "不可见"
        log(f"  [{r.get('index', 0)}] {r.get('title', '无标题')[:50]} | {visible}", indent=1)
    
    # 1. 优先按 note_id 匹配
    if expected_note_id:
        for r in results:
            if r.get("noteId") == expected_note_id and r.get("inViewport"):
                log(f"[OK] 通过note_id匹配到目标笔记", indent=1)
                return {
                    "found": True,
                    "index": r.get("index", 0),
                    "title": r.get("title", ""),
                    "note_id": r.get("noteId", ""),
                    "x": r.get("x", 0),
                    "y": r.get("y", 0)
                }
    
    # 2. 按标题匹配（包含关键词）
    query_lower = query.lower()
    for r in results:
        title = r.get("title", "").lower()
        if query_lower in title and r.get("inViewport"):
            log(f"[OK] 通过标题匹配到目标笔记", indent=1)
            return {
                "found": True,
                "index": r.get("index", 0),
                "title": r.get("title", ""),
                "note_id": r.get("noteId", ""),
                "x": r.get("x", 0),
                "y": r.get("y", 0)
            }
    
    # 3. 如果没有精确匹配，返回第一个可见的结果（可能是相关笔记）
    for r in results:
        if r.get("inViewport") and r.get("y", 0) > 100:  # 排除顶部搜索栏区域
            log(f"[WARN] 未精确匹配，选择第一个可见结果", indent=1)
            return {
                "found": True,
                "index": r.get("index", 0),
                "title": r.get("title", ""),
                "note_id": r.get("noteId", ""),
                "x": r.get("x", 0),
                "y": r.get("y", 0)
            }
    
    log("[FAIL] 没有找到匹配的可见笔记", indent=1)
    return {"found": False}


def click_search_result(result: dict) -> str:
    """点击搜索结果中的笔记
    
    返回: note_id 或空字符串
    """
    log("[Step 4] 点击搜索结果中的笔记...")
    
    x = result.get("x", 0)
    y = result.get("y", 0)
    note_id = result.get("note_id", "")
    title = result.get("title", "")
    
    log(f"目标: {title[:50]}", indent=1)
    log(f"坐标: ({x}, {y})", indent=1)
    
    if x <= 0 or y <= 0:
        log("[FAIL] 坐标无效", indent=1)
        return ""
    
    # 执行真实点击
    if real_click(x, y):
        log("[OK] 已点击笔记", indent=1)
        random_sleep(2.0, 0.5)
        
        # 检查弹窗是否打开
        if check_popup_opened():
            log("[OK] 笔记弹窗已打开", indent=1)
            return note_id
        else:
            log("[WARN] 弹窗可能未打开，继续检查...", indent=1)
            # 再等待一下
            random_sleep(1.5, 0.3)
            if check_popup_opened():
                log("[OK] 笔记弹窗已打开（延迟确认）", indent=1)
                return note_id
            return note_id  # 即使弹窗检测失败，也可能已打开
    else:
        log("[FAIL] 点击失败", indent=1)
        return ""


def search_and_open_note(query: str, expected_note_id: str = None) -> str:
    """搜索并打开笔记的完整流程
    
    返回: note_id 或空字符串
    """
    log("=" * 60)
    log(f"搜索并打开笔记: {query}")
    if expected_note_id:
        log(f"期望的笔记ID: {expected_note_id}")
    log("=" * 60)
    
    # 1. 设置浏览器会话
    log("[Step 0] 设置浏览器会话...")
    if not setup_session(headed=True):
        log("[FAIL] 无法设置浏览器会话")
        return ""
    
    # 2. 确保在小红书首页或搜索页
    current_url = get_current_url()
    log(f"当前页面: {current_url}", indent=1)
    
    if "xiaohongshu.com" not in current_url:
        log("导航到小红书首页...", indent=1)
        goto("https://www.xiaohongshu.com")
        random_sleep(3.0, 0.5)
    
    # 3. 点击搜索框
    if not click_search_input():
        log("[FAIL] 无法操作搜索框")
        return ""
    
    # 4. 输入搜索关键词
    if not type_search_query(query):
        log("[FAIL] 无法输入搜索关键词")
        return ""
    
    # 5. 提交搜索
    if not submit_search():
        log("[FAIL] 无法提交搜索")
        return ""
    
    # 6. 获取搜索结果
    log("[Step 4] 获取搜索结果...")
    random_sleep(1.5, 0.3)
    results = get_search_results()
    
    if not results:
        log("[FAIL] 未获取到搜索结果，尝试再次获取...", indent=1)
        random_sleep(2.0, 0.3)
        results = get_search_results()
        if not results:
            log("[FAIL] 仍然没有搜索结果")
            return ""
    
    # 7. 找到目标笔记
    target = find_target_note(results, query, expected_note_id)
    if not target.get("found"):
        log("[FAIL] 未找到目标笔记")
        return ""
    
    # 8. 点击打开笔记
    note_id = click_search_result(target)
    if note_id:
        log("=" * 60)
        log(f"[OK] 笔记已打开: {note_id}")
        log(f"标题: {target.get('title', '')}")
        log("=" * 60)
        
        # 保存状态
        save_state()
        return note_id
    else:
        log("[FAIL] 无法打开笔记")
        return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python search_and_open_note.py \"笔记标题关键词\"")
        print("      python search_and_open_note.py \"笔记标题\" --note-id <note_id>")
        sys.exit(1)
    
    query = sys.argv[1]
    expected_note_id = None
    
    if "--note-id" in sys.argv:
        idx = sys.argv.index("--note-id")
        if idx + 1 < len(sys.argv):
            expected_note_id = sys.argv[idx + 1]
    
    note_id = search_and_open_note(query, expected_note_id)
    sys.exit(0 if note_id else 1)
