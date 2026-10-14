# 麦当劳 MCP 大赛调研与参赛方向构思

> 调研时间：2026-10-13 17:00–18:30（榜单快照时间：2026-10-13 17:00:40）
> 数据来源：官方活动仓库 RANKING.md / README.md、M-China/mcd-mcp-server 工具清单、掘金参赛复盘文
> 状态标注：本文所有数字均可回溯到上述来源；无法证实的已标 UNVERIFIED

---

## 一、这是一场什么比赛

**麦当劳程序员创意开发大赛**（官方英文名 M-China McDonald's Developer Innovation Challenge），
麦当劳中国 GitHub 官方账号 M-China 主办，WorkBuddy 为官方合作伙伴。

| 项 | 内容 |
|---|---|
| 赛制 | 基于麦当劳 MCP 开发一个 Skill，推到**公开 GitHub 仓库**，官方仓库 Issue 报名，**按 Star 数排名** |
| 活动开始 | 2026-10-09 10:30（北京时间） |
| 报名 + 排名截止 | **2026-10-25 23:59** |
| 定榜 | 2026-10-26 00:00 采集的数据为最终排名 |
| 获奖信息提交截止 | 2026-11-14 |
| 奖励发放 | 提交收货信息后约 2 周 |

**奖励结构**：

| 档位 | 条件 | 奖励 |
|---|---|---|
| 第 1 名 | 排名第 1 | 巨无霸 50 次免费兑换券 + WorkBuddy 10240 积分 |
| 第 2 名 | 排名第 2 | 巨无霸 30 次兑换券 + 10240 积分 |
| 第 3 名 | 排名第 3 | 巨无霸 20 次兑换券 + 10240 积分 |
| 进榜即得 | Star > 0 且进前 100 | 汉堡回车键玩具 ×1 + 程序员节实体徽章 ×1 |
| WorkBuddy 专项 | 进榜 + 真实使用 WorkBuddy + 提交 workbuddy.md + 前 100 | WorkBuddy 3000 积分 |

**报名硬性要求**（README.md 原文口径）：

1. 仓库必须包含：`README.md`、`CONTEST_DECLARATION.md`（内容一字不可改）、`MCP_INTEGRATION.md`、源代码、`workbuddy.md`（选填，但 WorkBuddy 专项必须）
2. 仓库为 Public，**创建时间须在 2025-12-25 00:00 ～ 2026-10-25 23:59 之间**
3. 官方仓库按模板发报名 Issue（标题与正文之间暂不要用换行符；项目地址不要用 Markdown 格式）
4. 排行榜只展示前 100；第 100 名有并列则全部展示
5. ⚠️ 严禁提交真实 Token，配置只允许环境变量占位符

**麦当劳 MCP 能力面**（35 个工具，官方 mcd-mcp-server 仓库 2026-09-10 v1.0.9）：

- 点餐域：`query-nearby-stores` / `query-meals` / `query-meal-detail` / `calculate-price` / `create-order` / `cancel-order` / `query-order` / `order-list`
- 优惠券域（**四路**）：`query-store-coupons`（门店券）/ `available-coupons`（麦麦省可领）/ `query-my-coupons`（我的券）/ `auto-bind-coupons`（一键领券）
- 营养域：`list-nutrition-foods`（能量/蛋白质/脂肪/碳水/钠/钙）
- 外送域：`delivery-query-addresses` / `delivery-query-stores` / `delivery-create-address`
- 积分/商城域：`query-my-account` / `mall-points-products` / `mall-product-detail` / `mall-create-order` / `mall-order-list` / `mall-order-detail`
- 抽奖域：`query-lottery-info` / `draw-lottery` / `query-my-prizes`
- 派对域：`query-party-city` / `query-party-store` / `query-partystore-date` / `query-partystore-session` / `party-order-create`
- 其他：`campaign-calendar`（活动日历）/ `now-time-info` / `query-meal-assistance`（团餐助餐）
- 限流：每 Token 每分钟 600 次请求（429）

