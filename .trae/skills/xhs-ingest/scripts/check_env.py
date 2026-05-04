#!/usr/bin/env python3
"""
xhs-ingest 环境检测脚本
用于验证当前机器是否满足运行条件

用法:
    python check_env.py
"""

import subprocess
import sys
import os
from pathlib import Path


def check_python_version():
    """检查Python版本"""
    version = sys.version_info
    ok = version.major >= 3 and version.minor >= 8
    status = "[OK]" if ok else "[FAIL]"
    print(f"{status} Python {version.major}.{version.minor}.{version.micro} (需要 >= 3.8)")
    return ok


def check_module(module_name, import_name=None):
    """检查Python模块是否已安装"""
    if import_name is None:
        import_name = module_name
    try:
        __import__(import_name)
        print(f"[OK] {module_name}")
        return True
    except ImportError:
        print(f"[FAIL] {module_name} (未安装: pip install {module_name})")
        return False


def check_playwright_cli():
    """检查playwright-cli是否可用"""
    # 先尝试直接运行
    try:
        result = subprocess.run(
            "playwright-cli --version", shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            print(f"[OK] playwright-cli: {result.stdout.strip()}")
            return True
    except:
        pass

    # 尝试where查找
    try:
        result = subprocess.run(
            "where playwright-cli", shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0 and result.stdout.strip():
            print(f"[OK] playwright-cli 路径: {result.stdout.strip().split()[0]}")
            return True
    except:
        pass

    print("[FAIL] playwright-cli (未安装: npm install -g @anthropic-ai/playwright-cli)")
    return False


def check_gbrain_cli():
    """检查gbrain CLI是否可用"""
    methods = [
        ("gbrain --version", "gbrain (PATH)"),
        ("bun run gbrain --version", "bun run gbrain"),
        ("npx gbrain --version", "npx gbrain"),
    ]

    for cmd, label in methods:
        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True,
                timeout=5, encoding="utf-8", errors="replace"
            )
            if result.returncode == 0:
                print(f"[OK] gbrain CLI ({label}): {result.stdout.strip()}")
                return True
        except:
            pass

    # 检查 bun 全局安装目录
    bun_global = Path(os.environ.get("USERPROFILE", "")) / ".bun" / "install" / "global"
    candidates = [
        bun_global / "node_modules" / "gbrain" / "src" / "cli.ts",
        bun_global / "node_modules" / "gbrain" / "dist" / "cli.js",
    ]
    for candidate in candidates:
        if candidate.exists():
            try:
                cmd = f'bun run "{candidate}" --version'
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, text=True,
                    timeout=5, encoding="utf-8", errors="replace"
                )
                if result.returncode == 0:
                    print(f"[OK] gbrain CLI (bun global): {result.stdout.strip()}")
                    return True
            except:
                pass

    print("[FAIL] gbrain CLI (未安装或不在PATH中)")
    return False


def check_project_structure():
    """检查项目目录结构"""
    # 检测项目根目录
    env_root = os.environ.get('GBRAIN_HOME')
    if env_root:
        project_root = Path(env_root)
        print(f"[OK] GBRAIN_HOME 环境变量: {project_root}")
    else:
        # 从脚本位置推算
        script_dir = Path(__file__).resolve().parent
        project_root = script_dir.parent.parent.parent.parent.parent
        print(f"[WARN] GBRAIN_HOME 未设置，从脚本位置推算: {project_root}")

    checks = [
        (project_root / ".gbrain", ".gbrain 目录"),
        (project_root / "brain", "brain 目录"),
        (project_root / ".gbrain" / "config.json", "config.json"),
    ]

    all_ok = True
    for path, name in checks:
        if path.exists():
            print(f"[OK] {name}: {path}")
        else:
            print(f"[WARN] {name} 不存在: {path}")
            if name == ".gbrain 目录":
                all_ok = False

    return all_ok


def check_env_vars():
    """检查环境变量"""
    vars_to_check = [
        ("GBRAIN_HOME", False),
        ("OPENAI_API_KEY", False),
        ("HTTP_PROXY", False),
        ("PATH", True),
    ]

    all_ok = True
    for var_name, required in vars_to_check:
        value = os.environ.get(var_name)
        if value:
            # 隐藏敏感信息
            display = value[:20] + "..." if len(value) > 20 else value
            if var_name in ("OPENAI_API_KEY",):
                display = "***已设置***"
            print(f"[OK] {var_name}={display}")
        elif required:
            print(f"[FAIL] {var_name} 未设置 (必需)")
            all_ok = False
        else:
            print(f"[INFO] {var_name} 未设置 (可选)")

    return all_ok


def main():
    print("=" * 60)
    print("xhs-ingest 环境检测")
    print("=" * 60)
    print()

    results = []

    print("--- Python环境 ---")
    results.append(check_python_version())
    print()

    print("--- Python依赖 ---")
    results.append(check_module("rapidocr"))
    results.append(check_module("openai"))
    results.append(check_module("Pillow", "PIL"))
    print()

    print("--- 外部工具 ---")
    results.append(check_playwright_cli())
    results.append(check_gbrain_cli())
    print()

    print("--- 项目结构 ---")
    results.append(check_project_structure())
    print()

    print("--- 环境变量 ---")
    results.append(check_env_vars())
    print()

    print("=" * 60)
    if all(results):
        print("[OK] 所有检查通过，环境就绪！")
    else:
        print("[WARN] 部分检查未通过，请根据提示修复")
    print("=" * 60)

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
