# 小红书防风控改造文档

> 本文档记录 2026-05-04 的防风控改造内容，涉及的核心模块为 `xhs_cli.py` 和 `xhs_ingest.py`。

---

## 一、改造背景

小红书反爬系统 2025 年已从"IP+UA"升级为**"浏览器指纹+行为特征"双重校验**。原有代码虽然做了随机延迟、贝塞尔曲线鼠标轨迹等行为模拟，但在**浏览器指纹层面**几乎没有防护，导致被识别为 AI 自动化工具。

### 原始检测问题诊断

通过分析 `playwright-cli` 的实际工作机制（底层通过 CDP 控制 Chromium），逐条确认了以下检测问题的真实存在性：

| # | 检测问题 | playwright-cli 实际情况 | 严重程度 |
|---|---------|----------------------|---------|
| 1 | `navigator.webdriver = true` | Playwright 管理的浏览器确实会设置 | 🔴 致命 |
| 2 | CDP 泄漏 | playwright-cli 通过 WebSocket 通信，端口不暴露，风险较低 | 🟡 中等 |
| 3 | `__pwInitScripts` 注入 | Playwright 注入的全局变量，可被 JS 检测 | 🔴 致命 |
| 4 | WebGL 指纹 | 默认用 Playwright 自带 Chromium，渲染器为 SwiftShader/ANGLE | 🔴 致命 |
| 5 | Canvas 指纹 | 自带 Chromium 的 Canvas 渲染与真实 Chrome 不同 | 🟠 严重 |
| 6 | TLS 指纹 | 自带 Chromium 的 JA3/JA4 指纹异常 | 🟠 严重 |
| 7 | `eval(atob())` 调用 | 代码中大量使用 JS eval 执行 base64 编码脚本 | 🟠 严重 |
| 8 | `querySelector` 追踪 | 频繁用 JS 查询 DOM，正常用户不会这样做 | 🟡 中等 |
| 9 | 输入事件链不完整 | 直接设 `input.value`，缺少完整键盘事件 | 🟠 严重 |
| 10 | 视口尺寸异常 | Playwright 默认 1280×720 | 🟡 中等 |
| 11 | Chrome for Testing UA | 默认用 playwright 自带 Chromium | 🟠 严重 |
| 12 | 行为时序模式 | 只浏览收藏夹、只看不互动 | 🟡 中等 |
| 13 | 鼠标轨迹破绽 | 起始点在目标附近随机偏移，不自然 | 🟡 中等 |
| 14 | 滚动行为规律 | 间隔太均匀，缺少阅读停顿 | 🟡 中等 |
| 15 | 截图操作可检测 | 可能触发 visibility change | 🟢 低 |

**核心发现**：最大的问题是 `playwright-cli open` 默认启动的是 **Playwright 自带的 Chromium**，而非用户安装的 Chrome。只要改用 `--browser=chrome`，就能一次性解决 #4、#5、#6、#11 四个致命/严重问题。

---

## 二、改造方案

### 改造1：使用用户安装的 Chrome（解决 #4 #5 #6 #11）

**文件**: `scripts/xhs_cli.py`

**修改位置**: `open_browser()` 函数

**改动内容**:
```python
# 改动前
cmd = f"open {url}"

# 改动后
cmd = f"open {url}"
cmd += " --browser=chrome"  # 启动用户安装的 Chrome
```

**效果**:
- WebGL 渲染器变为真实显卡（NVIDIA/AMD）
- Canvas 渲染与正常浏览器一致
- TLS 指纹为标准 Chrome 指纹
- User-Agent 为真实 Chrome 而非 Chrome for Testing

**回退机制**: 如果 `--browser=chrome` 失败，自动回退到默认 Chromium。

---

### 改造2：注入反检测 JS 脚本（解决 #1 #3）

**文件**: `scripts/xhs_cli.py`

**新增函数**: `inject_anti_detection()`

**覆盖的检测点**:

