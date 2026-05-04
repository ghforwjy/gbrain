#!/usr/bin/env python3
"""
小红书收藏笔记 -> GBrain 自动化导入 Skill v3

核心升级（v3）：
1. 三层内容架构：OCR文字 + Vision LLM描述 + 原始图片
2. 智能图片分类：纯文字 / 示意图+文字混搭 / 纯示意图 / 照片
3. 针对示意图的专用Vision提示词（描述组件关系、数据流向、层级结构）
4. 本地图片存储（brain/sources/xhs/images/）+ markdown相对路径引用
5. OCR文字 + Vision描述智能合并（去重+互补）

图文混搭处理策略：
- 纯文字图：OCR提取文字，保留层级结构
- 示意图+文字：OCR提取文字标签 + Vision LLM描述图的结构关系 + 保留原始图片
- 纯示意图：Vision LLM描述 + 保留原始图片
- 照片：Vision LLM描述 + 保留原始图片
"""

import json
import re
import os
import sys
import base64
import shutil
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

from rapidocr import RapidOCR


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
BRAIN_DIR = PROJECT_ROOT / "brain"
XHS_DIR = BRAIN_DIR / "sources" / "xhs"
XHS_IMG_DIR = XHS_DIR / "images"
XHS_DIR.mkdir(parents=True, exist_ok=True)
XHS_IMG_DIR.mkdir(parents=True, exist_ok=True)

PROXY = os.getenv("HTTP_PROXY") or os.getenv("http_proxy") or "http://127.0.0.1:7897"

UI_KEYWORDS = [
    "业务合作", "发现", "直播", "编辑专辑", "发布",
    "粉丝", "通知", "系统规范", "一片荒地", "说点什么",
    "更多", "三更多", "这是一片荒地点击评论", "nc_n_webp",
    "X书", "关注", "点赞", "收藏", "评论", "分享",
    "规范", "回到顶部", "小红薯", "小红书",
]

HEADING_WORDS = [
    "核心问题", "技术创新", "实现思路", "场景", "快速上手",
    "整体来说", "借鉴", "方案", "架构", "流程", "对比",
    "总结", "概述", "介绍", "原理", "设计", "步骤",
    "实现", "关键", "亮点", "优势", "注意",
]


