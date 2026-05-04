"""
关闭笔记弹框并回到收藏夹 (playwright-cli 版)
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_cli import (
    close_popup, navigate_to_favorites, get_current_url,
    get_note_cards_count, check_cli_installed
)

USER_ID = "608286f10000000001009ad1"


def main():
    if not check_cli_installed():
        print("错误: playwright-cli 未安装")
        return 1

    print(f"当前页面: {get_current_url()}")

    # 关闭弹框
    print("关闭弹框...")
    close_popup()
    time.sleep(1)

    # 导航到收藏夹
    print("导航到收藏夹...")
    navigate_to_favorites(USER_ID)
    time.sleep(2)

    # 检查收藏夹加载
    note_count = get_note_cards_count()
    print(f"收藏夹笔记数量: {note_count}")

    print(f"当前页面: {get_current_url()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
