# xhs-ingest 设计文档

## 1. 设计目标

将小红书收藏夹中的图文笔记导入 GBrain，形成结构化的知识库。

## 2. 核心架构

### 2.1 分层设计

```
┌─────────────────────────────────────┐
│  Layer 3: 业务逻辑层                  │
│  - process_one_note_cli.py           │
│  - 状态机管理、错误恢复、批量调度       │
├─────────────────────────────────────┤
│  Layer 2: 操作封装层                  │
│  - xhs_cli.py                        │
│  - 浏览器操作、页面交互、数据提取       │
├─────────────────────────────────────┤
│  Layer 1: 工具层                      │
│  - xhs_progress.py                   │
│  - xhs_ingest_v2.py                  │
│  - 进度管理、OCR处理、Markdown生成    │
└─────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 禁止行为 |
|------|------|----------|
| xhs_cli.py | 浏览器操作封装 | 不得包含业务逻辑、不得直接操作进度文件 |
| xhs_progress.py | 进度读写 | 不得包含浏览器操作、OCR逻辑 |
| xhs_ingest_v2.py | OCR和Markdown生成 | 不得包含浏览器操作、进度管理 |
| process_one_note_cli.py | 业务流程编排 | 不得直接调用 playwright-cli，必须通过 xhs_cli.py |

## 3. 关键设计决策

### 3.1 路径策略（通用性设计）

**核心原则: 禁止写死任何绝对路径**

#### 项目路径检测
```python
def get_project_root() -> Path:
    """按优先级检测项目根目录"""
    # 1. 环境变量（最高优先级）
    env_root = os.environ.get('GBRAIN_HOME')
    if env_root:
        return Path(env_root)
    
    # 2. 从脚本位置推算
    # scripts/xhs_cli.py -> 向上4级到项目根目录
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent.parent
    if (project_root / '.gbrain').exists() or (project_root / 'brain').exists():
        return project_root
    
    # 3. 当前工作目录（兜底）
    return Path.cwd()
```

#### 工具路径检测
```python
def find_playwright_cli() -> str:
    """检测 playwright-cli 位置"""
    # 1. 直接运行（PATH中）
    # 2. where 命令查找
    # 3. 返回命令名让系统自己找
    return "playwright-cli"  # 必须在 PATH 中
```

**约束:**
- 所有路径必须通过 `get_project_root()` 动态获取
- playwright-cli 必须在系统 PATH 中
- 禁止硬编码任何用户目录（如 `C:\Users\xxx`）

### 3.2 浏览器自动化方案

**选择: playwright-cli (命令行模式)**

理由:
- 与 Trae IDE 集成更好
- 支持状态持久化 (state-save/state-load)
- 避免 Python API 的上下文销毁问题

**约束:**
- 所有浏览器操作必须通过 `xhs_cli.py` 封装
- 禁止使用 Playwright Python API
- 禁止在脚本中直接调用 `page.click()` 等 API

### 3.2 登录状态管理

**流程:**
1. 尝试加载已保存的状态文件 (`xhs_auth.json`)
2. 刷新页面验证登录态
3. 如果失效，提示人工登录
4. 登录成功后保存新状态

**状态文件位置:** `d:\mycode\gbrain\xhs_auth.json`

### 3.3 虚拟滚动处理

**问题:** 小红书专辑页面使用虚拟滚动，只有当前可见笔记在 DOM 中

**解决方案:**
1. 通过 `data-index` 属性定位笔记
2. 智能滚动加载：滚动一屏减去2个卡片高度
3. 边界检测：连续3次无新内容变化则到达边界
4. 滚动后必须重新获取元素坐标

**关键代码模式:**
```python
# 1. 检查当前可见范围
# 2. 计算滚动方向和距离
# 3. 执行滚动
# 4. 等待加载 (2秒)
# 5. 检查新范围
# 6. 重复直到找到目标或到达边界
```

### 3.4 点击交互方案

**选择: 真实鼠标事件 (mousemove + mousedown + mouseup)**

理由:
- JavaScript `click()` 被风控拦截
- 真实鼠标事件模拟用户行为

**约束:**
1. 必须先滚动元素到视口中央
2. 必须重新获取坐标（滚动后坐标会变）
3. 必须验证坐标在视口内 (x>0, y>0, y<window.innerHeight)
4. 执行顺序: mousemove -> sleep(0.5s) -> mousedown -> sleep(0.2s) -> mouseup -> sleep(3s)

### 3.5 输出可见性要求

**强制要求:**
- 每个操作必须有输出（滚动、点击、等待）
- 使用 `flush=True` 确保实时输出
- 禁止使用 Unicode 特殊字符（如 ✅）
- 使用 ASCII 字符表示状态: `[OK]`, `[FAIL]`, `[WARN]`

**输出格式:**
```
[操作类型] 具体描述
  详细状态: 值
  详细状态: 值
