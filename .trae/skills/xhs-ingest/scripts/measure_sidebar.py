"""
测量左侧导航栏的实际宽度
"""
import sys
import os
sys.path.insert(0, str(os.path.dirname(os.path.abspath(__file__))))

from xhs_batch import connect_browser

def measure_sidebar():
    p, browser, page = connect_browser()
    
    # Measure sidebar and popup
    measurements = page.evaluate("""() => {
        const sidebar = document.querySelector('.side-bar, .channel-list');
        const mask = document.querySelector('.note-detail-mask');
        
        const results = {};
        
        if (sidebar) {
            const rect = sidebar.getBoundingClientRect();
            results.sidebar = {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height,
                right: rect.right
            };
        }
        
        if (mask) {
            const rect = mask.getBoundingClientRect();
            results.mask = {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            };
        }
        
        // Also measure the note content area
        const noteContent = document.querySelector('.note-content, .interaction-container');
        if (noteContent) {
            const rect = noteContent.getBoundingClientRect();
            results.noteContent = {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            };
        }
        
        return results;
    }""")
    
    print("测量结果:")
    print("="*60)
    
    if measurements.get('sidebar'):
        sb = measurements['sidebar']
        print(f"侧边栏: x={sb['x']}, width={sb['width']}, right={sb['right']}")
    
    if measurements.get('mask'):
        mk = measurements['mask']
        print(f"遮罩层: x={mk['x']}, width={mk['width']}")
    
    if measurements.get('noteContent'):
        nc = measurements['noteContent']
        print(f"笔记内容: x={nc['x']}, width={nc['width']}")
    
    browser.close()

if __name__ == "__main__":
    measure_sidebar()
