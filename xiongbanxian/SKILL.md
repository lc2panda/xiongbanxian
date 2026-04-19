---
name: xiongbanxian
description: 熊半仙 · 梅花易数（含小六壬）起卦断卦。支持年月日时起卦、数字起卦、汉字笔画起卦（离线 Unihan，无 API 依赖），以及小六壬起课。自动推演本卦、互卦、变卦、错卦、综卦，判断体用五行生克关系，并按起卦方式自动套用三套皮肤（宋代文人 / 民俗木刻 / 道符掐指）输出 HTML 卡片。**每次调用会自动生成 HTML + 精准裁剪的 2× Retina 长图 PNG**，Claude 可直接把 PNG 文件分享给用户。当用户提到"起卦 / 占卜 / 梅花易数 / 周易 / 小六壬 / 解卦 / 卜一卦 / 看看运势"等时调用本技能。
---

# 熊半仙 · 梅花易数推演

熊半仙是一位精于《梅花易数》与小六壬的数字化占卜师。它依照宋代邵雍《梅花易数》的先天起卦法，接受「**年月日时**」「**数字**」或「**汉字笔画**」输入，自动：

1. 推演 **本卦、互卦、变卦、错卦、综卦**
2. 判定 **体卦/用卦** 以及 **体用五行生克关系**
3. 输出一张 **精美的 HTML 结果卡片**（自包含、自带长图导出）

本技能也内置 **小六壬**（月→日→时 三步起课）。

---

## 何时调用此技能

当用户提到下列任一意图时调用：
- 「起卦 / 算一卦 / 卜一卦 / 占个卦」
- 「梅花易数 / 梅花心易 / 邵雍 / 先天八卦 / 周易占卜」
- 「小六壬 / 大安留连速喜 / 掐指一算」
- 「解卦 / 断卦 / 五行生克」
- 用户给出一个具体问题 + 明确希望用周易/梅花易数推演

调用前先用 **AskUserQuestion** 工具至少确认 1) 起卦方式 与 2) 所问事项，除非用户已说清楚。

---

## 执行流程

所有推演逻辑都由 `scripts/divination.py` 实现，Claude 只需要：

1. **准备输入**（用户的问题、时间、可选数字/汉字）
2. **调用 CLI**（或 import 为库）
3. **生成卡片 HTML** 并放到用户的工作目录（`/sessions/*/mnt/ClaudeWork/`）
4. **给出"view"链接** + 简短断语

### 环境要求（跨平台 · Mac / Windows / Linux）

**必需依赖**：`lunar_python`（公历转农历）。
**可选依赖**：`playwright`（自动长图 PNG）、`strokes`（笔画查询提速）。

| 平台 | 安装命令 |
|---|---|
| **macOS** | `pip3 install lunar_python playwright && playwright install chromium` |
| **Windows** | `pip install lunar_python playwright` 然后 `playwright install chromium` |
| **Linux (系统管理 Python)** | `pip install lunar_python playwright --break-system-packages && playwright install chromium` |
| **Linux (venv/conda)** | 同 Mac，无需 `--break-system-packages` |

> `--break-system-packages` 是 Linux/Mac 上受 PEP 668 保护的系统 Python 才需要的；
> Windows / 虚拟环境里直接 `pip install ...` 即可。

可选：

```bash
pip install strokes       # 笔画提速；未装时自动退化到内嵌 JSON
```

**离线/内嵌资产**：
- `scripts/data/unihan_strokes.json` —— Unicode Unihan `kTotalStrokes`（~870KB，93000+ 字），**不依赖百度 API**。

### 自动长图的降级策略（重要）

自动长图依赖 Playwright + Chromium。**在以下任一情况下会静默跳过长图、仅输出 HTML**：

1. 未安装 `playwright`
2. 未运行 `playwright install chromium`
3. 当前系统（严格沙箱 / 容器 / 杀毒软件 / 公司策略）不允许启动浏览器

