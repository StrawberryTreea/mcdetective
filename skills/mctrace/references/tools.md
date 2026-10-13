# 工具与真实返回结构（McTrace 用到的 5 个只读工具）

> 以下均为对 `https://mcp.mcd.cn` 的**真实调用**观察所得，非推测。
> 该平台共 35 个工具，McTrace 仅使用下列 5 个查询类工具。

---

## 1. `query-nearby-stores`

**入参**

```json
{ "beType": 1, "searchType": 2, "city": "上海市", "keyword": "静安寺" }
```

**返回（节选）**

```json
{ "success": true, "code": 0,
  "data": [
    { "storeCode": "1450002",
      "storeName": "麦当劳上海静安寺餐厅",
      "address": "万航渡路***号",
      "distance": "..." }
  ] }
```

- `data` 为数组；McTrace 取 `data[0]` 作为目标门店。
- **脱敏**：`address` 门牌号以 `**` 打码（`mask_address()`）后才进入 Trace。

---

## 2. `query-meals`

**入参**

```json
{ "storeCode": "1450002", "orderType": 1, "beType": 1 }
```

**返回（节选）**

```json
{ "success": true,
  "data": {
    "categories": [ { "meals": [ { "code": "1600" } ] } ],
    "meals": {
      "1600": { "name": "麦香鱼", "currentPrice": "23", "originalPrice": "24", "canWithOrder": true }
    }
  } }
```

- **`currentPrice` 是字符串**（元），归一化时 `to_yuan()` 转 float。
- McTrace 从 `data.meals` 取 `{code, name, currentPrice}` 作为候选；某门店样本约 117 个带价单品。

---

## 3. `list-nutrition-foods`

**入参**：无（`{}`）

**返回**：`data` 为 **CSV 文本表**（不是 JSON 对象），形如

```
[160]{productName,nutritionDescription,energyKj,powerKj...}:
  麦香鱼,某描述,1350,325,...
  培根安格斯厚牛堡,某描述,2956,707,...
```

- 第 4 列为 **kcal**；McTrace `parse_nutrition()` 解析为 `{名称: kcal}`。
- 与菜单候选**按名称精确匹配**；匹配不到**不补造**。

---

## 4. `query-store-coupons`

**入参**

```json
{ "orderType": 1, "beType": 1, "storeCode": "1450002" }
```

**返回（节选）**

```json
{ "success": true,
  "data": [ { "title": "麦旋风任选", "products": [ { "productName": "..." } ] },
            { "title": "薯薯任选",   "products": [ { "productName": "..." } ] } ] }
```

- McTrace 记录 `couponCount / coupons`，并按 `products[].productName` 判断**是否适用于推荐单品**。

---

## 5. `calculate-price`

**入参**

```json
{ "storeCode": "1450002", "orderType": 1, "beType": 1,
  "items": [ { "code": "1600", "quantity": 1 } ] }
```

**两种返回**

- 真正计价（需带 `modification / selectedKey` 等明细）：
  `{ "success": true, "data": { "price": "23.00", "productList": [ ... ], "takeWayList": [ ... ] } }`
- 只传 `{code, quantity}`：`{ "success": true, "data": { "price": 0, "productList": [] } }` —— **空明细**。

### McTrace 的处理：诚实降级

当出现空明细时，McTrace **不假装算价成功**，而是：

- 事件 `kind = warning`、`status = degraded`；
- 事实里加 `priceSource = menu`；
- 叙述写明「算价接口这次没返回明细，我就用菜单标价」。

这保证了**金额永远可回溯到真实来源**，而不是编造。

---

## 附：MCP 客户端兼容性说明

`packages/core/mcp_client.py` 的响应解析需同时兼容：

1. 纯 JSON；
2. SSE（`event: message` + `data: {...}`）；
3. 文本包裹（末尾 `## Original Response` 后再接 JSON）。

**已踩坑**：某些工具返回的 Markdown 说明里含**伪花括号**（如 `{data[].x}`），会误导朴素的 `json.loads(首个{)`。
因此解析器改为「在每个 `"success"` 之前找最近的 `{` 起做括号配平」（`_balance_parse`）。
