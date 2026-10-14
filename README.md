# 麦探长 · 麦当劳物价侦探 —— 查遍方圆几公里，哪家便宜、哪家有货，一条条摊开给你看

> 一个**实际可用**的工具：你在 WorkBuddy 里说「查一下静安寺附近麦香鱼哪家便宜」，
> 麦探长就去调麦当劳 MCP 实跑一遭，把巡查过程、价差、可得性、证据全摆出来。
> 查完给你一个能打开的办案页，每个数字都能戳开看它取自哪个接口的哪个字段。
>
> 底层是一套证据链引擎：负责把每次麦当劳 MCP 调用变成可核验的事实——不编、不糊、每条都能戳开看。

<p align="center"><img src="assets/mcdetective-badge.png" width="140" alt="麦探长警徽"/></p>
<p align="center"><b>麦探长</b>（本仓库门面场景）· 麦当劳物价侦探 —— 跑遍方圆几公里的门店，把「哪家便宜、哪家有货」查个底掉，每条线索都可戳开核验。</p>
<p align="center"><b>👉 在线试用（真能跑）：<a href="https://mcdetective.app.workbuddy.host/">https://mcdetective.app.workbuddy.host/</a></b>　|　仓库：<a href="https://github.com/StrawberryTreea/mcdetective">github.com/StrawberryTreea/mcdetective</a>（觉得探长称职，点个 Star ⭐）</p>
<p align="center"><sub>在线试用怎么用：接案台里报一句个案（如「静安寺 麦香鱼」「中关村 精选单人餐三件套」）→ 贴上你的 MCP Token（<a href="https://open.mcd.cn/mcp" target="_blank">免费申请</a>，30 秒）→ 探长<b>实时</b>调麦当劳 MCP 巡查，全程办案直播、每条线索可核验。<b>Token 只用于你这一次请求：不写进页面、不进仓库、不保存；本服务自身不持有任何 Token。</b></sub></p>

> 他不闷头扔结果，而是把「怎么给你挑的」当场演出来——边做边说、会亮红灯、还会老实认怂。
> 查价也好、盘积分也好，每一步都锚在真实麦当劳 MCP 调用上：过程全摊开，能随时戳、能挑刺。

**麦探长是一个实际可用的产品**（以 WorkBuddy Skill 形态交付）：用户用自然语言说一句需求，模型就**自主配置连接器、自主运行、自主把结果呈现出来**。本次参赛只是它的公开亮相与拿奖励的载体。

---

## 看得见的办案过程（真实运行截图 / 动图）

下面是麦探长办北京中关村那宗案子的全过程，全部为**对麦当劳 MCP 的真实只读调用**（案号 `mcdetective-20261013-aafba506`，2026-10-13）。

**办案直播（Live Story 回放，16 条证据逐条长出）**

![办案直播](docs/demo/patrol-play.gif)

**① 接案台 —— 你说一句话，他自己领会**

<img src="docs/screenshots/01-intake.png" alt="接案台" width="820"/>

**② 巡查路线 · 逐店取证 → 线索一 · 价差榜**

<img src="docs/screenshots/02-patrol.png" alt="巡查路线与价差榜" width="820"/>

**③ 线索二 · 餐品可得性（128 款并集，家家都有的只有 39%）**

<img src="docs/screenshots/03-clues.png" alt="餐品可得性" width="820"/>

**④ 结案报告 —— 差价 ¥3，海淀镇最便宜；一条命令可复现**

<img src="docs/screenshots/04-verdict.png" alt="结案报告" width="820"/>

**⑤ 案卷附录 —— 每条证据可展开原始请求与返回**

<img src="docs/screenshots/05-evidence.png" alt="案卷附录" width="820"/>