---

## 二、当前战况（2026-10-13 17:00 榜单快照）

榜单共展示 118 个项目（前 100 + 并列）。关键数字：

| 位次 | 项目 | Star |
|---:|---|---:|
| 1 | mcd-coupon-strategist | 256 |
| 2 | mcd-party-officer | 208 |
| 3 | mccarbon | 206 |
| 4 | mcd-budget-meal | 142 |
| 5 | mcd-hui-life | 111 |
| 6 | mcd-saver-strategist | 106 |
| … | … | … |
| 100 名门槛 | （约第 97 位并列组） | **6** |

**结论：进前 100 的 Star 门槛只有 6；前三名需要 200+。**

**赛道拥挤度盘点**（按项目名归类，同一开发者多个仓库已合并计）：

| 赛道 | 项目数（约） | 头部 Star | 头部项目 |
|---|---:|---:|---|
| 省钱 / 优惠券 | 9 | 256 | mcd-coupon-strategist |
| 派对 / 团餐 / 聚会 | 6 | 208 | mcd-party-officer |
| 趣味 / 人格 / 玄学（MBTI、运势、盲盒、心情） | 10 | 37 | mcd-mbti |
| 热量 / 减脂 / 营养 | 8 | 37 | mcd-order-calories |
| 积分 / 券 / 资产盘点 | 8 | 33 | maimen-certification |
| 活动 / 资讯雷达 | 4 | 73 | mcd-event-radar |
| 语音 / 通用助手 | 3 | 15 | mcd-voice-order-assistant |
| 其他单点（地图、宠物、宝宝餐、wrapped、git 燃料、终端、小票、now） | 12 | 78 | mcd-git |
| **过程可信 / 证据链 / 可观测性** | **0** | — | **空白** |

（项目名归类为人工判读，个别项目可能横跨两类；Star 数以 10-13 17:00 快照为准。）

---

## 三、我们自己的位置（必须先说清的三件事）

1. **尚未报名。** 官方仓库 Issues 检索 `mcdetective` 无结果，RANKING.md 无本项目（截至 2026-10-13 18:30）。若已在别处报名，以实际为准——**待人工确认**。
2. **仓库材料不齐。** 本地 `mcdetective/` 目录目前只有 `CONTEST_DECLARATION.md`、`README.md`、`skills/mcdetective/SKILL.md`；报名必须的 `MCP_INTEGRATION.md`、`mcp-config.example.json`、**源代码**（packages/ apps/ examples/ 等，完整资产在 `~/.workbuddy/apps/mcdetective/`）、`workbuddy.md` 均未进仓库。
3. **时间只剩 12 天**（今天 10-13，截止 10-25 23:59）。报名材料齐备 + 至少 1 个 Star 即可保底拿周边，门槛很低；但 Star 增长需要传播动作，越早开始越好。

另有一个**安全隐患**：`~/.workbuddy/apps/mcdetective/token.txt` 持有真实 MCP Token，整理仓库进 GitHub 前必须确认 .gitignore 覆盖它，并全局搜一遍无 Token 字符串再推送。

---

## 四、五个参赛方向构思

评判维度：**机制具体度**（落到调哪些工具、算什么、验什么）、**榜单差异化**（避开 118 个存量项目）、**Star 传播逻辑**（这个比赛按 Star 排名，传播力和技术力同样重要）、**资产复用度**（现成的 trace / Studio / App / 双视角叙事能直接用多少）。

### 方向 1 · 「麦麦不装」——AI 点单直播间（麦探长 正统方向）

**一句话**：所有项目都在回答「买什么」，只有它在回答「凭什么信它」。

