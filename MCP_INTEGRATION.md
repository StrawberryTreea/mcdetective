# MCP 集成说明（MCP_INTEGRATION.md）

> 本文说明麦探长 / McTrace 实际使用的麦当劳 MCP Server、Tool、调用流程与业务价值。
> 所有工具名与返回结构均来自对 `https://mcp.mcd.cn` 的真实调用观察（2026-10），非推测。

## 一、接入的 MCP Server

| Server | 类型 | 地址 | 用途 |
|---|---|---|---|
| `mcd-mcp` | streamablehttp | `https://mcp.mcd.cn` | **数据通道**：麦当劳中国官方 MCP，提供门店/菜单/营养/券/积分/订单等只读查询 |

认证：`mcd-mcp` 请求头携带 `Authorization: Bearer <MCD_TOKEN>`（Token 在麦当劳 MCP 开放平台 open.mcd.cn/mcp 免费申请）。**本项目全程只读，绝不调用任何写操作工具**（create-order / auto-bind-coupons / draw-lottery / mall-create-order / party-order-create / cancel-order 均不在调用清单内）。

限流处理：官方限制每 Token 600 次/分钟；巡查流水线在多门店循环中每次调用间隔 350ms，远低于限流。

## 二、实际调用的工具（14 个，按场景分组）

### 麦探长 · 跨店比价巡查（`packages/core/pipeline_stores.py`）

| 工具 | 用途 | 读取的关键字段 |
|---|---|---|
| `query-nearby-stores` | 按城市+地段拉附近门店，含距离（米） | `data[].storeCode / storeName / distance` |
| `query-meals` | 拉门店可售菜单 | `data.meals{code}.name / currentPrice` |
| `query-store-coupons` | 拉门店级优惠券 | `data[].title / products[].productName` |

调用时序：`query-nearby-stores` →（按方圆半径过滤 + 店数上限）→ 逐店 `query-meals` + `query-store-coupons` → 跨店比对（同形态比价 / 可得性 / 券一致性）→ 结案。

### 点餐推荐（`packages/core/pipeline.py`）

| 工具 | 用途 |
|---|---|
| `query-nearby-stores` | 定位门店 |
| `query-meals` | 菜单与标价 |
| `list-nutrition-foods` | 营养表（能量/蛋白质/脂肪/碳水/钠/钙），返回 CSV 文本 |
| `query-meal-detail` | 餐品构成（套餐组成/替换选项） |
| `query-store-coupons` | 门店券 |
| `available-coupons` | 麦麦省可领券（返回 Markdown，需专用解析器） |
| `calculate-price` | 下单前核价（无明细则诚实降级为菜单标价并标注来源） |

### 积分资产盘点（`packages/core/pipeline_points.py`）

| 工具 | 用途 |
|---|---|
| `query-my-account` | 积分账户（可用/累计/冻结/即将过期） |
| `query-lottery-info` | 积分抽奖活动信息 |
| `query-my-prizes` | 已中奖品记录 |
| `order-list` | 历史订单（沉睡奖券线索） |
| `query-survey-coupon` | 订单关联的满意度调查奖券（沉睡券唤醒） |
| `mall-points-products` | 积分商城可兑商品 |
| `campaign-calendar` | 当月营销活动日历 |

> 口径说明：`query-survey-coupon` 在当前服务端 `tools/list`（35 个工具）中存在，官方 GitHub 仓库的工具清单暂未列入——以服务端实时清单为准。

## 三、调用流程的业务价值

1. **取数交给 MCP，算术交给代码，表达交给 Agent**：优惠组合、跨店比价这类带约束的组合问题由确定性 Python 完成（可测试、可复现），模型只负责理解需求与讲解结论——价格错一位数就是事故，不让模型口算；
2. **每次调用都是一条证据**：所有调用以统一 Trace 契约记录（`traceId / seq / kind / tool / facts[] / rule / say{ friendly, pro } / request / response / evidenceRef`），用户可点开任何数字看它取自哪个接口的哪个字段；
3. **诚实降级是功能不是兜底**：算价无明细 → 标注 `priceSource=menu`；各店同价 → 明言「无从比起」；餐品关键词命中多种形态（单品/套餐）→ 分组比价，不拿形态差异冒充跨店差价；接口不给距离 → 明说不装懂；
4. **界面双形态**：MCP App（SEP-1865）把办案直播渲染进对话；不支持界面的宿主用自包含 HTML 回放页（`apps/detective/detective.html` / `apps/studio/live_story.html`），双击即开、离线可用。

## 四、快速验证

```bash
# 装为 WorkBuddy Skill 后，一句话报案（或本地入口直跑）
python skills/mcdetective/scripts/run_trace.py --detective 北京市 中关村 精选单人餐三件套 3 10
python apps/detective/build_detective.py   # 重新生成办案页
```
