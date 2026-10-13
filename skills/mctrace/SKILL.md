---
name: mctrace
description: 麦搭子 / McTrace —— 真实调用麦当劳 MCP，把「怎么给你挑的」全程摊开给你看：每一步用了哪个只读工具、抽出了哪些带来源的事实、预算与热量约束过没过，全在回复的文字里。**触发场景**：用户说「麦搭子」「McTrace」，或提到麦当劳点餐/找店/门店/菜单/早餐/晚餐/减脂/控卡/低卡/减肥/热量/预算/蛋白/饱腹，或积分/券/抽奖/积分商城/过期积分。**执行要求**：① 必须调用 MCP 工具（mctrace_launch / mctrace_start / mctrace_scan_*），工具返回的文本就是用户看到的产品正文，直接把它讲给用户，不要另起炉灶重写一遍；② **绝对不要说「界面上」「点按钮」「弹出来」「点一下开始」——这台客户端不会渲染 MCP App 界面，用户只看到纯文本**；③ 用户没说自己在哪里（城市/位置）时，必须先反问，不要用默认值代替；④ 减脂/控卡/低卡场景必须传 goal="fatloss"。核心理念是「工具调用成功 ≠ 用户目标达成」：算价失败诚实降级到菜单标价，营养表未覆盖的餐品不参与推荐。全程只读，绝不调用下单/抽奖/兑换等写操作。
agent_created: true
---

# McTrace —— 让每一次麦当劳 MCP 调用都可被验证

## 这是什么

McTrace 把麦当劳 MCP 的调用过程还原成一条「**有事实、有证据、可回放**」的执行链。

- 普通用户看到的是「会边做边说的助手」；
- 开发者看到的是「对业务结果负责的 MCP 证据分析工具」；
- 两种视角共用**同一份真实事件流**。

> 一句话立场：**工具调用成功 ≠ 用户目标达成。事实是一等公民，拟人化 ≠ 编造思考。**

## 两种形态：界面优先，Studio 兜底

| 形态 | 载体 | 什么时候用 |
| --- | --- | --- |
| **① MCP 应用界面**（首选） | `mctrace-app` MCP 服务器 + `ui://mctrace/live-story` | 用户提需求时**默认用它**：结果直接渲染在对话里，不用跳转、不用打开文件 |
| **② 独立 Studio 回放页**（后备） | `<runtime>/apps/studio/live_story.html` | 宿主不支持界面、用户要深度分析 / 离线查看 / 载入自己的 trace 时 |

两者共用同一套渲染内核（`packages/studio_core.py`），界面长得一样，不会漂移。

### 为什么要有两个
界面依赖宿主支持 **MCP Apps**（SEP-1865，2026-01-26 稳定版）。WorkBuddy 已支持「MCP 应用界面」，
但并非所有入口都开着。所以：

- 工具**一定同时返回可读文本**，不支持界面的宿主（命令行、旧客户端）照样拿到结论；
- App 拿不到数据时显示**诚实降级面板**，并指路独立 Studio；
- App 轮询失败 3 次会停止并提示，不会一直空转；
- App 里的「深度分析」按钮把用户带回 Studio。

**已知未验证项**：界面在真实 WorkBuddy 桌面端是否渲染，尚未在实机确认（只在本项目自带的
模拟宿主里跑通过）。详见 `docs/compatibility.md`。**不要向用户声称"一定能看到界面"**，
如果这次调用只返回了文本结论，就照实说，并给出 Studio 路径。

## 自主工作流（按这个顺序，别跳步）

### 步骤 0 · 确保产品已安装
```bash
python ~/.workbuddy/skills/mctrace/scripts/install.py --check
```
未安装就跑一遍幂等安装：
```bash
python <repo>/skills/mctrace/scripts/install.py
```

### 步骤 1 · 确保两个连接器都注册了
```bash
python ~/.workbuddy/skills/mctrace/scripts/configure_connector.py --check
```
缺谁补谁（缺 mcd-mcp 时需要向用户索取一次 Token）：
```bash
python ~/.workbuddy/skills/mctrace/scripts/configure_connector.py --token-file <Token文件>
python ~/.workbuddy/skills/mctrace/scripts/configure_connector.py --server mctrace   # 只补应用本体
```
脚本幂等、保留其他服务器。**首次写入后需重启 WorkBuddy。**

### 步骤 2 · 必须调用 MCP 工具（这是产品的全部意义）