| 检测点 | 覆盖方式 |
|-------|---------|
| `navigator.webdriver` | 定义 getter 返回 `undefined` |
| `__pwInitScripts` / `__playwright` 等 | `delete window[key]` 删除 |
| `chrome.runtime` 异常 | 重新构造正常的 runtime 对象 |
| `Permissions API` 异常 | hook `navigator.permissions.query`，修正 notification 状态 |
| `navigator.plugins` 为空 | 模拟真实插件列表（Chrome PDF Plugin 等） |
| `navigator.languages` 异常 | 覆盖为 `['zh-CN', 'zh', 'en-US', 'en']` |
| `iframe contentWindow` 检测 | hook `HTMLIFrameElement.prototype.contentWindow` |
| `Function.prototype.toString` 检测 | 维护 fakedFunctions Map 返回 native code 字符串 |

**调用时机**:
1. `setup_session()` - 浏览器会话建立后
2. `goto()` - 页面导航后（页面刷新后注入会失效）

---

### 改造3：完整键盘事件链输入（解决 #7 #9）

**文件**: `scripts/xhs_cli.py`（`search_note_in_board()`）和 `scripts/xhs_ingest.py`（`search_note_by_title()`）

**改动内容**:

1. **清空输入框**：改用 `Ctrl+A` 全选 + `Backspace` 删除，替代直接 `input.value = ''`
2. **逐字输入**：使用 `playwright-cli type` 命令逐字输入，触发完整键盘事件链（`keydown` → `keypress` → `beforeinput` → `input` → `keyup`）
3. **打字速度随机化**：50-300ms 每字（而非固定值）
4. **停顿思考**：3% 概率额外停顿 0.5-1.5 秒
5. **打错删除**：1% 概率打错一个字符再删除

```python
# 清空：Ctrl+A + Backspace
run_cli("press Control+a", timeout=2)
run_cli("press Backspace", timeout=2)

# 逐字输入
for char in title:
    run_cli(f'type "{char}"', timeout=2)
    delay = random.uniform(0.08, 0.3)  # 打字速度随机
    if random.random() < 0.03:  # 3%概率停顿思考
        delay += random.uniform(0.5, 1.5)
    time.sleep(delay)
```

---

### 改造4：优化鼠标轨迹算法（解决 #13）

**文件**: `scripts/xhs_cli.py`

**修改位置**: `mousemove()` 函数

**改进点**:

| 改进项 | 原来 | 现在 |
|-------|-----|------|
| 起始位置 | 目标附近随机偏移 `x ± 100` | 从上次位置开始（维护 `_last_mouse_pos`） |
| 移动步数 | 固定 10 步 | 根据距离动态：<200px 8-12步，>500px 18-25步 |
| 轨迹曲线 | 贝塞尔但控制点偏移过大 | 中间控制点偏移量限制在距离的 30% 以内 |
| 移动速度 | 各步延迟固定 20-80ms | 加速-减速模型：前期快、中期最快、后期慢 |
| 手部震颤 | 5px 抖动 | 1-3px 微小抖动 |

**物理模型**:
```python
# ease-in-out 加速-减速
if linear_t < 0.5:
    t = 2 * linear_t * linear_t  # 加速阶段
else:
    t = 1 - (-2 * linear_t + 2) ** 2 / 2  # 减速阶段
```

---

### 改造5：优化滚动行为（解决 #14）

**文件**: `scripts/xhs_cli.py`

**修改位置**: `scroll_by()` 函数

**改进点**:

1. **命令替代**：使用 `mousewheel` 命令替代 `window.scrollBy()`，触发真实的 wheel 事件
2. **分段时间滚动**：分 3-5 次小滚动，每次添加 ±10% 随机抖动，模拟惯性
3. **阅读停顿**：15% 概率停顿 1-4 秒，模拟人类浏览时停下来看内容
4. **减速模型**：前几次滚动快，最后一次慢

