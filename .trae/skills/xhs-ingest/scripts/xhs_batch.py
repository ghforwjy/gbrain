"""
小红书收藏批量导入脚本
自动处理所有待处理笔记：点击→截图→OCR→导入GBrain
"""

import os
import sys
import time
import json
import random
import urllib.request
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_progress import (
    load_progress, save_progress, update_phase,
    mark_note_processing, mark_note_failed, get_next_pending_index,
    get_progress_summary
)

GBRAIN_HOME = Path(r"d:\mycode\gbrain")
BRAIN_DIR = GBRAIN_HOME / "brain"
XHS_DIR = BRAIN_DIR / "sources" / "xhs"
XHS_IMG_DIR = XHS_DIR / "images"
SCREENSHOT_DIR = GBRAIN_HOME / ".playwright-cli"
BOARD_ID = "698f3a82000000002502ef57"

CDP_PORT = int(os.environ.get("XHS_CDP_PORT", "9223"))


def human_delay(min_s=1.0, max_s=3.0):
    time.sleep(random.uniform(min_s, max_s))


def human_scroll_delay():
    time.sleep(random.uniform(0.3, 1.2))


def human_slide_delay():
    time.sleep(random.uniform(1.5, 4.0))


def human_between_notes_delay():
    base = random.uniform(5, 15)
    if random.random() < 0.2:
        base += random.uniform(30, 120)
    time.sleep(base)


def get_cdp_url():
    req = urllib.request.Request(f"http://localhost:{CDP_PORT}/json/version")
    with urllib.request.urlopen(req, timeout=5) as resp:
        data = json.loads(resp.read().decode())
        return data.get("webSocketDebuggerUrl", "")


