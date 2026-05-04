"""
检查弹框状态 (playwright-cli 版)
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_cli import (
    check_cli_installed, get_current_url,
    check_popup_opened, get_note_cards_count
)


def main():
    if not check_cli_installed():
        print("错误: playwright-cli 未安装")
        return 1

    print(f"当前页面: {get_current_url()}")

    # 检查弹框
    has_popup = check_popup_opened()
    print(f"弹框状态: {'已打开' if has_popup else '未打开'}")

    # 检查笔记卡片
    note_count = get_note_cards_count()
    print(f"笔记卡片数量: {note_count}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