跳过时 CLI 会打印诊断信息，但**不会中断主流程** —— HTML 照常生成。
用户可在浏览器里打开 HTML，点右上角「📸 保存为长图」按钮手动导出（基于 modern-screenshot CDN 的浏览器内方案）。

如需预检：

```bash
python3 scripts/screenshot.py --check
```
输出 `[ok] ok` 即当前环境可自动出图；否则打印跳过原因。

### 起卦方式 A：年月日时起卦（最常用 · 皮肤 A 宋代文人）

```bash
cd <SKILL_DIR>/scripts
python3 divination.py \
    --datetime "2026-04-17 14:30" \
    --question "事业发展" \
    --output-html "/sessions/.../mnt/ClaudeWork/熊半仙-事业.html"
```

未指定时间时，使用**当前系统时间**起卦（对应传统"动念起卦"的时刻）。
默认皮肤：`a`（宋代文人雅致 · 宣纸 + 松烟 + 绛色）。

### 起卦方式 B1：数字起卦（皮肤 B 民俗木刻）

```bash
python3 divination.py \
    --numbers "168" \
    --rule "规则1" \
    --question "今日财运" \
    --output-html ".../熊半仙-财运.html"
```

- 规则 1（默认）：3 位数时 上卦=d1%8、下卦=d2%8、动爻=d3%6
- 规则 2：上卦=d1、下卦=d2+d3、动爻=总和
- 可加 `--use-hour` 让动爻再加时辰数

### 起卦方式 B2：汉字笔画起卦（皮肤 B · 无需百度 API）

```bash
python3 divination.py \
    --numbers "梅花易数" \
    --question "学业" \
    --stroke-variant simplified \
    --output-html ".../熊半仙-学业.html"
```

`--stroke-variant`:
- `simplified`（默认）· 按 Unihan 主笔画（对简体用户直觉友好）
- `traditional` · 先把简体字对照到繁体再查笔画（覆盖常用约 260 字，未覆盖字按原字查）
- `kangxi` · 目前与 traditional 等价；Unihan 印刷笔画在大多数场景与康熙字典一致

卡片上会自动显示"字→笔画"可视化条，并标注本次使用的制式。

### 起卦方式 C：小六壬（皮肤 C 道符掐指）

```bash
python3 divination.py \
    --xiaoliuren \
    --datetime "2026-04-17 14:30" \
    --question "何时能见到他" \
    --output-html ".../熊半仙-小六壬.html"
```

### 手动指定皮肤

默认按起卦方式自动匹配（A/B/C）。要强制某一款皮肤用于长图美化时：

```bash
python3 divination.py --numbers "168" --skin a --output-html ...
```

皮肤值：`auto | a | b | c`。

---

## 自动长图（默认开启）

**每次 `--output-html` 都会同步生成一张精准长图 PNG**，Claude 无需任何额外操作。

```bash
# 默认行为：同目录同文件名自动生成 .png
python3 divination.py --numbers "168" --output-html card.html
# → 产出 card.html + card.png
```

参数：
- `--output-png PATH` · 显式指定 PNG 路径
- `--no-png`         · 禁用自动长图（仅输出 HTML）
- `--png-width N`    · 视口宽度（默认 900）
- `--png-scale N`    · 像素倍率（默认 2 = Retina）

自动长图的内部流程（`scripts/screenshot.py`）：
1. Playwright 以 headless Chromium 打开 HTML（`device_scale_factor=2`）
2. Chromium 启动自带 `--no-sandbox --disable-dev-shm-usage` 等参数，兼容 Linux 容器 / WSL / macOS / Windows
3. 注入 JS 展开所有 `<details>`、隐藏导出按钮栏
4. 定位 `#capture-root` 容器，调用 `locator.screenshot()` 一次性出长图
5. 无多余留白、不截断 box-shadow、真实字体 + 真实布局

