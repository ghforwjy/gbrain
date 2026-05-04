"""
小红书收藏导入 - 状态驱动自动化脚本 (playwright-cli 版)
所有浏览器操作通过 playwright-cli 执行
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_cli import (
    check_cli_installed, open_browser, close_browser, goto, reload_page,
    get_current_url, save_state, load_state, snapshot, click,
    check_login_status_xhs, ensure_login, navigate_to_favorites,
    get_note_cards_count, click_note_by_index, check_popup_opened,
    setup_session
)
from xhs_progress import (
    load_progress, init_progress, mark_note_processing,
    mark_note_failed, get_next_pending_index, get_progress_summary
)

BOARD_ID = "698f3a82000000002502ef57"
USER_ID = "608286f10000000001009ad1"


def run_state_machine():
    """主状态机循环"""
    print("\n" + "=" * 60)
    print("小红书收藏导入 - 状态驱动自动化 (playwright-cli版)")
    print("=" * 60)

    # 显示进度
    print(get_progress_summary())

    # 检查 playwright-cli
    if not check_cli_installed():
        print("错误: playwright-cli 未安装")
        print("请运行: npm install -g @playwright/cli@latest")
        return 1

    try:
        # 设置会话（打开浏览器 + 加载状态 + 检查登录）
        if not setup_session(headed=True):
            print("会话设置失败")
            return 1

        current_url = get_current_url()
        print(f"当前页面: {current_url}")

        # 如果不在收藏夹页面，导航到收藏夹
        if "tab=fav" not in current_url:
            print("\n导航到收藏夹...")
            navigate_to_favorites(USER_ID)
            time.sleep(3)

        # 检查收藏夹加载状态
        note_count = get_note_cards_count()
        print(f"收藏夹笔记数量: {note_count}")

        if note_count == 0:
            print("收藏夹为空，可能需要登录")
            if not ensure_login():
                return 1
            # 重新加载收藏夹
            navigate_to_favorites(USER_ID)
            time.sleep(3)
            note_count = get_note_cards_count()

        # 初始化进度
        progress = load_progress()
        if not progress:
            init_progress(BOARD_ID, "AI概念学习", note_count)

        # 获取下一个待处理笔记
        note_idx = get_next_pending_index()
        if note_idx is None:
            print("所有笔记已处理完成！")
            close_browser()
            return 0

        print(f"\n下一个待处理笔记: [{note_idx}]")

        # 点击笔记
        note_id = click_note_by_index(note_idx)
        if note_id:
            progress = load_progress()
            mark_note_processing(progress, note_idx, note_id)

            # 检查弹框是否打开
            if check_popup_opened():
                print("\n" + "=" * 60)
                print("笔记弹框已打开！")
                print("=" * 60)
                print(f"笔记ID: {note_id}")
                print("\n接下来请运行:")
                print("  python scripts/xhs-ingest/screenshot_slides_cli.py")
                print("=" * 60)
                return 0
            else:
                print("弹框可能未正确打开，请检查浏览器")
                return 1
        else:
            print(f"笔记 [{note_idx}] 打开失败")
            progress = load_progress()
            mark_note_failed(progress, note_idx, "无法打开笔记")
            return 1

    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(run_state_machine())
