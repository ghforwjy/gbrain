"""
检查浏览器状态 (playwright-cli 版)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_cli import (
    check_cli_installed, get_page_info, get_current_url,
    check_login_status_xhs, get_note_cards_count
)


def main():
    print("=" * 60)
    print("浏览器状态检查 (playwright-cli)")
    print("=" * 60)

    # 检查 CLI
    if not check_cli_installed():
        print("playwright-cli: 未安装")
        print("请运行: npm install -g @playwright/cli@latest")
        return 1

    print("playwright-cli: 已安装")

    # 获取页面信息
    info = get_page_info()
    url = info.get("url", "")
    title = info.get("title", "")

    print(f"\n当前页面:")
    print(f"  URL: {url}")
    print(f"  标题: {title}")

    # 检查登录状态
    if "xiaohongshu.com" in url:
        is_logged_in = check_login_status_xhs()
        print(f"\n小红书登录状态: {'已登录' if is_logged_in else '未登录'}")

        if is_logged_in and "tab=fav" in url:
            note_count = get_note_cards_count()
            print(f"收藏夹笔记数量: {note_count}")
    else:
        print("\n当前不在小红书页面")

    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