def find_gbrain_cli() -> str:
    """自动检测gbrain CLI的可用调用方式

    搜索顺序:
    1. 直接运行 gbrain（PATH中）
    2. 使用 bun run 运行全局安装的 gbrain
    3. 查找 bun 全局安装目录中的 gbrain 入口文件
    4. 使用 npx gbrain
    返回: 可用的命令前缀
    """
    # 1. 检查 gbrain 是否在 PATH 中
    try:
        result = subprocess.run(
            "gbrain --version", shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return "gbrain"
    except:
        pass

    # 2. 检查 bun 全局安装的 gbrain (通过 bun run)
    try:
        result = subprocess.run(
            "bun run gbrain --version", shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return "bun run gbrain"
    except:
        pass

    # 3. 查找 bun 全局安装目录中的 gbrain 入口文件
    bun_global_paths = []
    try:
        result = subprocess.run(
            "bun pm bin -g", shell=True, capture_output=True, text=True,
            timeout=5, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            bin_dir = result.stdout.strip().strip()
            if bin_dir:
                bun_global_paths.append(Path(bin_dir).parent.parent)
    except:
        pass

    # 默认 bun 全局路径
    bun_global_paths.append(Path(os.environ.get("USERPROFILE", "")) / ".bun" / "install" / "global")
    bun_global_paths.append(Path(os.environ.get("HOME", "")) / ".bun" / "install" / "global")

    for base_path in bun_global_paths:
        if not base_path.exists():
            continue
        # 查找 gbrain 入口文件
        candidates = [
            base_path / "node_modules" / "gbrain" / "src" / "cli.ts",
            base_path / "node_modules" / "gbrain" / "dist" / "cli.js",
            base_path / "node_modules" / "gbrain" / "bin" / "cli.js",
        ]
        for candidate in candidates:
            if candidate.exists():
                return f'bun run "{candidate}"'

    # 4. 尝试 npx
    try:
        result = subprocess.run(
            "npx gbrain --version", shell=True, capture_output=True, text=True,
            timeout=10, encoding="utf-8", errors="replace"
        )
        if result.returncode == 0:
            return "npx gbrain"
    except:
        pass

    # 兜底：返回 gbrain 让系统自己找
    return "gbrain"


# 全局缓存 gbrain CLI 路径
_GBRAIN_CLI_CMD = None


def get_gbrain_cli() -> str:
    """获取 gbrain CLI 命令（带缓存）"""
    global _GBRAIN_CLI_CMD
    if _GBRAIN_CLI_CMD is None:
        _GBRAIN_CLI_CMD = find_gbrain_cli()
    return _GBRAIN_CLI_CMD


def run_cmd(cmd, cwd=None):
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        cwd=cwd or str(PROJECT_ROOT)
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def run_gbrain(args):
    """运行 gbrain 命令，自动检测可用的调用方式"""
    cli = get_gbrain_cli()
    env_prefix = f'$env:GBRAIN_HOME="{PROJECT_ROOT}"; '
    cmd = f'{env_prefix}{cli} {args}'
    return run_cmd(cmd)


def is_heading(text, box, all_boxes):
    if len(text) > 40 or len(text) < 3:
        return False
    for hw in HEADING_WORDS:
        if hw in text:
            return True
    try:
        if all_boxes is not None and len(all_boxes) > 0:
            avg_h = sum(b[3] - b[1] for b in all_boxes) / len(all_boxes)
            h = box[3] - box[1]
            if h > avg_h * 1.5:
                return True
    except Exception:
        pass
    return False


def download_image(url, save_path):
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.xiaohongshu.com/",
            "Origin": "https://www.xiaohongshu.com",
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                save_path.write_bytes(data)
                return True
        except Exception:
            pass
        proxy_handler = urllib.request.ProxyHandler({"http": PROXY, "https": PROXY})
        opener = urllib.request.build_opener(proxy_handler)
        with opener.open(req, timeout=30) as resp:
            data = resp.read()
            save_path.write_bytes(data)
            return True
    except Exception as e:
        print(f"    CDN下载失败: {e}")
        return False


def copy_screenshot_as_image(screenshot_path, save_path):
    try:
        shutil.copy2(str(screenshot_path), str(save_path))
        return True
    except Exception as e:
        print(f"    截图复制失败: {e}")
        return False


def ocr_with_structure(image_path):
    ocr_engine = RapidOCR()
    result = ocr_engine(str(image_path))
    if result is None:
        return []
    items = []
    boxes = result.boxes if hasattr(result, "boxes") else []
    txts = result.txts if hasattr(result, "txts") else []
    for i, (box, text) in enumerate(zip(boxes, txts)):
        if not text or not text.strip():
            continue
        text = text.strip()
        item_type = "heading" if is_heading(text, box, boxes) else "paragraph"
        items.append({"type": item_type, "text": text, "box": box})
    return items


def clean_ocr_items(items):
    cleaned = []
    for item in items:
        text = item["text"]
        if len(text) < 5:
            continue
        is_ui = False
        for kw in UI_KEYWORDS:
            if kw in text:
                is_ui = True
                break
        if is_ui:
            continue
        cleaned.append(item)
    return cleaned


def items_to_markdown(items):
    lines = []
    for item in items:
        text = item["text"]
        if item["type"] == "heading":
            lines.append(f"\n### {text}\n")
        else:
            lines.append(text)
    return "\n".join(lines)


def classify_slide(ocr_items, image_path=None):
    """
    智能判断图片类型：
    - text_only: 纯文字（文字多，布局规整）
    - diagram_with_text: 示意图+文字混搭（有文字标签，但文字量不大）
    - diagram_only: 纯示意图（几乎没有文字）
    - photo: 照片（文字极少，可能有人物/场景描述）
    """
    text_count = len(ocr_items)
    text_chars = sum(len(item["text"]) for item in ocr_items)

    if text_chars < 20:
        return "diagram_only"

    if text_chars < 80:
        return "diagram_with_text"

    if text_chars > 400:
        has_structure = any(item["type"] == "heading" for item in ocr_items)
        if has_structure and text_chars < 800:
            return "diagram_with_text"
        return "text_only"

    return "diagram_with_text"


def vision_describe_image(image_path, note_title="", slide_type="diagram_with_text"):
    """
    用 Vision LLM 描述图片内容。
    根据图片类型使用不同的提示词策略。
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None

    try:
        import openai
        client = openai.OpenAI(
            api_key=api_key,
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )

        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")

        if slide_type == "diagram_with_text" or slide_type == "diagram_only":
            prompt = f"""这是一张小红书笔记中的图片，标题是「{note_title}」。这是一张示意图/架构图/流程图。

请详细分析这张图片，按以下结构输出：

1. **图的结构描述**：这是什么类型的图（架构图/流程图/对比图/思维导图/时序图等）？整体布局是怎样的？

2. **组件与关系**：图中有哪些关键组件/模块/节点？它们之间的关系是什么（箭头、连线、层级、包含等）？请列出所有可见的组件名称和连接关系。

3. **数据/流程走向**：如果有箭头或流程，描述数据/信息的流向。

4. **关键标签文字**：提取图中所有文字标签（包括小字注释），按区域/位置分组列出。

5. **核心信息**：这张图想要传达的核心观点或信息是什么？

请用中文回答，尽量详细，不要遗漏任何组件或关系。"""

        elif slide_type == "photo":
            prompt = f"""这是一张小红书笔记中的照片，标题是「{note_title}」。

请描述这张照片的内容：
1. 画面主体是什么？
2. 有哪些关键细节？
3. 照片传达的信息或氛围是什么？

请用中文回答。"""

        else:
            prompt = f"""这是一张小红书笔记中的图片，标题是「{note_title}」。

请详细描述这张图片的内容，特别是：
1. 如果是示意图/架构图/流程图，描述图中的组件和它们之间的关系
2. 如果是文字为主的图，提取所有文字
3. 如果是照片，描述照片内容

请用中文回答。"""

        response = client.chat.completions.create(
            model=os.getenv("VISION_MODEL", "gpt-4o"),
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{img_data}"}
                        }
                    ]
                }
            ],
            max_tokens=2000
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  Vision LLM 出错: {e}")
        return None


def merge_ocr_and_vision(ocr_text, vision_desc, slide_type):
    """
    智能合并 OCR 文字和 Vision 描述。
    策略：
    - text_only: 主要用OCR，Vision补充
    - diagram_with_text: OCR提取文字标签，Vision描述结构关系，两者互补
    - diagram_only: 主要用Vision，OCR补充文字标签
    - photo: 主要用Vision
    """
    if not vision_desc and not ocr_text:
        return "（无法提取内容）"

    if not vision_desc:
        return ocr_text

    if not ocr_text:
        return f"**【图片描述】**\n\n{vision_desc}"

    if slide_type == "text_only":
        return f"{ocr_text}\n\n**【AI补充描述】**：{vision_desc}"

    if slide_type == "diagram_with_text":
        return (
            f"**【文字标签（OCR）】**\n\n{ocr_text}\n\n"
            f"**【图片结构描述（AI视觉）】**\n\n{vision_desc}"
        )

    if slide_type == "diagram_only":
        return (
            f"**【图片结构描述（AI视觉）】**\n\n{vision_desc}\n\n"
            f"**【文字标签（OCR）】**\n\n{ocr_text}"
        )

    return f"**【图片描述】**\n\n{vision_desc}\n\n**【文字内容】**\n\n{ocr_text}"


def process_slide(slide_num, total_slides, screenshot_path, note_title, note_id):
    """
    处理单张图片，返回结构化内容。
    三层内容：
    1. OCR 文字（保留层级）
    2. Vision LLM 描述（根据图片类型使用不同提示词）
    3. 本地图片文件 + markdown引用

    注意：不使用CDN下载，因为小红书图片有防盗链（403）。
    截图是可靠的图片源。
    """
    slide_label = f"{slide_num}/{total_slides}"
    print(f"\n  处理第 {slide_label} 张...")

    ocr_items = ocr_with_structure(screenshot_path)
    cleaned_items = clean_ocr_items(ocr_items)
    ocr_text = items_to_markdown(cleaned_items) if cleaned_items else ""
    print(f"    OCR: {len(ocr_items)} -> 清理后 {len(cleaned_items)} 个文本块, {len(ocr_text)} 字符")

    slide_type = classify_slide(cleaned_items, screenshot_path)
    type_label = {
        "text_only": "纯文字",
        "diagram_with_text": "图文混搭",
        "diagram_only": "纯示意图",
        "photo": "照片",
    }.get(slide_type, "图文混搭")
    print(f"    类型: {type_label}")

    # 只用截图作为图片源（CDN下载不了）
    img_filename = f"{note_id}_slide{slide_num}.png"
    local_img_path = None

    if screenshot_path and Path(screenshot_path).exists():
        local_img_path = XHS_IMG_DIR / img_filename
        if copy_screenshot_as_image(screenshot_path, local_img_path):
            print(f"    图片来源: 截图复制")
        else:
            local_img_path = None

    vision_desc = None
    if slide_type in ("diagram_with_text", "diagram_only", "photo"):
        vision_desc = vision_describe_image(
            screenshot_path, note_title, slide_type
        )
        if vision_desc:
            print(f"    Vision 描述: {len(vision_desc)} 字符")
        else:
            print(f"    Vision 描述: 不可用（需要OPENAI_API_KEY）")

    merged_content = merge_ocr_and_vision(ocr_text, vision_desc, slide_type)

    return {
        "slide_num": slide_num,
        "slide_label": slide_label,
        "slide_type": slide_type,
        "type_label": type_label,
        "ocr_text": ocr_text,
        "vision_desc": vision_desc,
        "merged_content": merged_content,
        "local_img": str(local_img_path) if local_img_path else None,
        "img_filename": img_filename,
    }


def generate_gbrain_markdown(note_id, title, author, slides_data, like_count=0, collect_count=0):
    date_str = datetime.now().strftime("%Y-%m-%d")
    slug = "xhs-" + note_id

    md_content = f"""---
title: "{title}"
slug: sources/xhs/{slug}
type: source
created: {date_str}
updated: {date_str}
tags: ["xhs", "xhs-collection"]
xhs_note_id: "{note_id}"
xhs_author: "{author}"
xhs_type: "图文笔记"
xhs_slides: "{len(slides_data)}张图"
---

## Summary

{title}

## Content

"""

    for slide in slides_data:
        label = slide["slide_label"]
        type_label = slide["type_label"]
        merged_content = slide["merged_content"]
        local_img = slide["local_img"]
        img_filename = slide["img_filename"]

        md_content += f"### 第{label}张\n\n"
        md_content += f"> 类型: {type_label}\n\n"
        md_content += merged_content + "\n\n"

        if local_img:
            md_content += f"![第{label}张图](images/{img_filename})\n\n"

        md_content += "---\n\n"

    md_content += f"""## Meta

- 作者: {author}
- 点赞: {like_count} | 收藏: {collect_count}
- 笔记类型: 图文（共{len(slides_data)}张）
- 原文链接: https://www.xiaohongshu.com/explore/{note_id}

<!-- timeline -->

## {date_str}

- 收藏此笔记 [Source: 小红书收藏]

"""
    return md_content, slug


def import_to_gbrain(md_file):
    print("\n导入 GBrain...")
    stdout, stderr, rc = run_gbrain(f'import "{BRAIN_DIR}" --no-embed')
    print(stdout)
    if rc != 0:
        print(f"错误: {stderr}")
    return rc == 0


def verify_import(slug):
    print("\n验证导入...")
    stdout, stderr, rc = run_gbrain(f'query "{slug}"')
    if rc == 0 and stdout:
        print(f"验证成功: 找到页面 {slug}")
        return True
    else:
        print(f"验证失败: {stderr}")
        return False


def process_note(note_id, title, author, total_slides, screenshot_dir=None):
    """
    处理一个小红书笔记的完整流程。
    截图是唯一的图片源（CDN下载不了）。
    """
    print("=" * 80)
    print(f"处理笔记: {title}")
    print(f"笔记ID: {note_id}")
    print(f"作者: {author}")
    print(f"总页数: {total_slides}")
    print("=" * 80)

    if screenshot_dir:
        screenshot_path = Path(screenshot_dir)
    else:
        screenshot_path = PROJECT_ROOT / ".playwright-cli"

    screenshots = sorted(screenshot_path.glob("page-*.png"))
    print(f"\n找到 {len(screenshots)} 个截图文件")

    if len(screenshots) == 0:
        print("错误: 没有找到截图文件！请先用 playwright-cli 截图。")
        return None

    slides_data = []
    for i, screenshot in enumerate(screenshots[:total_slides]):
        slide_info = process_slide(
            slide_num=i + 1,
            total_slides=total_slides,
            screenshot_path=screenshot,
            note_title=title,
            note_id=note_id,
        )
        slides_data.append(slide_info)

    md_content, slug = generate_gbrain_markdown(
        note_id=note_id,
        title=title,
        author=author,
        slides_data=slides_data,
    )

    md_file = XHS_DIR / f"{slug}.md"
    md_file.write_text(md_content, encoding="utf-8")
    print(f"\nMarkdown 已保存到: {md_file}")

    img_count = sum(1 for s in slides_data if s["local_img"])
    print(f"图片文件: {img_count} 张已保存到 {XHS_IMG_DIR}")

    return md_file, slug, slides_data


def main():
    print("=" * 80)
    print("小红书收藏笔记 -> GBrain 自动化导入 v3")
    print("支持：OCR + Vision LLM + 图片下载 + 三层内容架构")
    print("=" * 80)

    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        note_id = "69e95785000000002300755c"
        title = "GBrain：AI智能体知识记忆系统"
        author = "LLM- insights"
        total_slides = 8

        result = process_note(
            note_id=note_id,
            title=title,
            author=author,
            total_slides=total_slides,
        )

        if result:
            md_file, slug, slides_data = result
            print("\n" + "=" * 80)
            print("处理完成！")
            print(f"Markdown: {md_file}")
            print(f"图片目录: {XHS_IMG_DIR}")
            for s in slides_data:
                print(f"  第{s['slide_label']}张: {s['type_label']} | OCR:{len(s['ocr_text'])}字 | Vision:{'有' if s['vision_desc'] else '无'} | 图片:{'有' if s['local_img'] else '无'}")
            print("=" * 80)
    elif len(sys.argv) > 1 and sys.argv[1] == "--note":
        # 从进度文件读取指定笔记信息并处理
        # 用法: python xhs_ingest_v2.py --note <note_index>
        try:
            note_index = int(sys.argv[2])
        except (IndexError, ValueError):
            print("错误: 请指定笔记索引，例如: python xhs_ingest_v2.py --note 1")
            sys.exit(1)

        # 导入进度模块
        script_dir = Path(__file__).parent
        sys.path.insert(0, str(script_dir))
        from xhs_progress import load_progress, update_phase

        progress = load_progress()
        if not progress:
            print("错误: 没有找到进度文件，请先运行收藏夹点击脚本")
            sys.exit(1)

        # 查找笔记信息
        note_info = None
        for note in progress.get('notes', []):
            if note['index'] == note_index:
                note_info = note
                break

        if not note_info:
            print(f"错误: 没有找到索引为 {note_index} 的笔记")
            sys.exit(1)

        note_id = note_info.get('note_id')
        title = note_info.get('title', 'Unknown')
        author = note_info.get('author', 'Unknown')
        phase2 = note_info.get('phases', {}).get('phase2_screenshot', {})
        total_slides = phase2.get('total_slides', 1)
        screenshot_dir = phase2.get('screenshot_dir', '.playwright-cli')

        if not note_id:
            print(f"错误: 笔记 {note_index} 没有note_id")
            sys.exit(1)

        # 更新Phase 3为processing
        update_phase(progress, note_index, 'phase3_ocr', 'processing')

        result = process_note(
            note_id=note_id,
            title=title,
            author=author,
            total_slides=total_slides,
            screenshot_dir=screenshot_dir,
        )

        if result:
            md_file, slug, slides_data = result
            # 更新Phase 3为completed
            update_phase(progress, note_index, 'phase3_ocr', 'completed',
                        ocr_text_file=f"sources/xhs/{slug}.md",
                        slides_processed=len(slides_data))
            print("\n" + "=" * 80)
            print(f"笔记 [{note_index}] Phase 3 OCR处理完成！")
            print(f"Markdown: {md_file}")
            print(f"图片目录: {XHS_IMG_DIR}")
            for s in slides_data:
                print(f"  第{s['slide_label']}张: {s['type_label']} | OCR:{len(s['ocr_text'])}字 | Vision:{'有' if s['vision_desc'] else '无'} | 图片:{'有' if s['local_img'] else '无'}")
            print("=" * 80)
            print(f"\n下一步: Phase 4 Agent视觉描述")
            print(f"  请检查OCR结果，然后运行 vision描述 脚本")
        else:
            update_phase(progress, note_index, 'phase3_ocr', 'failed',
                        fail_reason="OCR处理失败")
            print(f"\n笔记 [{note_index}] Phase 3 OCR处理失败！")
    else:
        print("\n用法:")
        print("  python xhs_ingest_v2.py --test          # 用测试数据运行")
        print("  python xhs_ingest_v2.py --note <index>  # 处理指定索引的笔记")
        print("\n或从其他脚本调用 process_note() 函数")


if __name__ == "__main__":
    main()