> 想自己动手：打开 [在线试用](https://mcdetective.app.workbuddy.host/)，在接案台里报个案（比如「静安寺 麦香鱼」「黄冈万达 巨无霸」），或按下方「快速开始」本地跑一次。

---

## 它特别在哪

别家 AI 帮你办事，只给你一个结果；McTrace 把「它怎么办的」全程摊开给你看：

- **边做边播**：查门店、翻菜单、核热量、算价，事件一条条实时「边长」，像看直播而不是等宣判。
- **随手戳**：任意一家店、一份餐、一张券、一个价格，点开就能看它从哪个真实接口来、原始返回长啥样——像发弹幕一样随时验真、挑刺。
- **会认怂**：算价接口没返明细？它直接说「按菜单价给你，不瞎编」；餐品超了你 500 千卡的线？它自己亮红灯跳过。一个不装、老实的搭子，比「可信」俩字招人喜欢。

俏皮腔可以很欢，但每一句都锚在一次真实麦当劳 MCP 调用上，点得开、看得见原始数据——这是它和「编故事的 AI」最不一样的底子。

---

## 它长什么样

一份 McTrace Trace 由一串**事件**组成，每个事件都带：

| 字段 | 含义 |
| --- | --- |
| `title` / `tool` | 这一步在做什么（中文标题 + 真实工具名）|
| `facts[]` | 从返回里抽出的**事实**，每条标注 `sourcePath`（如 `$.data[0].storeName`）|
| `entities{}` | 可点击实体（门店 / 餐品 / 券 / 金额）及其角色 |
| `rule` | 触发的约束校验结果（预算、热量）|
| `say{friendly, pro}` | 同一事实的**双视角叙述**：俏皮版 / 专业版 |
| `request` / `response` | 原始调用与返回（证据，可展开核对）|
| `evidenceRef` | 该事件的证据地址（`trace://…/events/{seq}`）|

`apps/studio/live_story.html` 是一个**离线可回放**的可视化界面：顶部下拉可切换多个真实场景，流式播放事件、点击任意实体或来源路径打开「证据透镜」查看原始 request/response、并在结尾给出结果卡。

**内置两个真实场景**（同一套 Trace schema）：

| # | 场景 | 只读链路 | 看点 |
| --- | --- | --- | --- |
| ① | 静安寺早餐 · 点餐推荐 | 门店 → 菜单 → 营养 → 券 → 算价 | 热量超标 `warning` + 算价**诚实降级** |
| ② | 积分资产盘点（原「麦麦资产管家」） | 账户 → 抽奖 → 奖品 → 订单 → 满意度奖券 → 积分商城 → 券/活动 | 历史已过期积分**资产流失告警** + 最值兑换 |

下面是仓库内一份**真实运行**的 Trace（场景①，静安寺早餐，非模拟）：

```
• [user-request]        先把要求记下来     → 预算 ¥40 / 热量 ≤500kcal / 有券就用
• [query-nearby-stores] 找到具体门店       → 麦当劳上海静安寺餐厅（storeCode 1450002）
• [query-meals]         认真翻了菜单       → 117 个带价单品
• [list-nutrition-foods] 核对候选热量       → 匹配 12 个正餐单体热量
⚠ [detect:rule]         发现约束冲突       → 「培根安格斯厚牛堡」707kcal，超上限 207
• [query-store-coupons] 查看门店券         → 麦旋风任选 / 薯薯任选（本单不适用）
⚠ [calculate-price]     核算价格           → 算价未返回明细 → 诚实降级用菜单标价 ¥23
✓ [summary-composer]    整理好结果与证据    → 推荐「麦香鱼」¥23 / 325kcal · 未下单
```

## 架构

```
MCP Adapter + Trace  →  Event Normalizer  →  Fact & Rule Engine  →  Narrative Engine  →  Live Story UI
   (真实调用捕获)          (事实归一化)          (预算/热量约束)        (俏皮/专业双文案)      (可回放 + 证据透镜)
        │                                                                                      │
        └──────────────────────►  Trace Store (旁路)  ─────────────────────────────────────────┘
                                        │
                              Evidence Explorer · Summary Composer
```

对应到本仓库：

| 蓝图分层 | 代码 |
| --- | --- |
| MCP Adapter + Trace | `packages/core/mcp_client.py` |
| Fact & Rule / Narrative（点餐场景） | `packages/core/pipeline.py` |
| Fact & Rule / Narrative（积分盘点场景） | `packages/core/pipeline_points.py` |
| 旁路探针（原始响应留存） | `packages/core/probe_scenario.py` |
| Live Story UI + Evidence Lens（渲染内核） | `packages/studio_core.py` —— App 与 Studio **共用同一份** |
| | 交付形态②：独立 Studio（后备 / 深度分析） | `apps/studio/live_story.html`（由 `apps/studio/build_studio.py` 生成）|
| 真实 Trace 样本 | `examples/traces/*.json` |
| Pages 落地页 | `docs/index.html` |

> 两种交付形态共用同一份 Trace 结构与渲染内核：
> **MCP App** 走 MCP Apps（SEP-1865）把界面渲染进对话；**独立 Studio** 是自包含 HTML，
> 在宿主不支持界面时兜底，也承担离线查看 / 载入任意 trace / 深度分析的入口。

---

## 快速开始

> 纯 Python 标准库，**无需安装任何依赖**。

### 0. 装进 WorkBuddy（推荐 · 用户只说一句话）

```bash
python skills/mcdetective/scripts/install.py           # 安装 / 升级（幂等，可反复执行）
python skills/mcdetective/scripts/install.py --check   # 查看安装状态
python skills/mcdetective/scripts/install.py --uninstall  # 卸载（移入 ~/.workbuddy/trash/，不硬删）
```

安装器把产品放进两处，互不影响：

| 位置 | 内容 |
| --- | --- |
| `~/.workbuddy/apps/mcdetective/` | **运行时**：`packages/core`（流水线）、`packages/mcp_app`（App 服务器）、`apps/studio`（回放生成器）、`examples/traces`（Trace 产物）、`VERSION` |
| `~/.workbuddy/skills/mcdetective/` | **智能体入口**：`SKILL.md`、`scripts/`、`references/` |
| `~/.workbuddy/mcp.json` | **连接器**：（无）（应用本体，stdio）+ `mcd-mcp`（数据通道，含你的 Token） |

### 2. 本地起办案服务（把在线试用页跑在自己机器上）

办案页 = 静态页面 + 一个薄后端（转发麦当劳 MCP，因为麦当劳 MCP 不允许浏览器跨域直连）。
后端纯标准库、无依赖，Token 从请求里取、当次用完即弃：

```bash
export MCD_TOKEN=<你的 Token>          # 可省略；省略时由访客在页面上贴
python apps/detective/server.py       # 监听 $PORT（默认 8000），打开 http://127.0.0.1:8000
```

页面能力：接案台一句话报案 → 意图自解析（缺城市/餐品会反问，不瞎猜）→ 实时巡查 → 办案直播 → 案卷 + 证据附录。
已有三册归档案卷（`examples/traces/real-detective-*.json`）可在页面上直接调阅，不需要 Token。

### 3. 独立 Studio 回放页（兼容后备 · 深度分析入口）

自包含 HTML，双击即开，**离线可用**，支持场景切换、播放控制、载入任意 `trace.json`：

```bash
python apps/studio/build_studio.py
python ~/.workbuddy/skills/mcdetective/scripts/run_trace.py --all   # 跑真实链路 + 生成回放页
```

### 4. 配置麦当劳 MCP（拿一个 Token）

方式 A（推荐，命令行）：

```bash
python ~/.workbuddy/skills/mcdetective/scripts/configure_connector.py --check
python ~/.workbuddy/skills/mcdetective/scripts/configure_connector.py --token <你的Token>
python ~/.workbuddy/skills/mcdetective/scripts/configure_connector.py --token-file <文件>  # 避免 Token 出现在命令行历史
```

方式 B（图形界面）：WorkBuddy【专家·技能·连接器】→【连接器】→【自定义连接器】→【配置 MCP】，
填入 `mcp-config.example.json` 的内容，把 `Authorization` 换成你自己的 Token（在麦当劳 MCP 控制台申请）。

### 5. 跑一次真实场景 → 生成 Trace（直接的用法）

**场景① 点餐推荐**（静安寺附近、预算 ≤40 元、热量 ≤500kcal、有券就用）

```bash
python packages/core/pipeline.py https://mcp.mcd.cn 静安寺 40 500 上海市
```

**场景② 积分资产盘点**

```bash
python packages/core/pipeline_points.py https://mcp.mcd.cn
```

脚本会串联对应的**只读**工具，输出 `examples/traces/real-jingan-breakfast.json` / `real-points-steward.json`
（固定场景名，重复运行覆盖，不会堆积），并在控制台打印俏皮叙事。

装成本地 Skill 后，推荐直接用入口脚本一次跑完（自动定位运行时目录，无需手动切路径）：

```bash
python ~/.workbuddy/skills/mcdetective/scripts/run_trace.py 静安寺 40 500 上海市  # 场景①
python ~/.workbuddy/skills/mcdetective/scripts/run_trace.py --points              # 场景②
python ~/.workbuddy/skills/mcdetective/scripts/run_trace.py --all                 # 两个都跑
```
Token 请放在环境变量或本地文件读取，**不要写进仓库**。

> Token 读取优先级：环境变量 `MCD_TOKEN` > 环境变量 `MCD_TOKEN_FILE` 指定的文件 > 仓库根 `token.txt`（已 gitignore）。
> `pipeline.py` 把目标 URL 作为命令行参数传入，方便在受限网络环境或沙箱中显式声明目标主机。

### 6. 生成可视化回放页（离线可开）

```bash
python apps/studio/build_studio.py
# 产出 apps/studio/live_story.html 与 docs/index.html（自包含、双击即开）
```

打开 `live_story.html`：点「▶ 播放」流式回放，点任意**实体芯片**或**来源路径**打开证据透镜，
右上角可切换「俏皮 / 专业」双视角，也可「📂 载入」你自己的 trace.json。

---

## 直接看结果

不想跑代码？仓库里已内置两份真实 Trace：

- 打开 `apps/studio/live_story.html`（已内联两个场景，双击即回放），顶部下拉切换。
- Trace 原始文件：`examples/traces/real-jingan-breakfast.json`、`examples/traces/real-points-steward.json`

---

## 设计原则（不是口号，写进了代码）

1. **只叙述已观察到的事实**：不在返回数据之外补全名称（例如不在营养表里的餐品不会被编造热量）。
2. **金额以真实标价为准，算价失败就降级**：`calculate-price` 未返回明细时，显式标注 `priceSource=menu`，而不是假装算价成功。
3. **约束真的会被执行**：预算与热量是硬校验，不满足就发 `warning` 事件。
4. **拟人化 ≠ 编造思考**：俏皮文案只描述已发生的事实（"我翻了菜单"，而不是"我心想这家店老板今天心情不错"）。
5. **全程只读**：本项目只调用查询类工具，**绝不**触发下单 / 抽奖等写操作。

---

## 目录结构

```
mcdetective/
├── README.md                  # 本文件
├── CONTEST_DECLARATION.md     # 参赛声明（官方原文）
├── MCP_INTEGRATION.md         # MCP 工具调用说明
├── mcp-config.example.json    # 脱敏 MCP 配置示例
├── workbuddy.md               # WorkBuddy 开发上下文（联动奖励核验）
├── docs/
│   ├── index.html             # GitHub Pages 落地页（含真实回放）
│   ├── compatibility.md       # 宿主兼容性实测记录（哪些验过、哪些没验）
│   ├── app-preview.html       # App 形态快照（打开即带数据）
│   ├── app-live-demo.html     # 单文件实时演示（模拟宿主 + 界面 + trace，双击即播）
│   └── tool-inventory.json    # 麦当劳 MCP 35 个工具的真实 schema 存档
├── skills/
│   └── mcdetective/
│       ├── SKILL.md           # WorkBuddy Skill 定义（自主工作流）
│       ├── scripts/
│       │   ├── install.py     # 一键安装/升级/卸载（装进 ~/.workbuddy）
│       │   ├── configure_connector.py  # 自主写入 mcd-mcp 连接器
│       │   ├── run_trace.py   # 入口：跑场景 + 生成回放页
│       │   └── runtime.py     # 运行时目录解析（安装布局 / 仓库布局）
│       └── references/tools.md
├── packages/core/             # 纯标准库实现
│   ├── mcp_client.py          # MCP 客户端 + Trace 捕获
│   ├── pipeline.py            # 场景① 点餐：事实/规则/叙事流水线
│   ├── pipeline_points.py     # 场景② 积分资产盘点：事实/规则/叙事流水线
│   ├── probe_scenario.py      # 只读联调探针
│   └── probe_tools.py         # tools/list 探测：存档服务端真实工具与 schema
├── packages/studio_core.py    # 界面渲染内核（App 与 Studio 共用，样式 + 卡片 + 证据透镜）
│   ├── build_app.py           # 生成可嵌入对话的界面 HTML / 单文件实时演示页
│   ├── selftest.py            # 协议自检（44 项断言，可离线）
│   ├── tests/host_sim.html    # 模拟 MCP Apps 宿主（验证「边跑边长」）
│   └── assets/live_story_app.html
├── apps/studio/               # 独立 Studio（兼容后备 + 深度分析）
│   ├── build_studio.py
│   └── live_story.html
└── examples/traces/           # 真实 Trace 样本（点餐 + 积分盘点）
```

---

## 免责声明

本项目为**麦当劳程序员节创意开发大赛**参赛作品，由参赛者独立开发，**非麦当劳官方产品**。
输出仅供参考，不构成医疗 / 营养或其他专业建议；餐品信息、价格及供应状态以**麦当劳官方渠道的实时结果为准**。