**⏱️ 别犹豫，一次调用就够。** 不要先探查文件、不要先跑探针、不要反复读 SKILL。

```
第 0 步：用户只是提到「麦搭子」「McTrace」「能干什么」，还没说要什么
   → 调 mctrace_launch（零参数）。它会返回一段「这产品能干什么 + 三个可直接说的例子」，
     你把这段讲给用户，再问一句"你在哪个城市、哪个位置附近？"

第 1 步：用户说了需求
   ├ 没说城市/位置 → 先反问，拿到后再调（工具也会拒绝执行并返回 needsClarification）
   └ 说全了 → 直接调 mctrace_start（或 mctrace_scan_order），一次，带齐参数
```

| 情况 | 调什么 |
|---|---|
| 「我想用麦搭子」「麦搭子能干什么」 | `mctrace_launch` |
| 「帮我在静安寺点个减脂晚餐，40 以内」 | `mctrace_start`（`goal=fatloss`） |
| 「盘点我的积分」 | `mctrace_start`（`scenario=points`） |

### ⛔ 三条硬禁止（违反就是让用户看空气）

1. **禁止说「界面上」「弹出来」「点按钮」「点开始」** —— 这台 WorkBuddy 桌面端**不渲染 MCP App 界面**，
   用户只看得到纯文本。工具返回的文本就是产品本身。
2. **禁止自己写脚本 import mcp_client** —— 绕过工具既没有证据链，也不受自检保护。
3. **禁止编造界面操作** —— 别让用户去点你看不见的东西。
4. **禁止只念页面路径** —— 生成页面后必须用 `present_files` 打开它，让用户直接看到。

### 🌐 每次调用后必须打开页面（重要）

这台客户端不渲染对话内嵌界面，**所以页面要我们生成、自己打开**。
`mctrace_start` / `mctrace_scan_*` 的返回文本最后一行就是页面路径，例如：

```
可交互回放页（双击即开，离线可用，每步都能点开看原始返回）：
C://Users//...//examples//pages//trace-mctrace-20261010-e62db40e.html
```

**拿到这个路径后，立刻用 `present_files` 把它打开**，参数直接给绝对路径。
不要只把路径念给用户 —— 那等于让用户自己去翻文件夹。

页面里有什么：首屏结论卡（门店/推荐/总价/热量/选品规则/备选）+ 10 步过程，
每步都能点工具名看原始请求与返回、点来源路径看字段取自哪里、点实体名看角色。

**不确定就问，不要猜。** 以下任一缺失时，**先反问，不要用默认值代替**：

| 缺什么 | 后果 | 该怎么办 |
|---|---|---|
| **城市 / 位置** | 会找到几百甚至上千公里外的门店 | 必须问，工具也会直接拒绝执行 |
| 「减脂」到底指什么 | 热量低 ≠ 吃得饱 ≠ 想吃主食 | 问一句，或在结果里明说你的理解并给备选 |
| 预算 / 热量上限 | 约束不明确，推荐就是瞎猜 | 问，或明说用了什么假设 |

> 工具已经做了硬拦截：缺 `city`/`keyword` 时它会返回 `needsClarification`，
> **这时正确动作是把问题转述给用户**，不是自己补个默认值继续跑。

| 用户想做的事 | 调用工具 | 参数 |
| --- | --- | --- |
| **只是想了解产品（提到产品名）** | **`mctrace_launch`** | **无（零参数，返回能力说明+示例）** |
| **看过程**：找店 / 点餐推荐 / 对比热量与预算 | `mctrace_start` | `scenario=order`，`city`，`keyword`，`goal`，`budget_yuan`，`max_kcal` |
| **看过程**：盘点积分 / 查过期 / 找沉睡券 | `mctrace_start` | `scenario=points` |
| 只想要结果、不想等过程 | `mctrace_scan_order` / `mctrace_scan_points` | 同上 |
| 取某次追踪的文本结论 | `mctrace_get_summary` | `traceId` |
| 要离线 / 深度查看 | `mctrace_open_studio` | — |

**`goal` 一定要选对，它直接决定推荐结果：**

| 用户说 | `goal` | 选品规则 |
| --- | --- | --- |
| 减脂、控卡、低卡、减肥、晚上吃少点 | **`fatloss`** | 约束内取**热量最低**的正餐单品 |
| 早餐、正餐、吃饱、顶饱 | `satiety` | 约束内取**最顶饱**的单品（能量最高但不超标） |