**三层兜底**：
1. **Python 层**：`ScreenshotUnavailable` 异常被 `divination.py` 捕获，静默降级为只输出 HTML
2. **浏览器层**：卡片 HTML 右上角保留 `📸 保存为长图` 按钮（modern-screenshot CDN），用户可手动导出
3. **系统层**：最次可用 OS 自带截图（macOS `⌘⇧4`、Windows `Win+Shift+S`）或浏览器开发者工具 "Full-size screenshot"

### Claude 使用建议

调用完 CLI 后：
- 若 stderr 显示「长图已保存：...」，`<name>.png` 已就绪 —— **优先**把 PNG 链接发给用户；
- 若 stderr 显示「[长图生成跳过]」，则 PNG 未生成 —— 仅分享 HTML 链接，并提示用户可在浏览器里点右上角按钮手动出图。

```
# 能出图时
[查看长图](computer:///.../熊半仙-事业.png)
[查看完整卡片](computer:///.../熊半仙-事业.html)

# 环境不支持时
[查看完整卡片](computer:///.../熊半仙-事业.html)
（长图可在打开后点击右上角「📸 保存为长图」导出）
```

长图适合发到微信/朋友圈/小红书；HTML 适合在电脑上查看和二次截图。

---

## 算法说明（供解释时引用）

起卦依据为宋代邵雍《梅花易数》，已与多份权威文献交叉核验：

**先天八卦数**：乾 1、兑 2、离 3、震 4、巽 5、坎 6、艮 7、坤 8

**年月日时起卦公式**：
- 上卦 = (年支数 + 农历月 + 农历日) mod 8（余 0 取 8）
- 下卦 = (年支数 + 农历月 + 农历日 + 时支数) mod 8
- 动爻 = (年支数 + 农历月 + 农历日 + 时支数) mod 6（余 0 取 6）
- 年、时均以地支序数（子 1、丑 2 … 亥 12）取

**衍生卦**：
- 互卦：本卦二三四爻为下卦、三四五爻为上卦
- 变卦：动爻翻转阴阳
- 错卦：六爻整体阴阳俱反
- 综卦：六爻整体上下颠倒

**体用判定**：
- 动爻在下卦（初/二/三爻）→ 体卦=上卦、用卦=下卦
- 动爻在上卦（四/五/上爻）→ 体卦=下卦、用卦=上卦

**五行生克**（体 vs 用）：
- 比和（同五行）→ 大吉
- 用生体 → 大吉
- 体克用 → 小吉
- 体生用 → 小凶
- 用克体 → 大凶

---

## 三套皮肤

| 皮肤 | 起卦方式 | 美学锚点 | 主色调 | 字体 | 装饰 |
|---|---|---|---|---|---|
| **A** 宋代文人 | 年月日时 | 宋代学者雅致 | 宣纸 `#FFFAF0` · 绛色 `#C41E3A` · 松烟 `#5A5552` | LXGW WenKai / Noto Serif SC | 云纹 |
| **B** 民俗木刻 | 数字 / 笔画 | 民俗年画 · 笔画木刻 | 米黄宣纸 `#E8D9B0` · 暗朱 `#8B2518` · 古金 `#B8860B` | LXGW WenKai | 古金回纹 · 暗朱双线框 |
| **C** 道符掐指 | 小六壬 | 道教符箓 · 掐指诀 | 素笺 `#D4CDAE` · 松柏墨青 `#2F4F3E` · 褐金 `#8B6F47` | 楷体 / LXGW WenKai | 墨青八卦角章（纯 CSS/SVG） |

> B、C 已调整为**柔和米黄/素笺底色**，告别刺眼红背景，长图上的观感更温润沉稳。
> 所有色板均通过 WCAG AA 对比度校验（正文 ≥ 4.5 : 1）。

---

## 回复风格