**核心机制**：
- 用户说「黄冈万达附近，减脂晚餐，500 大卡以内」→ 事件流一条条实时长出：定位门店 → 翻菜单（117 个带价单品）→ 匹配营养表（12 个正餐单体）→ 热量规则硬校验（麦香鱼 325 kcal 通过 / 培根安格斯 707 kcal 亮红灯跳过）→ 查券 → 算价 → 结果卡
- 每个事件可戳开三层证据：原始 request/response、字段来源路径（如 `$.data[0].storeName`）、实体角色
- 诚实设计写进代码：`calculate-price` 未返明细时显式标注 `priceSource=menu`（诚实降级，不假装算价成功）；不在营养表里的餐品不编热量
- 双视角叙事：俏皮版给用户，专业版给开发者，同一份事实流

**榜单差异化**：过程可信赛道 0 个存量项目；MCP 可观测性是当下技术社区热点。

**Star 逻辑**：「AI 装傻/编造检测」有争议性和话题性；直播间形态 demo 独特。风险：偏 geek，大众向传播弱于省钱类。

**资产复用度**：最高。Trace schema、pipeline、Studio、MCP App 全部现成，只差仓库整理和 README 打磨。

### 方向 2 · 「省钱打假局」——每一分省钱都要有证据

**一句话**：省钱赛道已被 256 Star 证明是最大流量口，但所有省钱项目都只给结论不给证据——把最热的赛道和唯一的空白焊在一起。

**核心机制**：
- 取数四路查全：`available-coupons`（麦麦省可领）+ `query-my-coupons`（我的券）+ `query-store-coupons`（门店券）+ `auto-bind-coupons` 后再查一遍新增；少查一路用户就少省钱
- 确定性优化器（纯标准库、零依赖、可复现）在「菜单 × 券」空间带剪枝穷举，输出总价最低 Top-N 方案；核心逻辑带 13 项自测断言，离线可跑
- **证据链**：每个「省了 ¥25.10」都能戳开——券从哪个工具来、原价取哪个字段、叠加规则引用；保守策略：`stackable:false` 一律互斥，方案价 ≤ 用户实付价，下单前 `calculate-price` 核价闭环
- 「打假模式」彩蛋：同一需求分别演示「无证据链的通用 AI」与「本 Skill」，展示编造 vs 可核验的对照——天然传播素材

**榜单差异化**：省钱赛道最挤（coupon-strategist / saver-strategist / save-master / best-deal / saving-assistant / budget-* 等 9 个），但「省钱 + 可验证」无人做。

**Star 逻辑**：省钱数字本身有传播力（「巨无霸套餐 47 → 21.9」式截图）；「AI 数字可信度」是争议钩子。

**风险**：需要投入优化器开发（中等工作量）；与方向 1 不冲突——是方向 1 的一个场景插件。

### 方向 3 · 「人机点单王」——同样的钱，你敢跟 AI 比划吗

**一句话**：把点单变成一档节目：用户点一单，AI 点一单，MCP 统一核价，多维裁决。

**核心机制**：
- 开局给定约束（预算 / 热量上限 / 口味标签），用户先点、AI 后点（AI 决策过程用 trace 直播，把方向 1 的证据链变成「对战实况」）
- `calculate-price` 双单统一核价；裁决维度：价格（低者胜）、热量（按目标函数贴近度）、满足感（口味标签匹配度 + 用户自评）
- 战绩天梯本地留存，「AI 胜率」可晒；裁决规则全部公开可查（每一维怎么算的写在 README）

**榜单差异化**：0 个游戏化 / 对战类项目。趣味类（MBTI、运势）有玩法但无对抗交互。

**Star 逻辑**：游戏化最易破圈；「我赢了/输了 AI」是社交货币；demo 视频天然有节目效果。

**风险**：交互开发量中高（规则引擎 + 界面，但 Studio/App 资产可复用）；「实用价值」需要靠「点单决策训练」叙事补足。

### 方向 4 · 「麦麦热量审计署」——你这周吃了多少钠，敢看吗