```

## 4. 状态机设计

### 4.1 单笔记处理状态机

```
[Start]
  |
  v
[CheckBrowser] --浏览器未打开--> [OpenBrowser] --> [LoadState]
  |                                    |
  |<--浏览器已打开-----------------------|
  v
[CheckLocation]
  |
  +--不在专辑页--> [NavigateToBoard] --> [WaitForLoad]
  |
  +--在专辑页------|
  v
[FindNote] --不在视图--> [Scroll] --> [CheckRange]
  |                           ^
  |<--在视图------------------|
  v
[ScrollToCenter]
  |
  v
[GetCoordinates]
  |
  v
[MouseMove]
  |
  v
[MouseDown] -> [MouseUp]
  |
  v
[CheckPopup]
  |
  +--未打开--> [RetryClick] (最多3次) --> [MarkFailed]
  |
  +--已打开---|
  v
[Screenshot]
  |
  v
[OCR]
  |
  v
[SaveMarkdown]
  |
  v
[ClosePopup]
  |
  v
[SaveState]
  |
  v
[MarkCompleted]
```

### 4.2 错误恢复策略

| 错误类型 | 恢复策略 |
|----------|----------|
| 点击未打开弹窗 | 重试3次，然后标记失败 |
| 笔记不在DOM中 | 滚动查找，最多100次 |
| 坐标不在视口内 | 滚动到中央，重新获取 |
| 浏览器断开 | 重新连接，恢复状态 |
| 登录失效 | 提示人工登录 |
| 截图失败 | 标记失败，继续下一个 |

## 5. 进度管理

### 5.1 进度文件格式

```json
{
  "board_id": "string",
  "board_name": "string",
  "total_notes": 104,
  "notes": [
    {
      "index": 0,
      "note_id": "string",
      "title": "string",
      "author": "string",
      "status": "pending|processing|completed|failed",
      "phases": {
        "phase2_screenshot": {"status": "pending|completed"},
        "phase3_ocr": {"status": "pending|completed"},
        "phase4_vision": {"status": "pending|completed"},
        "phase5_import": {"status": "pending|completed"},
        "phase6_verify": {"status": "pending|completed"}
      }
    }
  ]
}
```

### 5.2 状态定义

| 状态 | 含义 | 可转移至 |
|------|------|----------|
| pending | 待处理 | processing, failed |
| processing | 处理中 | completed, failed |
| completed | 已完成 | - |
| failed | 失败 | pending (重试) |

## 6. 编码规范

### 6.1 字符编码

- 文件编码: UTF-8
- 控制台输出: 通过 `sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')` 修复
- 禁止使用: emoji、特殊Unicode字符

### 6.2 命名规范

- 函数名: snake_case
- 常量: UPPER_CASE
- 类名: PascalCase

### 6.3 输出规范

```python
# 正确
print(f"[OK] 笔记已找到: {note_id}", flush=True)
print(f"  坐标: ({x}, {y})", flush=True)
print(f"  在视口内: {in_viewport}", flush=True)

# 错误
print("✅ 成功")  # 禁止使用emoji
print("处理中...")  # 缺少flush
```

## 7. 测试要求

### 7.1 单元测试

- xhs_cli.py: 每个函数独立测试
- xhs_progress.py: 进度读写测试

### 7.2 集成测试

- 单笔记完整流程测试
- 错误恢复测试
- 登录状态测试

### 7.3 验收标准

- [ ] 能正确处理第一页可见笔记
- [ ] 能正确滚动到指定索引笔记
- [ ] 点击后能打开笔记弹窗
- [ ] 截图包含完整内容
- [ ] OCR能提取文本
- [ ] Markdown正确生成
- [ ] 进度正确更新

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| v1 | 2026-05-03 | 初始设计文档 |
