"""
小红书收藏导入进度管理模块 v2

支持Phase级别进度记录：
- Phase 2: 截图（记录total_slides和screenshoted_slides）
- Phase 3: OCR
- Phase 4: Agent视觉描述
- Phase 5: 导入GBrain
- Phase 6: 验证

每个笔记需要重复Phase 2-6。
"""

import json
import os
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录"""
    env_root = os.environ.get('GBRAIN_HOME')
    if env_root:
        return Path(env_root)
    
    try:
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent.parent.parent.parent
        if (project_root / '.gbrain').exists() or (project_root / 'brain').exists():
            return project_root
    except:
        pass
    
    return Path.cwd()


PROJECT_ROOT = get_project_root()
PROGRESS_FILE = PROJECT_ROOT / ".gbrain" / "xhs_progress.json"


def load_progress():
    """加载进度文件"""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_progress(progress):
    """保存进度文件（原子写入）"""
    progress['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    tmp_file = str(PROGRESS_FILE) + '.tmp'
    with open(tmp_file, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=2)
    import shutil
    shutil.move(tmp_file, str(PROGRESS_FILE))


def init_progress(board_id, board_name, total_notes):
    """初始化进度"""
    progress = {
        "board_id": board_id,
        "board_name": board_name,
        "total_notes": total_notes,
        "notes": [],
        "pending_notes": [
            {"index": i, "note_id": None, "status": "pending"}
            for i in range(total_notes)
        ],
        "last_updated": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "chrome_pid": None,
        "cdp_port": 9222
    }
    save_progress(progress)
    return progress


def get_or_create_note(progress, index, note_id=None, title=None, author=None):
    """获取或创建笔记记录"""
    for note in progress['notes']:
        if note['index'] == index:
            if note_id and not note.get('note_id'):
                note['note_id'] = note_id
            if title and not note.get('title'):
                note['title'] = title
            if author and not note.get('author'):
                note['author'] = author
            return note

    # 创建新笔记记录
    new_note = {
        "index": index,
        "note_id": note_id,
        "title": title,
        "author": author,
        "status": "processing",
        "phases": {
            "phase2_screenshot": {"status": "pending"},
            "phase3_ocr": {"status": "pending"},
            "phase4_vision": {"status": "pending"},
            "phase5_import": {"status": "pending"},
            "phase6_verify": {"status": "pending"}
        }
    }
    progress['notes'].append(new_note)

    # 从pending_notes中移除
    progress['pending_notes'] = [
        n for n in progress['pending_notes']
        if n['index'] != index
    ]

    save_progress(progress)
    return new_note


def update_phase(progress, note_index, phase_name, status, **kwargs):
    """更新指定Phase的状态"""
    note = get_or_create_note(progress, note_index)
    if 'phases' not in note:
        note['phases'] = {
            "phase2_screenshot": {"status": "pending"},
            "phase3_ocr": {"status": "pending"},
            "phase4_vision": {"status": "pending"},
            "phase5_import": {"status": "pending"},
            "phase6_verify": {"status": "pending"}
        }

    if phase_name not in note['phases']:
        note['phases'][phase_name] = {}

    note['phases'][phase_name]['status'] = status
    for key, value in kwargs.items():
        note['phases'][phase_name][key] = value

    # 检查是否所有Phase都完成了
    all_completed = all(
        p.get('status') == 'completed'
        for p in note['phases'].values()
    )
    if all_completed:
        note['status'] = 'completed'

    save_progress(progress)


def mark_note_completed(progress, note_index):
    """标记笔记为已完成"""
    note = get_or_create_note(progress, note_index)
    note['status'] = 'completed'
    for phase in note['phases'].values():
        phase['status'] = 'completed'
    save_progress(progress)


def mark_note_processing(progress, note_index, note_id=None, title=None, author=None):
    """标记笔记为处理中"""
    note = get_or_create_note(progress, note_index, note_id, title, author)
    note['status'] = 'processing'
    save_progress(progress)


def mark_note_failed(progress, note_index, reason=""):
    """标记笔记为失败"""
    note = get_or_create_note(progress, note_index)
    note['status'] = 'failed'
    note['fail_reason'] = reason
    save_progress(progress)


def get_next_pending_index(progress=None):
    """获取下一个待处理的笔记索引"""
    if progress is None:
        progress = load_progress()
    if not progress:
        return None

    for note in progress['notes']:
        if note['status'] == 'pending':
            return note['index']

    return None


def get_note_phase_status(progress, note_index):
    """获取指定笔记的Phase状态"""
    for note in progress.get('notes', []):
        if note['index'] == note_index:
            return note.get('phases', {})
    return {}


def get_progress_summary():
    """获取进度摘要"""
    progress = load_progress()
    if not progress:
        return "没有进度记录"

    total = progress['total_notes']
    notes = progress.get('notes', [])
    pending = progress.get('pending_notes', [])

    completed = len([n for n in notes if n['status'] == 'completed'])
    processing = len([n for n in notes if n['status'] == 'processing'])
    failed = len([n for n in notes if n['status'] == 'failed'])
    pending_count = len([n for n in pending if n['status'] == 'pending'])

    summary = f"""
{'='*60}
小红书收藏导入进度
{'='*60}
专辑: {progress['board_name']}
总笔记数: {total}
已完成: {completed}
处理中: {processing}
待处理: {pending_count}
失败: {failed}
{'='*60}
"""

    # 显示每个笔记的Phase状态
    if notes:
        summary += "\n笔记详情:\n"
        for note in sorted(notes, key=lambda x: x['index']):
            status_icon = {
                'completed': '[OK]',
                'processing': '[ING]',
                'failed': '[FAIL]'
            }.get(note['status'], '[PND]')

            summary += f"\n  [{note['index']}] {status_icon} {note.get('title', 'Unknown')}\n"

            phases = note.get('phases', {})
            phase_names = {
                'phase2_screenshot': '截图',
                'phase3_ocr': 'OCR',
                'phase4_vision': '视觉描述',
                'phase5_import': '导入GBrain',
                'phase6_verify': '验证'
            }

            for phase_key, phase_name in phase_names.items():
                phase = phases.get(phase_key, {})
                phase_status = phase.get('status', 'pending')
                icon = {'completed': '[OK]', 'processing': '[ING]', 'pending': '[PND]'}.get(phase_status, '[PND]')

                # Phase 2显示截图进度
                if phase_key == 'phase2_screenshot' and phase_status in ['processing', 'completed']:
                    total_slides = phase.get('total_slides', '?')
                    screenshoted = phase.get('screenshoted_slides', 0)
                    summary += f"    {icon} {phase_name}: {screenshoted}/{total_slides}\n"
                else:
                    summary += f"    {icon} {phase_name}\n"

    next_idx = get_next_pending_index(progress)
    if next_idx is not None:
        summary += f"\n下一个待处理: [{next_idx}]\n"
    else:
        summary += "\n所有笔记已处理完成！\n"

    summary += f"\n最后更新: {progress['last_updated']}\n"
    summary += "="*60 + "\n"

    # 添加断点续传提示
    if next_idx is not None and next_idx > 0:
        summary += "\n[NOTE] 断点续传提示:\n"
        summary += "  如果浏览器被关闭，请:\n"
        summary += "  1. 重新启动Chrome（带CDP）\n"
        summary += "  2. 登录小红书（如果需要）\n"
        summary += "  3. 运行: python scripts/xhs-ingest/xhs_click_note.py\n"
        summary += "  4. 脚本会自动从下一个待处理笔记继续\n"
        summary += "="*60 + "\n"

    return summary


def reset_progress():
    """重置进度（谨慎使用）"""
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
    print("进度已重置")


def print_resume_guide():
    """打印断点续传指南"""
    # 自动检测Chrome路径
    chrome_paths = [
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
        Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "Application" / "chrome.exe",
    ]
    chrome_path = None
    for p in chrome_paths:
        if p.exists():
            chrome_path = p
            break

    chrome_cmd = f'& "{chrome_path}"`' if chrome_path else "& <Chrome路径>`"

    guide = f"""
============================================================
小红书收藏导入 - 断点续传指南
============================================================

如果工作中断（浏览器关闭、电脑重启等），请按以下步骤恢复：

1. 查看当前进度:
   python scripts/xhs-ingest/xhs_progress.py

2. 重新启动Chrome（带CDP）:
   {chrome_cmd}
       --remote-debugging-port=9222 `
       --user-data-dir="$env:LOCALAPPDATA\\Google\\Chrome\\User Data" `
       --profile-directory="Default"

3. 登录小红书（如果需要）

4. 从断点继续:
   python scripts/xhs-ingest/xhs_click_note.py
   （脚本会自动获取下一个待处理笔记）

[!] 注意事项:
   - 进度自动保存，不会丢失
   - 关闭浏览器后登录态会丢失，需要重新登录
   - 重新登录可能触发风控，操作要慢
   - 建议完成一个笔记的所有Phase后再关闭浏览器

============================================================
"""
    print(guide)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--resume":
        print_resume_guide()
    else:
        print(get_progress_summary())