1. **先给卡片** → 调用 CLI 生成 HTML → 用「[查看推演卡片](computer://<absolute-path>)」格式给用户直接跳转。
2. **提示用户**：卡片右上角可点「📸 保存为长图」一键导出 PNG。
3. **再给断语**（80–200 字）。断语须包含：
   - 卦名 + 一句象意
   - 体用关系判断 + 吉凶层级
   - 对应"所问事项"的具体建议（2–3 点）
4. **不要**把原始 JSON 或大段文本倒到对话里 —— 卡片里都有。
5. **语气**：半仙风格（沉稳、言简、引古不晦涩），不要过度玄学化、不要迷信暗示。
6. **免责声明**（每次末尾一小行）：`占卜之术仅为决策参考，请以现实判断为据。`

---

## 卡片结构（用户会看到什么）

生成的 HTML 卡片自上而下包括：
- **导出栏**：熊半仙专属长图导出按钮（截图时自动隐身）
- **顶部**：熊半仙标识 + 所问事项 + 阳历/阴历/干支 + 起卦公式
- **笔画条**（仅笔画起卦显示）：字→笔画 可视化 + 制式标注
- **主卦 Hero**：卦名、上下卦、卦意描述、六爻图（动爻高亮）
- **体用区**：体卦 / 用卦 两幅三爻图 + 五行关系 + 吉凶徽章
- **六爻 · 六神 · 六亲**：自上而下表格 + 六神详解
- **六亲发动**：当动爻的六亲名 + 发动详解
- **四卦联动**：互卦、变卦、错卦、综卦 四张小卡
- **卦辞详解**：原文、白话、象意、《断易天机》、邵雍/傅佩荣解、传统解卦、哲学含义
- **万物类象**：上下卦各自的类象
- **底部**：免责提示 + 时间戳

小六壬卡片另有「月课→日课→时课」三步流，以「时课」为终断，并带有四角八卦章装饰。

---

## 常见问答

**Q：用户没给时间怎么办？**
A：使用当前系统时间（`datetime.now()`），相当于"动念之时"。

**Q：用户用汉字起卦（如"事业"二字）？**
A：`--numbers "事业"` 即可，自动走笔画路径（离线 Unihan 查询）。
可加 `--stroke-variant traditional` 使用繁体笔画。

**Q：笔画数与其他工具不一致？**
A：多半是制式差异。梅花易数古籍以繁体笔画为准，现代工具大多按简体。
卡片右上的制式标注帮助判断来源。

**Q：长图按钮点了没反应？**
A：该功能需要联网加载 modern-screenshot CDN。离线环境下请用浏览器自带
的"网页截图"或操作系统截图工具。

**Q：用户问事情"何时应期"？**
A：用 **小六壬**。小六壬天生擅断"何时何事何地"的具体时点。

---

## 输出路径约定

- 卡片文件写到用户的工作目录：`/sessions/*/mnt/ClaudeWork/`
- 文件名建议：`熊半仙-<所问事项>-<YYYYMMDD-HHMM>.html`
- 每次生成一张新卡，不要覆盖历史卡片

---

## 依赖清单

| 包 | 必选 | 用途 | Mac/Windows | Linux（系统 Python） |
|---|---|---|---|---|
| `lunar_python` | ✅ 必需 | 公历转农历 / 干支 | `pip install lunar_python` | `pip install lunar_python --break-system-packages` |
| `playwright` + `chromium` | ⚠️ 可选 | 自动长图 PNG | `pip install playwright` → `playwright install chromium` | `pip install playwright --break-system-packages` → `playwright install chromium` |
| `strokes` | 🔹 可选 | 加速笔画查询 | `pip install strokes` | `pip install strokes --break-system-packages` |
| 标准库 `argparse json re dataclasses datetime html pathlib` | ✅ 自带 | 脚本运行 | — | — |
| `scripts/data/unihan_strokes.json` | ✅ 内嵌 | 离线笔画库（870KB，93000+ 字） | 已打包 | 已打包 |

**无需网络、无 API Key、无百度依赖。**
**自动长图在任何环境下失败都不会中断主流程** —— HTML 照常输出。
