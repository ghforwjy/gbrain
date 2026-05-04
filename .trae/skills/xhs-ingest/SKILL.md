---
name: xhs-ingest
version: 14.0.0
description: |
  将小红书收藏夹中的图文笔记导入 GBrain。
  核心方案：通过 playwright-cli 控制浏览器，复用登录态，避免风控。
  截图是唯一的图片源（CDN有防盗链，下载不了）。
  三层内容架构：OCR文字 + Agent视觉描述 + 原始截图。

  **人类行为模拟**：已优化操作延迟、鼠标轨迹、滚动行为、按键输入，降低被检测为AI的风险。

  **Agent操作极其简单**：只有一个入口脚本 `xhs_ingest.py`，6个模式搞定一切。
triggers:
  - "导入小红书收藏"
  - "抓取小红书笔记"
  - "xhs 收藏导入"
  - "小红书图文导入 brain"
  - "小红书示意图管理"
  - "小红书收藏整理"
  - "继续梳理小红书笔记"
tools:
  - search
  - query
  - get_page
  - put_page
  - file_upload
mutating: true
writes_pages: true
writes_to:
  - sources/xhs/
  - sources/xhs/images/
---

# 小红书收藏导入 Skill v13 - 极简版

## Agent操作流程（只看这一节就够了）

### 核心原则

**只有一个入口脚本**：`.trae/skills/xhs-ingest/scripts/xhs_ingest.py`

**6个模式**，处理一个笔记的完整流程：

```
# 方式1：搜索模式（推荐，最快）
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode search "笔记标题"
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode screenshot
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode process
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode close

# 方式2：翻页模式（不需要知道标题）
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode auto
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode screenshot
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode process
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode close
```

### 模式说明

| 模式 | 作用 | 什么时候用 |
|------|------|-----------|
| `auto` | 自动打开下一个待处理笔记（翻页查找） | 不知道标题，按顺序处理 |
| `search "标题"` | 搜索指定标题并打开 | **知道标题，优先用这个，最快** |
| `screenshot` | 对当前打开的笔记截图 | 笔记弹窗已打开后 |
| `process` | OCR识别 + 生成Markdown | 截图完成后 |
| `close` | 关闭弹窗，回到收藏夹 | 处理完一个笔记后 |
| `status` | 查看当前进度 | 随时查看 |

### 处理一个笔记的完整步骤

**Step 1: 查看进度（可选）**
```powershell
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode status
```

**Step 2: 打开笔记（二选一）**
```powershell
# 方式A：搜索模式（如果你知道标题）
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode search "笔记标题关键词"

# 方式B：翻页模式（自动找下一个）
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode auto
```

**Step 3: 截图**
```powershell
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode screenshot
```

**Step 4: OCR处理**
```powershell
python .trae/skills/xhs-ingest/scripts/xhs_ingest.py --mode process
```

**Step 5: 导入GBrain（重要！）**
```powershell
# 设置环境变量
$env:GBRAIN_HOME = "d:\mycode\gbrain"

# 导入已处理的笔记到brain
# 注意：需要先设置GBRAIN_HOME环境变量
bun run "C:\Users\wangjunyu\.bun\install\global\node_modules\gbrain\src\cli.ts" import brain --no-embed
```

**Step 6: 关闭弹窗，继续下一个**
```powershell
python .trae/skills/xhs-ingest/scripts\xhs_ingest.py --mode close
```

**循环**：重复 Step 2-6，直到所有笔记处理完成。

---

## 依赖要求

### 必需工具

| 工具 | 用途 | 安装方式 |
|------|------|----------|
| playwright-cli | 浏览器自动化 | `npm install -g @anthropic-ai/playwright-cli` |
| Python 3.8+ | 脚本运行 | 系统安装 |
| rapidocr | OCR文字识别 | `pip install rapidocr` |

### 环境变量

```powershell
# 设置一次，永久生效
[Environment]::SetEnvironmentVariable("GBRAIN_HOME", "d:\mycode\gbrain", "User")
$env:GBRAIN_HOME = "d:\mycode\gbrain"
```

---

## 登录状态管理

**自动化处理，Agent无需关心细节**：

1. 脚本自动检查 `xhs_auth.json` 是否存在
2. 存在则加载登录态，刷新页面验证
3. 失效则暂停，提示用户扫码登录
4. 登录成功后自动保存新状态

**手动保存（备用）**：
```powershell
playwright-cli state-save d:\mycode\gbrain\xhs_auth.json
```

---

## 文件输出

- Markdown: `brain/sources/xhs/xhs-{note_id}.md`
- 图片: `brain/sources/xhs/images/{note_id}_slide{N}.png`

---

## 踩坑记录

| 踩坑 | 后果 | 正确做法 |
|------|------|----------|
| 频繁快速操作 | 被识别为脚本 | 脚本已内置随机延迟，不要手动加速 |
| 直接访问笔记URL | IP被封 | 必须从收藏夹或搜索点击卡片进入弹框 |
| 笔记显示"暂时无法浏览" | 可能被风控 | 跳过该笔记，记录链接 |
| 弹窗未打开 | 截图失败 | 检查浏览器是否可见，重新运行auto/search |

---

## 旧脚本说明（不要直接用）

以下脚本已被 `xhs_ingest.py` 整合，**Agent不要直接调用**：

- `xhs_auto_cli.py` -> 用 `xhs_ingest.py --mode auto`
- `search_and_open_note.py` -> 用 `xhs_ingest.py --mode search`
- `screenshot_slides_cli.py` -> 用 `xhs_ingest.py --mode screenshot`
- `process_one_note_cli.py` -> 用 `xhs_ingest.py --mode process`
- `close_and_go_cli.py` -> 用 `xhs_ingest.py --mode close`
- `xhs_progress.py` -> 用 `xhs_ingest.py --mode status`
