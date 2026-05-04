"""
检查窗口大小和显示大小的区别
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser

def check_window_size():
    p, browser, page = connect_browser()
    
    # Get all size-related info
    sizes = page.evaluate("""() => {
        return {
            // Window size (browser window)
            window: {
                innerWidth: window.innerWidth,
                innerHeight: window.innerHeight,
                outerWidth: window.outerWidth,
                outerHeight: window.outerHeight
            },
            // Screen size (monitor)
            screen: {
                width: screen.width,
                height: screen.height,
                availWidth: screen.availWidth,
                availHeight: screen.availHeight
            },
            // Document size
            document: {
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight,
                clientWidth: document.documentElement.clientWidth,
                clientHeight: document.documentElement.clientHeight
            },
            // Body size
            body: {
                scrollWidth: document.body.scrollWidth,
                scrollHeight: document.body.scrollHeight
            },
            // Viewport (same as window.innerWidth/Height)
            viewport: {
                width: window.innerWidth,
                height: window.innerHeight
            },
            // Device pixel ratio
            devicePixelRatio: window.devicePixelRatio
        };
    }""")
    
    print("窗口大小 vs 显示大小分析:")
    print("="*60)
    print(f"\n1. 浏览器窗口 (Window):")
    print(f"   内部: {sizes['window']['innerWidth']}x{sizes['window']['innerHeight']}")
    print(f"   外部: {sizes['window']['outerWidth']}x{sizes['window']['outerHeight']}")
    
    print(f"\n2. 显示器 (Screen):")
    print(f"   总大小: {sizes['screen']['width']}x{sizes['screen']['height']}")
    print(f"   可用: {sizes['screen']['availWidth']}x{sizes['screen']['availHeight']}")
    
    print(f"\n3. 文档 (Document):")
    print(f"   滚动: {sizes['document']['width']}x{sizes['document']['height']}")
    print(f"   可视: {sizes['document']['clientWidth']}x{sizes['document']['clientHeight']}")
    
    print(f"\n4. Body:")
    print(f"   滚动: {sizes['body']['scrollWidth']}x{sizes['body']['scrollHeight']}")
    
    print(f"\n5. 视口 (Viewport):")
    print(f"   {sizes['viewport']['width']}x{sizes['viewport']['height']}")
    
    print(f"\n6. 设备像素比:")
    print(f"   {sizes['devicePixelRatio']}x")
    
    # Check current viewport setting
    try:
        viewport = page.viewport_size
        print(f"\n7. Playwright设置的视口:")
        print(f"   {viewport}")
    except:
        print(f"\n7. Playwright视口: 未设置")
    
    browser.close()

if __name__ == "__main__":
    check_window_size()