**一句话**：榜单上 8 个热量类项目全是「这一次吃什么」的单点查询；没有人在时间维度上做审计。

**核心机制**：
- `order-list` 拉近 90 天历史订单 → `query-meals` / `query-meal-detail` 匹配餐品编码 → `list-nutrition-foods` 取营养 → 个人营养档案
- 周报：热量 / 钠 / 蛋白质 / 脂肪趋势 vs 参考摄入量（参考值来源必须标注），超标项红灯，如「本周钠摄入约为推荐量的 187%」
- 点单时实时联动审计：「这单吃完，本周钠将再超 22%」——历史 × 当下的闭环
- 诚实边界：餐品匹配失败（历史订单中的已下架餐品）如实标注匹配率，不猜；显式声明不构成医疗建议

**榜单差异化**：calorie 类存量 8 个全部单点；「历史订单 × 营养 × 审计」叙事空白。

**Star 逻辑**：健康焦虑是永恒传播话题；周报截图友好；「审计」有冲击力。

**风险**：健康合规边界要小心（只做数据呈现，不做医疗断言）；历史订单匹配有噪声，必须诚实标注；隐私敏感度略高（只读订单 + 地址脱敏，已有处理经验）。

### 方向 5 · 「麦门 MCP 公开课」——3 分钟看懂 AI 怎么帮你点餐

**一句话**：大多数参赛项目只用了 16 个 MCP 工具；用一次真实点餐 trace 当教材，把 35 个工具的能力面演一遍。

**核心机制**：
- 一次真实点单的完整 trace 当教材：10 步事件，每步三层展开——「发生了什么」（人话）/「调用了什么工具」（MCP 名）/「数据从哪来」（原始返回）
- 互动教学点：让用户故意发模糊指令（「我想吃点啥」），看 Skill 先澄清 vs 直接瞎猜——教「好的 AI 先问再做」
- 完整演示四路查券、派对预约、积分抽奖、活动日历等冷门工具，补全生态能力地图
- 学完生成「我搞懂了 MCP」证书卡片（可晒）

**榜单差异化**：0 个教学 / 元方向；对官方生态有可见贡献，可能获得官方或 WorkBuddy 转发。

**Star 逻辑**：生态价值 + 「从入门到点餐」标题党 + 证书晒图。

**风险**：自然增长可能慢，依赖转发；实用性叙事要包装好。

---

## 五、路线建议

**推荐组合：方向 1 做本体卡位 + 方向 2 做主传播钩子，方向 3/4/5 作为 README 里的 Roadmap 展示野心。**

理由：
1. **先解决报名**：方向 1 资产最全，12 天内把仓库材料补齐、Issue 报名，先拿「进榜保底」（Star > 0 即可进前 100，门槛仅 6）
2. **传播上借力**：方向 2 复用最大流量赛道（省钱）+ 唯一空白（证据链），README 首屏放「无证据链 AI vs 麦探长」对照实验做传播素材；「47 → 21.9」式数字天然吸 Star
3. **Roadmap 展示**：方向 3/4/5 写进 README  roadmap，向 Star 用户和官方展示方向感，也留好后续迭代空间
4. **合规红线**：全程只读为主；写操作（create-order 等）如做必须用户确认；Token 绝不进仓库；健康/营养结论只做数据呈现不做医疗断言

**立即可做的三件事**（按优先级）：
1. 整理仓库：把 `~/.workbuddy/apps/mcdetective/` 的 packages / apps / examples / skills 复制进 `mcdetective/`，补齐 `MCP_INTEGRATION.md`、`mcp-config.example.json`、`workbuddy.md`；确认 .gitignore 覆盖 token.txt 后推送 GitHub
2. 发报名 Issue（注意格式：标题与正文间无换行、项目地址不用 Markdown）
3. README 首屏加「AI 吹牛对照实验」模块 + 求 Star 话术；同步发掘金/技术社区引流