选错的代价很实在：同一个黄冈万达门店，`satiety` 会给出 391 千卡的板烧鸡腿堡，
`fatloss` 给出 325 千卡的麦香鱼。**减脂场景用 `satiety` 等于没减脂。**

调用后**只需补一句结论**，**不要**再自作主张用 present_files 打开 Studio——界面已经在对话里了。

### ⛔ 步骤 2.5 · 三条硬禁止（违反就是把产品做废了）

1. **禁止自己写脚本绕过 MCP 工具。** 不许 `import mcp_client` / `import pipeline` 直接调麦当劳 MCP，
   不许用 `MCTRACE_OUT` 之类的环境变量自己造 trace.json。
   绕过去的代价是：**用户在对话里只能看到一段文字，看不到可点击的轨迹界面**，
   而且完全不受协议自检保护。这正是本产品要解决的问题，不是绕过它的办法。
2. **禁止硬编码推荐结果。** 推荐哪个组合、说什么理由，必须由 `pipeline.py` 从当次真实
   菜单 + 营养表算出来。早期版本把「板烧鸡腿堡+苹果片+纯悦」写死在脚本里，
   价格 ¥38 却毫无依据 —— 这是伪造演示，不是产品。
3. **禁止声称界面已展示。** 调完工具后如果没看到内嵌界面，就如实说
   「这次界面没渲染出来」，并给出 Studio 路径。不要写成「已为你展示可点击界面」。

### 步骤 3 · 唯一合法的降级条件

**只有当 `mctrace_start` / `mctrace_scan_*` 确实不在当前可用工具列表里**（例如用户还没重启
WorkBuddy、连接器未加载），才允许改跑本地入口：

```bash
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py 静安寺 40 500 上海市   # 场景①
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py --points               # 场景②
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py --all
```

再用 `present_files` 打开 `<runtime>/apps/studio/live_story.html`，并给出同一句结论，
同时**明确告诉用户这是降级路径**（对话里不会有内嵌界面）。

「懒得调工具」「觉得脚本更快」**不是**降级理由。

## 两个内置真实场景（同一套 Trace schema）

| 场景 | 只读链路 | 看点 |
| --- | --- | --- |
| ① 静安寺早餐 · 点餐推荐 | 门店 → 菜单 → 营养 → 券 → 算价 | 热量超标告警 + 算价**诚实降级**（标注来源：菜单标价） |
| ② 积分资产盘点 | 账户 → 抽奖 → 奖品 → 订单 → 满意度奖券 → 积分商城 → 券 / 活动 | 历史已过期积分**资产流失告警** + 最值兑换 |

## 安全边界（必须遵守）

- **全程只读**：只调用 `query-*` / `list-nutrition-foods` / `query-meal-detail` / `calculate-price`。
- **绝不**调用 `create-order` / `draw-lottery` / `mall-create-order` / `auto-bind-coupons`。
- 地址做**门牌脱敏**；**Token 不写入仓库**，只留在本机 `~/.workbuddy/mcp.json` 与 `<runtime>/token.txt`。
- 卸载用 `install.py --uninstall`（移入 `~/.workbuddy/trash/`，不硬删）。

## 事件契约（Trace schema）

| 字段 | 含义 |
| --- | --- |
| `traceId / seq / ts` | 轨迹号 / 序号 / 时间 |
| `kind` | `info` / `warning` / `success` / `error` / `degraded` |
| `title / tool` | 中文标题 / 真实工具名 |
| `facts[]` | `{key, value, source \| sourcePath}` —— 事实一等公民 |
| `entities{}` | `{实体名: 角色}` —— 可点击 |
| `rule` | `{id, pass, deltaKcal \| deltaYuan}` |
| `say{friendly, pro}` | 双视角叙述 |
| `request / response` | 原始调用与返回（证据） |
| `evidenceRef` | `trace://<traceId>/events/<seq>` |

## 参考

- 工具与真实返回结构：`references/tools.md`
- App 服务器：`packages/mcp_app/server.py`；协议自检：`python packages/mcp_app/selftest.py`
- 界面构建：`packages/mcp_app/build_app.py`（App）、`apps/studio/build_studio.py`（Studio）
- 渲染内核：`packages/studio_core.py`
- 详细集成说明：仓库根 `MCP_INTEGRATION.md`
