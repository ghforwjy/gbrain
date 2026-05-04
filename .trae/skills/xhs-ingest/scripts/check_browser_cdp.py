import os
import sys
import json
import urllib.request
from playwright.sync_api import sync_playwright

# 临时移除代理
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ["NO_PROXY"] = "localhost,127.0.0.1"

CDP_PORT = int(os.environ.get("XHS_CDP_PORT", "9223"))

def main():
    try:
        # 获取CDP信息
        req = urllib.request.Request(f"http://localhost:{CDP_PORT}/json/version")
        with urllib.request.urlopen(req, timeout=5) as resp:
            cdp_info = json.loads(resp.read().decode())
            cdp_url = cdp_info.get("webSocketDebuggerUrl", "")
            print(f"CDP连接成功: {cdp_info.get('Browser', 'Unknown')}")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else None

            if not page:
                print("没有打开的页面")
                return

            print(f"当前页面URL: {page.url}")
            print(f"当前页面标题: {page.title()}")

            # 截图保存
            screenshot_path = ".playwright-cli/check_browser.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"已截图保存到: {screenshot_path}")

            # 检查是否在小红书页面
            if "xiaohongshu.com" in page.url:
                print("✅ 当前在小红书页面")

                # 检查是否需要登录
                if "/login" in page.url:
                    print("❌ 需要登录小红书")
                else:
                    print("✅ 已登录（或不需要登录）")

                    # 检查是否有笔记卡片
                    note_cards = page.evaluate("""() => {
                        return document.querySelectorAll('section.note-item').length;
                    }""")
                    print(f"找到 {note_cards} 个笔记卡片")
            else:
                print(f"⚠️ 当前不在小红书页面，在: {page.url}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