```python
# 分3-5段滚动
num_chunks = random.randint(3, 5)
for i in range(num_chunks):
    jitter = int(scroll_amount * random.uniform(-0.1, 0.1))
    run_cli(f"mousewheel 0 {scroll_amount + jitter}", timeout=5)

# 15%概率阅读停顿
if random.random() < 0.15:
    time.sleep(random.uniform(1.0, 4.0))
```

---

### 改造6：随机互动行为（解决 #12）

**文件**: `scripts/xhs_cli.py`

**新增函数**: `random_browse_behavior()`

**模拟的行为类型**:

| 行为 | 概率 | 说明 |
|-----|------|-----|
| `mousemove` | 25% | 随机移动鼠标到页面某位置 |
| `small_scroll` | 25% | 小幅度滚动 ±50-200px |
| `hover_note` | 25% | 在笔记卡片上悬停 1-3 秒 |
| `idle` | 25% | 发呆停顿 2-5 秒 |

**调用位置**:
- `collect_all_notes_from_board()` - 每次翻页后调用
- `click_note_by_index()` - 每 3 次滚动尝试后调用
- `auto_open_next_note()` - 导航到收藏夹后调用

---

### 改造7：自然视口尺寸（解决 #10）

**文件**: `scripts/xhs_cli.py`

**修改位置**: `setup_session()` 函数，在反检测注入后设置

```python
natural_viewports = [
    (1920, 1080), (1366, 768), (1536, 864),
    (1440, 900), (1280, 900), (1600, 900)
]
viewport = random.choice(natural_viewports)
resize(viewport[0], viewport[1])
```

---

### 改造8：页面导航后自动重新注入

**文件**: `scripts/xhs_cli.py`

**修改位置**: `goto()` 函数

页面导航（`window.location` 变化）后，JavaScript 上下文会重置，之前注入的反检测脚本会失效。修改后的 `goto()` 在导航成功后自动重新调用 `inject_anti_detection()`。

---

## 三、修改文件清单

| 文件 | 修改类型 | 主要改动 |
|-----|---------|---------|
| `scripts/xhs_cli.py` | 大量重构 | `open_browser`、`inject_anti_detection`、`mousemove`、`scroll_by`、`search_note_in_board`、`goto`、`setup_session` |
| `scripts/xhs_ingest.py` | 部分修改 | `search_note_by_title` 输入方式、`random_browse_behavior` 调用 |

---

## 四、验证方法

### 语法验证
```bash
python -c "import py_compile; py_compile.compile('scripts/xhs_cli.py', doraise=True)"
python -c "import py_compile; py_compile.compile('scripts/xhs_ingest.py', doraise=True)"
```

### 导入验证
```bash
cd scripts
python -c "import xhs_cli; print('OK')"
```

### 运行时验证（建议）
在浏览器控制台执行以下检测，验证改造效果：

```javascript
// 1. 检查 navigator.webdriver
console.log('webdriver:', navigator.webdriver);  // 应为 undefined

// 2. 检查 Playwright 注入变量
console.log('__playwright:', window.__playwright);  // 应为 undefined
console.log('__pwInitScripts:', window.__pwInitScripts);  // 应为 undefined

// 3. 检查插件列表
console.log('plugins length:', navigator.plugins.length);  // 应 > 0

// 4. 检查 languages
console.log('languages:', navigator.languages);  // 应包含 zh-CN

// 5. 检查 Permissions API
navigator.permissions.query({name: 'notifications'}).then(r => {
    console.log('notifications permission:', r.state);  // 应与 Notification.permission 一致
});
```

---

## 五、已知局限

1. **TLS 指纹**：playwright-cli 底层的 TLS 握手特征无法通过 JS 修改，仍然可能与真实 Chrome 有差异
2. **CDP 连接检测**：高级反爬可能检测 CDP WebSocket 连接的存在，但小红书目前未发现此类检测
3. **WebGL 深度修改**：当前通过用户 Chrome 已大幅改善，但 WebGL 指纹伪装需要更底层的 GPU 参数修改
4. **行为模式**：虽然增加了随机互动，但整体只浏览收藏夹的行为模式仍然单一，建议偶尔穿插首页推荐浏览
