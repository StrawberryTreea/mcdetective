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

## 交付形态：办案页是唯一看得见的产物

**这台 WorkBuddy 桌面端不渲染 MCP App 界面**（已在实机确认）。所以产品的可见形态只有一个：
**生成办案页并用 `present_files` 打开它**。只给文字 = 用户什么都没拿到。

| 形态 | 载体 | 说明 |
| --- | --- | --- |
| **① 办案页（唯一门面）** | `<runtime>/apps/detective/detective.html` | 麦探长办案现场：接案台 + 归档案卷 + 三条线索 + 结案报告 + 证据附录。自包含，双击即开、离线可用 |
| **② 深度回放台** | `<runtime>/apps/studio/live_story.html` | 多场景切换、逐步播放、任意 trace 载入，供深度分析 |
| ③ MCP 工具（可选加速） | `mctrace_start` / `mctrace_scan_*` | 拿文本结论用；**即使调用成功，也照样要 `present_files` 打开办案页** |

两个页面共用同一套 Trace 契约与渲染内核（`packages/studio_core.py` / `apps/detective/case_render.py`），外观与数据一致。

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

### 步骤 2 · 出结果：直接跑，不要问（这是产品的全部意义）

**⏱️ 用户说「用一下麦搭子/麦探长」「麦搭子能干什么」时，不要反问、不要介绍自己——
直接跑一宗默认案子，把办案页打开给他看。** 一次调用 ≈ 10 秒。

```bash
# 零参数 = 默认案子（黄冈万达 / 麦香鱼 / 方圆 3km / 最多 10 店）
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py

# 用户给了地点或餐品：城市 区域 目标餐品（半径与店数走默认）
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py 上海市 静安寺 麦香鱼

# 其他场景
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py --points        # 积分资产盘点
python ~/.workbuddy/skills/mctrace/scripts/run_trace.py --order 静安寺 40 500 上海市
```

跑完 **立刻用 `present_files` 打开**：

```
<runtime>/apps/detective/detective.html
```

然后补**一句话**结论（门店/差价/结论/案号），例如：
「黄冈万达方圆 3 公里 2 家店巡查完：麦香鱼各店同价 ¥22，无从比起——办案页已打开，点「案卷附录」看 10 条原始证据。」

### ⛔ 五条硬禁止

1. **禁止只给文字不给页面。** 本机不渲染内嵌界面，不 `present_files` 等于什么都没交付。
2. **禁止把路径念给用户而不打开。** 那等于让用户自己去翻文件夹。
3. **禁止说「界面上」「弹出来了」「点按钮」。** 你看不到界面，就别说界面；页面已经打开了。
4. **禁止绕过 MCP 工具自己造数据。** 不许 `import mcp_client` 自行调麦当劳 MCP、不许手写
   trace.json。取数只能走 `run_trace.py` / `pipeline*.py`（它们内部走官方 MCP 客户端，原始
   请求返回都在证据附录里）。绕过 = 没有证据链，正是本产品要消灭的东西。
5. **禁止硬编码推荐或编造数字。** 结论必须来自当次真实调用；菜单上没有的餐品不许出现在结果里；
   用户没点菜名时**不许替他决定吃什么**（问「什么好吃」→ 只报在售概览，不选菜）。

### 步骤 3 · 什么时候才允许反问（最多一轮）

**先给结果，再问一句**，不要连环追问：

| 情况 | 正确动作 |
|---|---|
| 用户只说产品名，没说地点 | 跑默认案子出页面 → 结论末尾问一句「你在哪个城市？我重跑一宗」 |
| 用户说了地点但没说餐品 | 跑该地点的**在售概览**（不替他选）→ 问「想比哪一款？」 |
| 用户说了「什么好吃」 | **不替他选**：报在售款数 / 覆盖面 / 价格区间，然后问「想比哪一款？」 |
| 工具返回 `needsClarification` | 把工具要的那一项转述给用户，只问这一项 |

**绝不允许**：先问三四个参数才动手；让用户描述「想看哪个 demo」；用户说「随便看看」却反问要城市。

### 步骤 4 · MCP 工具可用时（可选加速，不改变交付方式）

若当前工具列表里确实有 `mctrace_start` / `mctrace_scan_*`，可以用它们拿文本结论，**但交付方式不变**：
照样跑办案页生成器、照样 `present_files` 打开。工具不可用时（连接器未加载 / 未重启）直接走步骤 2，
这不是「降级」，是这台机器的正常路径。

## 三个内置真实场景（同一套 Trace schema）

| 场景 | 入口 | 只读链路 | 看点 |
| --- | --- | --- | --- |
| **③ 麦探长跨店巡查（门面，默认）** | `run_trace.py [城市 区域 餐品]` | 门店 → 逐店菜单 → 逐店券 → 跨店比对 → 结案 | 半径制选店 + **同一形态分组比价**（不把单品/套餐混成假差价）+ 时段不在售时给替代案 + 在售概览模式（用户没点菜名时**不替他选**） |
| ① 静安寺早餐 · 点餐推荐 | `run_trace.py --order 静安寺 40 500 上海市` | 门店 → 菜单 → 营养 → 券 → 算价 | 热量超标告警 + 算价**诚实降级**（标注来源：菜单标价） |
| ② 积分资产盘点 | `run_trace.py --points` | 账户 → 抽奖 → 奖品 → 订单 → 满意度奖券 → 积分商城 → 券 / 活动 | 历史已过期积分**资产流失告警** + 最值兑换 |

办案页自带三册**真实归档案卷**（北京中关村 ¥1 价差 / 上海静安寺 时段替代案 / 黄冈万达 各店同价），
用户没贴 Token 也能先看东西。

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
- 办案页生成：`apps/detective/build_detective.py`；部署组装（必须用它，别手工拷文件）：
  `apps/detective/scripts/prep_deploy.py`
- 渲染内核：`packages/studio_core.py`（回放台）、`apps/detective/case_render.py`（办案页，归档与实时共用）
- 入口脚本：`scripts/run_trace.py`（零参数=默认案子）、`scripts/runtime.py`（运行时目录解析）
- 详细集成说明：仓库根 `MCP_INTEGRATION.md`
