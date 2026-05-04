"""
自动重启Chrome浏览器，恢复正常视口大小
"""
import subprocess
import time
import os
from pathlib import Path

def restart_chrome():
    """Kill all Chrome processes and restart with correct settings."""
    print("正在关闭Chrome...")
    
    # Kill all chrome processes
    try:
        subprocess.run(["taskkill", "/F", "/IM", "chrome.exe"], 
                      capture_output=True, check=False)
        time.sleep(3)
    except Exception as e:
        print(f"关闭Chrome时出错: {e}")
    
    print("Chrome已关闭，正在重启...")
    
    # Start Chrome with remote debugging
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    if not os.path.exists(chrome_path):
        # Try alternative path
        chrome_path = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    
    if not os.path.exists(chrome_path):
        print("错误: 找不到Chrome浏览器")
        return False
    
    # Start Chrome with remote debugging
    try:
        subprocess.Popen([
            chrome_path,
            "--remote-debugging-port=9223",
            "--no-first-run",
            "--no-default-browser-check",
            "--user-data-dir=d:\\mycode\\gbrain\\.chrome-profile"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        print("Chrome已启动，等待加载...")
        time.sleep(5)
        
        # Verify Chrome is running
        result = subprocess.run(["tasklist", "/FI", "IMAGENAME eq chrome.exe"], 
                              capture_output=True, text=True)
        if "chrome.exe" in result.stdout:
            print("✅ Chrome已成功启动")
            return True
        else:
            print("❌ Chrome启动失败")
            return False
            
    except Exception as e:
        print(f"启动Chrome时出错: {e}")
        return False

if __name__ == "__main__":
    restart_chrome()
