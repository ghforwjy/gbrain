"""
使用 playwright-cli 处理小红书笔记
流程：
1. 打开浏览器并恢复登录态
2. 导航到收藏夹
3. 逐个点击笔记，截图，OCR，保存
4. 关闭弹窗，继续下一个
"""
import subprocess
import json
import time
import os
from pathlib import Path

# 配置
SCREENSHOT_DIR = Path(r"d:\mycode\gbrain\.playwright-cli")
IMAGES_DIR = Path(r"d:\mycode\gbrain\brain\sources\xhs\images")
AUTH_FILE = Path(r"d:\mycode\gbrain\.playwright-cli\xhs_auth.json")

def run_cli(command, timeout=30):
    """运行 playwright-cli 命令"""
    full_command = f"playwright-cli {command}"
    print(f"  执行: {full_command[:80]}...")
    
    result = subprocess.run(
        full_command,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        timeout=timeout
    )
    
    if result.returncode != 0:
        print(f"  错误: {result.stderr[:200]}")
        return None
    
    return result.stdout

def open_browser():
    """打开浏览器并恢复登录态"""
    print("="*60)
    print("步骤1: 打开浏览器")
    print("="*60)
    
    # 打开小红书
    result = run_cli("open https://www.xiaohongshu.com --headed", timeout=10)
    if not result:
        print("❌ 打开浏览器失败")
        return False
    
    time.sleep(3)
    
    # 恢复登录态
    if AUTH_FILE.exists():
        print("恢复登录态...")
        run_cli(f"state-load {AUTH_FILE}")
        run_cli("reload")
        time.sleep(2)
    else:
        print("⚠️ 未找到登录态文件，需要手动登录")
        input("请手动登录小红书，然后按Enter继续...")
        # 保存登录态
        run_cli(f"state-save {AUTH_FILE}")
    
    print("✅ 浏览器已打开")
    return True

def navigate_to_board():
    """导航到收藏夹"""
    print("\n" + "="*60)
    print("步骤2: 导航到收藏夹")
    print("="*60)
    
    result = run_cli("goto https://www.xiaohongshu.com/board/698f3a82000000002502ef57")
    if not result:
        print("❌ 导航失败")
        return False
    
    time.sleep(2)
    print("✅ 已到达收藏夹")
    return True

def click_note_by_title(title):
    """根据标题点击笔记"""
    print(f"\n点击笔记: {title}")
    
    # 使用文本选择器点击
    result = run_cli(f'click "{title}"')
    if not result:
        print("❌ 点击失败")
        return False
    
    time.sleep(2)
    print("✅ 笔记已打开")
    return True

def take_screenshot(filename):
    """截图并保存"""
    print(f"截图: {filename}")
    
    screenshot_path = SCREENSHOT_DIR / filename
    result = run_cli(f"screenshot --filename={screenshot_path}")
    
    if result:
        print(f"✅ 截图已保存: {screenshot_path}")
        return True
    else:
        print("❌ 截图失败")
        return False

def close_popup():
    """关闭笔记弹窗"""
    print("关闭弹窗...")
    
    # 方法1: 按 Escape 键
    result = run_cli("press Escape")
    time.sleep(1)
    
    # 检查是否还在笔记页面
    result = run_cli("eval \"window.location.href\"")
    if result and '/explore/' in result:
        # 还在笔记页面，尝试点击外部
        print("  Escape 未关闭，尝试点击外部...")
        run_cli("mousemove 100 200")
        run_cli("click")  # 在当前鼠标位置点击
        time.sleep(1)
    
    print("✅ 弹窗已关闭")
    return True

def process_single_note(note_title, note_id):
    """处理单个笔记"""
    print("\n" + "="*60)
    print(f"处理笔记: {note_title}")
    print("="*60)
    
    # 1. 点击笔记
    if not click_note_by_title(note_title):
        return False
    
    # 2. 截图
    screenshot_file = f"{note_id}_slide1.png"
    if not take_screenshot(screenshot_file):
        return False
    
    # 3. 关闭弹窗
    if not close_popup():
        return False
    
    print(f"✅ 笔记处理完成: {note_title}")
    return True

def main():
    """主流程"""
    print("="*60)
    print("小红书笔记处理 - Playwright CLI 版本")
    print("="*60)
    
    # 1. 打开浏览器
    if not open_browser():
        return
    
    # 2. 导航到收藏夹
    if not navigate_to_board():
        return
    
    # 3. 获取待处理笔记列表
    # 这里应该从进度文件中读取
    notes_to_process = [
        {"title": "5060的显存，竟然被我扩容到了40GB", "id": "69f333b9000000003503206b"},
        # 添加更多笔记...
    ]
    
    # 4. 逐个处理
    success_count = 0
    for note in notes_to_process:
        if process_single_note(note["title"], note["id"]):
            success_count += 1
        
        # 等待一段时间，避免风控
        time.sleep(3)
    
    print("\n" + "="*60)
    print(f"处理完成: {success_count}/{len(notes_to_process)}")
    print("="*60)
    
    # 5. 关闭浏览器
    run_cli("close")

if __name__ == "__main__":
    main()
