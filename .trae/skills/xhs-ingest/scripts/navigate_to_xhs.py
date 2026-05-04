"""
导航到小红书收藏夹
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser, navigate_to_board

def main():
    print("连接浏览器...")
    p, browser, page = connect_browser()
    
    print(f"当前页面: {page.url}")
    
    # Navigate to Xiaohongshu
    if 'xiaohongshu.com' not in page.url:
        print("导航到小红书...")
        page.goto("https://www.xiaohongshu.com")
        import time
        time.sleep(3)
        print(f"当前页面: {page.url}")
        print("请手动登录小红书，然后按Enter继续...")
        input()
    
    # Navigate to board
    print("导航到收藏夹...")
    navigate_to_board(page)
    
    print("已到达收藏夹页面")
    browser.close()

if __name__ == "__main__":
    main()