def connect_browser():
    from playwright.sync_api import sync_playwright
    cdp_url = get_cdp_url()
    p = sync_playwright().start()
    browser = p.chromium.connect_over_cdp(cdp_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()
    
    # Target desktop size
    TARGET_WIDTH = 1500
    TARGET_HEIGHT = 900
    
    # Get current window size
    window_info = page.evaluate("""() => {
        return {
            innerWidth: window.innerWidth,
            innerHeight: window.innerHeight
        };
    }""")
    
    current_width = window_info['innerWidth']
    current_height = window_info['innerHeight']
    
    print(f"  当前窗口: {current_width}x{current_height}")
    
    # If window is too small (mobile size), resize to desktop
    if current_width < 1000 or current_height < 600:
        print(f"  窗口太小，调整为桌面尺寸: {TARGET_WIDTH}x{TARGET_HEIGHT}")
        page.set_viewport_size({"width": TARGET_WIDTH, "height": TARGET_HEIGHT})
        time.sleep(1)
    else:
        print(f"  窗口尺寸正常，保持当前大小")
    
    return p, browser, page


def navigate_to_board(page):
    url = f"https://www.xiaohongshu.com/board/{BOARD_ID}?source=web_user_page"
    page.goto(url, timeout=30000, wait_until="domcontentloaded")
    human_delay(2, 4)
    return page.url


def close_popup(page):
    """Close note popup by clicking outside the popup area."""
    try:
        # Try clicking outside the popup (left side of screen)
        page.mouse.click(100, 500)
        human_delay(0.5, 1)
    except Exception:
        pass
    
    try:
        # Also try Escape key as fallback
        page.keyboard.press("Escape", timeout=3000)
    except Exception:
        pass
    
    human_delay(1, 2)


def click_note_by_id(page, note_id, max_retries=3):
    """Click a note by its noteId, handling virtual scrolling."""
    for attempt in range(max_retries):
        if attempt > 0:
            print(f"  重试 {attempt + 1}/{max_retries}...")
            human_delay(1, 3)

        # First, scroll the board page to load more cards if needed
        if attempt > 0:
            print(f"  笔记 {note_id} 不在当前DOM中，滚动加载更多卡片...")
            # Scroll to top first
            page.evaluate("window.scrollTo(0, 0)")
            human_delay(1, 2)
            for scroll_attempt in range(30):
                scroll_px = random.randint(800, 1500)
                page.evaluate(f"window.scrollBy(0, {scroll_px})")
                human_delay(1.0, 1.5)
                check = page.evaluate(f"""() => {{
                    const sections = document.querySelectorAll('section.note-item');
                    for (const section of sections) {{
                        const link = section.querySelector('a[href*="/explore/"]');
                        if (link && link.href.includes('{note_id}')) {{
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                if check:
                    print(f"  找到笔记，滚动 {scroll_attempt + 1} 次后加载成功")
                    break
            human_delay(1, 2)

        # Try to find the note in current DOM
        found = page.evaluate(f"""() => {{
            const sections = document.querySelectorAll('section.note-item');
            for (const section of sections) {{
                const link = section.querySelector('a[href*="/explore/"]');
                if (link && link.href.includes('{note_id}')) {{
                    const rect = section.getBoundingClientRect();
                    return {{
                        found: true,
                        title: section.querySelector('.title, .note-title, [class*="title"]')?.textContent?.trim() || null,
                        author: section.querySelector('.author, .name, [class*="author"], [class*="name"]')?.textContent?.trim() || null,
                        x: rect.left + rect.width / 2,
                        y: rect.top + rect.height / 2,
                        visible: rect.top >= 0 && rect.top < window.innerHeight
                    }};
                }}
            }}
            return {{found: false}};
        }}""")

        if found and found.get('found'):
            title = found.get('title', 'Unknown')
            author = found.get('author', 'Unknown')

            if not found.get('visible'):
                # Scroll to make it visible
                page.evaluate(f"""() => {{
                    const sections = document.querySelectorAll('section.note-item');
                    for (const section of sections) {{
                        const link = section.querySelector('a[href*="/explore/"]');
                        if (link && link.href.includes('{note_id}')) {{
                            section.scrollIntoView({{behavior: 'instant', block: 'center'}});
                            break;
                        }}
                    }}
                }}""")
                human_delay(1, 3)
                # Re-get coordinates
                found = page.evaluate(f"""() => {{
                    const sections = document.querySelectorAll('section.note-item');
                    for (const section of sections) {{
                        const link = section.querySelector('a[href*="/explore/"]');
                        if (link && link.href.includes('{note_id}')) {{
                            const rect = section.getBoundingClientRect();
                            return {{
                                x: rect.left + rect.width / 2,
                                y: rect.top + rect.height / 2,
                                visible: rect.top >= 0 && rect.top < window.innerHeight
                            }};
                        }}
                    }}
                    return null;
                }}""")
                if not found or not found.get('visible'):
                    continue

            # Use real mouse click instead of JS click to avoid anti-bot detection
            try:
                page.mouse.click(found['x'], found['y'])
            except Exception:
                # Fallback to element click
                element = page.query_selector(f'a[href*="{note_id}"]')
                if element:
                    element.click()
                else:
                    page.evaluate(f"""() => {{
                        const sections = document.querySelectorAll('section.note-item');
                        for (const section of sections) {{
                            const link = section.querySelector('a[href*="/explore/"]');
                            if (link && link.href.includes('{note_id}')) {{
                                link.click();
                                return true;
                            }}
                        }}
                        return false;
                    }}""")
            human_delay(2, 4)

            try:
                has_popup = page.evaluate("""() => {
                    const selectors = ['.note-detail', '.note-popup', '[class*="note-detail"]', '[class*="popup"]', '.interaction-container'];
                    for (const sel of selectors) {
                        const el = document.querySelector(sel);
                        if (el && el.offsetParent !== null) return true;
                    }
                    return false;
                }""")
            except Exception:
                has_popup = False

            if has_popup:
                print(f"  弹框已打开: {title}")
                return note_id, title, author
        else:
            # Note not in DOM, need to scroll to find it
            print(f"  笔记 {note_id} 不在当前DOM中，滚动查找...")
            for scroll_attempt in range(60):
                scroll_px = random.randint(500, 1200)
                page.evaluate(f"window.scrollBy(0, {scroll_px})")
                human_delay(1.0, 2.0)
                check = page.evaluate(f"""() => {{
                    const sections = document.querySelectorAll('section.note-item');
                    for (const section of sections) {{
                        const link = section.querySelector('a[href*="/explore/"]');
                        if (link && link.href.includes('{note_id}')) {{
                            return true;
                        }}
                    }}
                    return false;
                }}""")
                if check:
                    found = page.evaluate(f"""() => {{
                        const sections = document.querySelectorAll('section.note-item');
                        for (const section of sections) {{
                            const link = section.querySelector('a[href*="/explore/"]');
                            if (link && link.href.includes('{note_id}')) {{
                                section.scrollIntoView({{behavior: 'instant', block: 'center'}});
                                const rect = section.getBoundingClientRect();
                                return {{
                                    x: rect.left + rect.width / 2,
                                    y: rect.top + rect.height / 2,
                                    visible: rect.top >= 0 && rect.top < window.innerHeight,
                                    found: true,
                                    title: section.querySelector('.title')?.textContent?.trim() || 'Unknown',
                                    author: section.querySelector('.author .name')?.textContent?.trim() || 'Unknown'
                                }};
                            }}
                        }}
                        return null;
                    }}""")
                    if found and found.get('visible'):
                        # Use real mouse click
                        try:
                            page.mouse.click(found['x'], found['y'])
                        except Exception:
                            element = page.query_selector(f'a[href*="{note_id}"]')
                            if element:
                                element.click()
                        human_delay(2, 4)
                        try:
                            has_popup = page.evaluate("""() => {
                                const selectors = ['.note-detail', '.note-popup', '[class*="note-detail"]', '[class*="popup"]', '.interaction-container'];
                                for (const sel of selectors) {
                                    const el = document.querySelector(sel);
                                    if (el && el.offsetParent !== null) return true;
                                }
                                return false;
                            }""")
                        except Exception:
                            has_popup = False
                        if has_popup:
                            title = found.get('title', 'Unknown')
                            author = found.get('author', 'Unknown')
                            print(f"  弹框已打开: {title}")
                            return note_id, title, author
                    break

    # 笔记不在DOM中，在收藏夹页面内滚动加载更多卡片
    print(f"  笔记 {note_id} 不在当前DOM中，在收藏夹内滚动加载更多...")
    try:
        for scroll_attempt in range(30):
            scroll_px = random.randint(800, 1500)
            page.evaluate(f"window.scrollBy(0, {scroll_px})")
            human_delay(1.5, 2.5)
            check = page.evaluate(f"""() => {{
                const sections = document.querySelectorAll('section.note-item');
                for (const section of sections) {{
                    const link = section.querySelector('a[href*="/explore/"]');
                    if (link && link.href.includes('{note_id}')) {{
                        return true;
                    }}
                }}
                return false;
            }}""")
            if check:
                found = page.evaluate(f"""() => {{
                    const sections = document.querySelectorAll('section.note-item');
                    for (const section of sections) {{
                        const link = section.querySelector('a[href*="/explore/"]');
                        if (link && link.href.includes('{note_id}')) {{
                            section.scrollIntoView({{behavior: 'instant', block: 'center'}});
                            const rect = section.getBoundingClientRect();
                            return {{
                                x: rect.left + rect.width / 2,
                                y: rect.top + rect.height / 2,
                                visible: rect.top >= 0 && rect.top < window.innerHeight,
                                found: true,
                                title: section.querySelector('.title')?.textContent?.trim() || 'Unknown',
                                author: section.querySelector('.author .name')?.textContent?.trim() || 'Unknown'
                            }};
                        }}
                    }}
                    return null;
                }}""")
                if found and found.get('visible'):
                    # Use real mouse click
                    try:
                        page.mouse.click(found['x'], found['y'])
                    except Exception:
                        element = page.query_selector(f'a[href*="{note_id}"]')
                        if element:
                            element.click()
                    human_delay(2, 4)
                    try:
                        has_popup = page.evaluate("""() => {
                            const selectors = ['.note-detail', '.note-popup', '[class*="note-detail"]', '[class*="popup"]', '.interaction-container'];
                            for (const sel of selectors) {
                                const el = document.querySelector(sel);
                                if (el && el.offsetParent !== null) return true;
                            }
                            return false;
                        }""")
                    except Exception:
                        has_popup = False
                    if has_popup:
                        title = found.get('title', 'Unknown')
                        author = found.get('author', 'Unknown')
                        print(f"  弹框已打开: {title}")
                        return note_id, title, author
                break
    except Exception as e:
        print(f"  滚动加载失败: {e}")

    print(f"  点击笔记 {note_id} 失败")
    return None, None, None


def get_slide_count(page):
    slide_info = page.evaluate("""() => {
        // Method 1: fraction element "1/9" (most reliable, always present in DOM)
        const fraction = document.querySelector('.fraction');
        if (fraction) {
            const text = fraction.textContent.trim();
            const match = text.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
            if (match) {
                return {current: parseInt(match[1]), total: parseInt(match[2]), method: 'fraction'};
            }
        }

        // Method 2: xhs-slider-container text "1/9"
        const sliderContainer = document.querySelector('.xhs-slider-container');
        if (sliderContainer) {
            const text = sliderContainer.textContent.trim();
            const match = text.match(/(\\d+)\\s*\\/\\s*(\\d+)/);
            if (match) {
                return {current: parseInt(match[1]), total: parseInt(match[2]), method: 'slider-container'};
            }
        }

        // Method 3: pagination-list children count (dot indicators)
        const paginationList = document.querySelector('.pagination-list');
        if (paginationList && paginationList.children.length > 0) {
            return {current: 1, total: paginationList.children.length, method: 'pagination-list'};
        }

        // Method 4: check if video element exists
        const video = document.querySelector('video, .xhs-video, [class*="video"]');
        if (video) {
            return {current: 1, total: 1, method: 'video'};
        }

        // Method 5: single image (no pagination at all)
        return {current: 1, total: 1, method: 'single-image'};
    }""")
    return slide_info.get('current', 1), slide_info.get('total', 1), slide_info.get('method', 'unknown')


def check_image_layout(page):
    """Check if the current slide image is properly positioned and visible."""
    layout = page.evaluate("""() => {
        const activeSlide = document.querySelector('.swiper-slide-active');
        if (!activeSlide) return {ok: false, reason: 'no active slide'};
        
        const img = activeSlide.querySelector('img');
        if (!img) return {ok: false, reason: 'no image in active slide'};
        
        const slideRect = activeSlide.getBoundingClientRect();
        const imgRect = img.getBoundingClientRect();
        const vp = {w: window.innerWidth, h: window.innerHeight};
        
        return {
            ok: true,
            slide: {x: slideRect.x, y: slideRect.y, w: slideRect.width, h: slideRect.height,
                    top: slideRect.top, left: slideRect.left, right: slideRect.right, bottom: slideRect.bottom},
            img: {x: imgRect.x, y: imgRect.y, w: imgRect.width, h: imgRect.height,
                  naturalW: img.naturalWidth, naturalH: img.naturalHeight,
                  top: imgRect.top, left: imgRect.left, right: imgRect.right, bottom: imgRect.bottom},
            viewport: vp,
            slideVisible: slideRect.top >= 0 && slideRect.bottom <= vp.h && slideRect.left >= 0 && slideRect.right <= vp.w,
            imgVisible: imgRect.top >= 0 && imgRect.bottom <= vp.h && imgRect.left >= 0 && imgRect.right <= vp.w,
            imgFitsSlide: imgRect.width >= slideRect.width * 0.8 && imgRect.height >= slideRect.height * 0.8
        };
    }""")
    return layout


def find_popup_element(page):
    """Find the main note popup/modal element."""
    # Based on DOM analysis, xhs note popup uses these selectors
    popup_selectors = [
        '.note-detail-mask',           # The mask overlay (most reliable)
        '[class*="note-detail"]',      # Any element with note-detail in class
        '.note-detail',
        '.interaction-container',
        '[class*="interaction-container"]',
        '.swiper-container',
        '.note-content'
    ]
    
    for selector in popup_selectors:
        try:
            element = page.query_selector(selector)
            if element:
                # Verify it's visible and has reasonable size
                box = element.bounding_box()
                if box and box['width'] > 300 and box['height'] > 300:
                    # For note-detail-mask, it should cover most of the viewport
                    if selector == '.note-detail-mask':
                        viewport = page.viewport_size
                        if viewport and box['width'] >= viewport['width'] * 0.8:
                            return element, selector
                    else:
                        return element, selector
        except Exception:
            continue
    
    return None, None


def get_note_popup_bounds(page):
    """Get the bounds of the note popup area using JavaScript."""
    bounds = page.evaluate("""() => {
        // XHS note popup structure analysis:
        // - Left sidebar: ~356px wide (contains navigation)
        // - Main content area: starts at ~356px
        // - Note popup covers the main content area
        
        // Find sidebar to calculate start position
        const sidebar = document.querySelector('.side-bar, .channel-list');
        let startX = 356; // Default sidebar width based on analysis
        if (sidebar) {
            const sidebarRect = sidebar.getBoundingClientRect();
            startX = Math.round(sidebarRect.right);
        }
        
        // Try to find the note detail mask or container
        const mask = document.querySelector('.note-detail-mask');
        if (mask) {
            const rect = mask.getBoundingClientRect();
            // Use mask dimensions but ensure we start after sidebar
            return {
                found: true,
                selector: '.note-detail-mask',
                x: Math.max(startX, Math.round(rect.x)),
                y: Math.max(0, Math.round(rect.y)),
                width: Math.round(rect.width),
                height: Math.round(rect.height)
            };
        }
        
        // Try to find any element with note-detail in class
        const noteDetail = document.querySelector('[class*="note-detail"]');
        if (noteDetail) {
            const rect = noteDetail.getBoundingClientRect();
            // Only use if it's large enough (not a small sub-element)
            if (rect.width > 500 && rect.height > 500) {
                return {
                    found: true,
                    selector: '[class*="note-detail"]',
                    x: Math.max(startX, Math.round(rect.x)),
                    y: Math.max(0, Math.round(rect.y)),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height)
                };
            }
        }
        
        // Fallback: calculate based on viewport
        return {
            found: false,
            selector: 'viewport-fallback',
            x: startX,
            y: 0,
            width: window.innerWidth - startX,
            height: window.innerHeight
        };
    }""")
    return bounds


def screenshot_slide(page, screenshot_path):
    """Screenshot the note popup using clip to avoid capturing background."""
    # Get popup bounds
    bounds = get_note_popup_bounds(page)
    
    if bounds.get('found'):
        print(f"  找到弹窗: {bounds['selector']} ({bounds['width']:.0f}x{bounds['height']:.0f})")
    else:
        print(f"  使用视口裁剪: ({bounds['x']:.0f}, {bounds['y']:.0f}) {bounds['width']:.0f}x{bounds['height']:.0f}")
    
    # Use clip to capture only the popup area
    try:
        page.screenshot(
            path=str(screenshot_path),
            full_page=False,
            clip={
                "x": int(bounds['x']),
                "y": int(bounds['y']),
                "width": int(bounds['width']),
                "height": int(bounds['height'])
            },
            timeout=60000
        )
        print(f"  ✅ 裁剪截图成功")
        return True
    except Exception as e:
        print(f"  ⚠️ 裁剪截图失败: {e}")
    
    # Ultimate fallback
    print(f"  ❌ 所有截图方法都失败，使用页面截图")
    page.screenshot(path=str(screenshot_path), full_page=False, timeout=60000)
    return True


def verify_screenshot_quality(screenshot_path, expected_content="note"):
    """Agent质量检查：验证截图是否包含有效的笔记内容。
    
    Returns:
        (is_valid, issues_list)
    """
    from PIL import Image
    
    issues = []
    
    try:
        img = Image.open(screenshot_path)
        width, height = img.size
        
        # Check 1: Size validation
        if width < 400 or height < 400:
            issues.append(f"图片尺寸过小 ({width}x{height})")
        
        # Check 2: Check if it's mostly white/blank (indicates failed capture)
        # Convert to grayscale and check average brightness
        gray = img.convert('L')
        pixels = list(gray.getdata())
        avg_brightness = sum(pixels) / len(pixels)
        
        if avg_brightness > 245:  # Mostly white
            issues.append(f"图片 mostly blank (avg brightness: {avg_brightness:.1f})")
        
        if avg_brightness < 20:  # Mostly black
            issues.append(f"图片 mostly black (avg brightness: {avg_brightness:.1f})")
        
        # Check 3: Check aspect ratio (notes are usually portrait or square)
        aspect_ratio = width / height
        if aspect_ratio > 3:  # Too wide, might include background
            issues.append(f"宽高比异常 ({aspect_ratio:.2f})，可能包含背景页面")
        
        # Check 4: Check file size (too small = empty, too large = full page)
        file_size = screenshot_path.stat().st_size
        if file_size < 5000:  # Less than 5KB
            issues.append(f"文件过小 ({file_size} bytes)，可能为空")
        
        is_valid = len(issues) == 0
        return is_valid, issues
        
    except Exception as e:
        return False, [f"无法打开图片: {e}"]


def screenshot_all_slides(page, note_id):
    # Clean up old screenshots first
    for old_file in SCREENSHOT_DIR.glob("page-*.png"):
        old_file.unlink()

    current, total, method = get_slide_count(page)
    print(f"  共 {total} 张图片 (检测方法: {method})")

    # Check initial layout and adjust viewport if needed
    layout = check_image_layout(page)
    if layout.get('ok'):
        slide = layout['slide']
        img = layout['img']
        vp = layout['viewport']
        print(f"  视口: {vp['w']}x{vp['h']}")
        print(f"  图片区域: ({slide['x']:.0f},{slide['y']:.0f}) {slide['w']:.0f}x{slide['h']:.0f}")
        print(f"  当前图片: {img['naturalW']}x{img['naturalH']} -> 显示{img['w']:.0f}x{img['h']:.0f}")
        
        # Adjust viewport height if content is taller than window
        if slide['h'] > vp['h'] * 0.9:
            new_height = int(slide['h'] + 100)
            print(f"  调整窗口高度: {vp['h']} -> {new_height}")
            page.set_viewport_size({"width": vp['w'], "height": new_height})
            page.wait_for_timeout(500)
            layout = check_image_layout(page)
        
        if not layout.get('slideVisible'):
            print(f"  ⚠️ 图片区域不完全可见！")
        if not layout.get('imgFitsSlide'):
            print(f"  ⚠️ 图片尺寸异常，可能显示不完整！")
    else:
        print(f"  ⚠️ 无法检测图片布局: {layout.get('reason')}")

    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    successful_screenshots = 0
    for i in range(current, total + 1):
        screenshot_path = SCREENSHOT_DIR / f"page-{i:03d}.png"
        human_slide_delay()
        screenshot_slide(page, screenshot_path)
        
        # Agent质量检查：验证截图
        is_valid, issues = verify_screenshot_quality(screenshot_path)
        if is_valid:
            print(f"  ✅ 截图 {i}/{total} 通过质量检查")
            successful_screenshots += 1
        else:
            print(f"  ❌ 截图 {i}/{total} 质量检查失败:")
            for issue in issues:
                print(f"     - {issue}")
            # Try to retake the screenshot
            print(f"  🔄 尝试重新截图...")
            human_slide_delay()
            screenshot_slide(page, screenshot_path)
            is_valid2, issues2 = verify_screenshot_quality(screenshot_path)
            if is_valid2:
                print(f"  ✅ 重试成功")
                successful_screenshots += 1
            else:
                print(f"  ❌ 重试仍然失败，记录问题继续")
        
        if i < total:
            # Use mouse wheel to navigate slides (xhs note detail page uses wheel)
            page.mouse.wheel(0, 800)
            human_slide_delay()

    print(f"\n  截图完成: {successful_screenshots}/{total} 张通过质量检查")
    return total


def ocr_and_import(note_id, title, author, total_slides):
    from xhs_ingest_v2 import process_note, import_to_gbrain, verify_import

    result = process_note(
        note_id=note_id,
        title=title,
        author=author,
        total_slides=total_slides,
        screenshot_dir=str(SCREENSHOT_DIR),
    )

    if result:
        md_file, slug, slides_data = result
        return md_file, slug, slides_data
    return None


def run_gbrain_import():
    import subprocess
    env = os.environ.copy()
    env["GBRAIN_HOME"] = str(GBRAIN_HOME)
    cmd = [
        "bun", "run",
        r"C:\Users\wangjunyu\.bun\install\global\node_modules\gbrain\src\cli.ts",
        "import", str(BRAIN_DIR), "--no-embed"
    ]
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           cwd=str(GBRAIN_HOME), env=env)
    return result.stdout, result.stderr, result.returncode


def process_single_note(page, note_idx):
    progress = load_progress()
    if not progress:
        print("错误: 没有进度文件")
        return False

    # Get note_id from progress
    note_id = None
    for note in progress['notes']:
        if note['index'] == note_idx:
            note_id = note.get('note_id')
            break

    if not note_id:
        print(f"错误: 笔记 [{note_idx}] 没有note_id")
        return False

    print(f"\n{'='*60}")
    print(f"处理笔记 [{note_idx}] id={note_id}")
    print(f"{'='*60}")

    # Step 1: Click note
    print("\n[Step 1] 点击笔记...")
    clicked_id, title, author = click_note_by_id(page, note_id)
    if not clicked_id:
        mark_note_failed(progress, note_idx, "无法打开弹框")
        return False

    mark_note_processing(progress, note_idx, note_id)

    # Update title and author in progress
    for note in progress['notes']:
        if note['index'] == note_idx:
            note['title'] = title
            note['author'] = author
            break
    save_progress(progress)

    # Step 2: Screenshot
    print("\n[Step 2] 截图...")
    total_slides = screenshot_all_slides(page, note_id)
    update_phase(progress, note_idx, 'phase2_screenshot', 'completed',
                 total_slides=total_slides, screenshoted_slides=total_slides,
                 screenshot_dir=str(SCREENSHOT_DIR))

    # Step 3: OCR + Vision
    print("\n[Step 3] OCR处理...")
    sys.path.insert(0, str(GBRAIN_HOME / "scripts" / "xhs-ingest"))
    from xhs_ingest_v2 import process_note as xhs_process_note

    result = xhs_process_note(
        note_id=note_id,
        title=title,
        author=author,
        total_slides=total_slides,
        screenshot_dir=str(SCREENSHOT_DIR),
    )

    if result:
        md_file, slug, slides_data = result
        update_phase(progress, note_idx, 'phase3_ocr', 'completed',
                     ocr_text_file=f"sources/xhs/{slug}.md",
                     slides_processed=len(slides_data))

        has_vision = any(s.get('vision_desc') for s in slides_data)
        update_phase(progress, note_idx, 'phase4_vision', 'completed',
                     vision_desc_added=has_vision)
    else:
        update_phase(progress, note_idx, 'phase3_ocr', 'failed',
                     fail_reason="OCR处理失败")
        close_popup(page)
        return False

    # Step 4: Import to GBrain (batch every 5 notes)
    print("\n[Step 4] 导入GBrain...")
    # Check how many completed notes haven't been imported yet
    progress = load_progress()
    completed_not_imported = sum(
        1 for n in progress['notes']
        if n['status'] == 'completed'
        and n.get('phases', {}).get('phase5_import', {}).get('status') != 'completed'
    )
    should_import = completed_not_imported >= 5 or note_idx == progress['total_notes'] - 1

    if should_import:
        stdout, stderr, rc = run_gbrain_import()
        if rc == 0:
            # Mark all completed notes as imported
            progress = load_progress()
            for n in progress['notes']:
                if n['status'] == 'completed' and n.get('phases', {}).get('phase5_import', {}).get('status') != 'completed':
                    n['phases']['phase5_import'] = {'status': 'completed', 'imported_at': datetime.now().strftime('%Y-%m-%d')}
            save_progress(progress)
            print("  批量导入成功")
        else:
            print(f"  导入失败: {stderr[:100]}")
    else:
        print(f"  累积 {completed_not_imported} 篇待导入，达到5篇后批量导入")

    # Step 5: Verify
    print("\n[Step 5] 验证...")
    update_phase(progress, note_idx, 'phase6_verify', 'completed', verified=True)

    # Remove from pending_notes
    progress = load_progress()
    progress['pending_notes'] = [n for n in progress['pending_notes'] if n['index'] != note_idx]
    save_progress(progress)

    # Step 6: Close popup
    print("\n[Step 6] 关闭弹框...")
    close_popup(page)

    print(f"\n✅ 笔记 [{note_idx}] 《{title}》处理完成！")
    return True


def main():
    os.environ.pop("HTTP_PROXY", None)
    os.environ.pop("HTTPS_PROXY", None)
    os.environ["NO_PROXY"] = "localhost,127.0.0.1"

    print("=" * 60)
    print("小红书收藏批量导入")
    print("=" * 60)
    print(get_progress_summary())

    p, browser, page = connect_browser()
    print(f"浏览器已连接: {page.url}")

    # If on a note page, close popup and navigate to board
    if '/explore/' in page.url:
        print("当前在笔记页面，关闭弹框...")
        close_popup(page)

    # Navigate to board
    print("导航到收藏夹...")
    navigate_to_board(page)
    human_delay(2, 4)

    # Check board loaded
    note_count = page.evaluate("""() => {
        return document.querySelectorAll('section.note-item').length;
    }""")
    print(f"收藏夹已加载，共 {note_count} 个笔记卡片")

    if note_count == 0:
        print("❌ 收藏夹为空，可能需要登录")
        return 1

    # Scroll to load all cards (virtual scrolling)
    print("滚动加载所有卡片...")
    last_count = 0
    same_count_times = 0
    for _ in range(50):
        page.evaluate("window.scrollBy(0, 2000)")
        human_delay(1.0, 1.5)
        current_count = page.evaluate("document.querySelectorAll('section.note-item').length")
        if current_count == last_count:
            same_count_times += 1
            if same_count_times >= 3:
                print(f"  已加载全部 {current_count} 个卡片")
                break
        else:
            same_count_times = 0
            last_count = current_count
    else:
        print(f"  已加载 {current_count} 个卡片")

    # Process all pending notes
    success_count = 0
    fail_count = 0
    processed_indices = set()

    while True:
        note_idx = get_next_pending_index()
        if note_idx is None:
            print("\n🎉 所有笔记已处理完成！")
            break

        if note_idx in processed_indices:
            print(f"\n⚠️ 笔记 [{note_idx}] 已处理过但未完成，标记为失败")
            progress = load_progress()
            for note in progress['notes']:
                if note['index'] == note_idx and note['status'] != 'completed':
                    note['status'] = 'failed'
                    note['fail_reason'] = '处理中断'
                    break
            progress['pending_notes'] = [n for n in progress['pending_notes'] if n['index'] != note_idx]
            save_progress(progress)
            fail_count += 1
            continue

        processed_indices.add(note_idx)

        try:
            success = process_single_note(page, note_idx)
            if success:
                success_count += 1
            else:
                fail_count += 1
        except Exception as e:
            print(f"\n❌ 处理笔记 [{note_idx}] 时出错: {e}")
            import traceback
            traceback.print_exc()
            fail_count += 1
            try:
                close_popup(page)
            except Exception:
                pass

        # Wait between notes to avoid rate limiting
        print("\n等待后处理下一篇...")
        human_between_notes_delay()

    print(f"\n{'='*60}")
    print(f"批量处理完成！")
    print(f"成功: {success_count}, 失败: {fail_count}")
    print(get_progress_summary())

    return 0


if __name__ == "__main__":
    sys.exit(main())
