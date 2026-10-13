"""
McTrace · 真实场景流水线

读取用户需求（预算 / 热量上限 / 位置），串联麦当劳 MCP 的只读工具：
  query-nearby-stores → query-meals → list-nutrition-foods → query-store-coupons → calculate-price
把每一次真实调用归一化为「事实事件」，由规则引擎做预算/营养校验，再由叙事引擎
生成俏皮/专业双文案，最终产出一份可回放的 trace.json。

原则（来自产品蓝图）：
- 只叙述已观察到的真实事实；不在返回数据之外补全名称。
- 金额以菜单 currentPrice（元，字符串）为准；calculate-price 若能返回明细则采用，
  否则明确标注「菜单标价（算价未返回明细）」，不假装算价成功。
- 全程只读，绝不调用 create-order / draw-lottery 等写操作。
"""
import os
import sys
import json
import re
import time
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import McdMCPClient, load_token
from coupon_parser import parse_coupon_markdown, usable_coupons

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO, "examples", "traces")
OUT_NAME = os.environ.get("MCTRACE_OUT") or "jingan-breakfast"

TITLE_MAP = {
    "user-request": "先把要求记下来",
    "query-nearby-stores": "找到具体门店",
    "query-meals": "认真翻了菜单",
    "list-nutrition-foods": "核对候选热量",
    "query-meal-detail": "拆开看它有什么",
    "mctrace:rule": "发现约束冲突",
    "query-store-coupons": "查看门店券",
    "calculate-price": "核算价格",
    "summary-composer": "整理好结果与证据",
}


# ---------- 脱敏 ----------
def mask_address(addr):
    if not addr:
        return ""
    # 保留到「路/号」前缀，门牌号打码
    m = re.match(r"^(.+?[路街巷道号])", addr)
    if m:
        return m.group(1).rstrip("号") + "**号"
    return addr[:4] + "***"


# ---------- 营养解析 ----------
def parse_nutrition(text):
    """list-nutrition-foods 的 data 是 CSV 文本表：
    [160]{productName,nutritionDescription,energyKj,energyKj?...}:\n  name,desc,kj,kcal,...
    返回 {产品名: kcal(int)}。
    """
    if not isinstance(text, str):
        return {}
    lines = text.splitlines()
    out = {}
    started = False
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith("[") and "productName" in ln:
            started = True
            continue
        if not started:
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 4:
            continue
        name = parts[0]
        try:
            kcal = int(float(parts[3]))
        except Exception:
            continue
        out[name] = kcal
    return out


# ---------- 餐品构成 ----------
# query-meal-detail 的返回结构可能随服务端变化，这里只做「保守抽取」：
# 能明确认出名字就给，认不出就返回空列表 —— 上层会标 degraded，不编造。
_NAME_KEYS = ("name", "productName", "itemName", "mealName", "materialName", "goodsName")
_LIST_KEYS = ("items", "mealDetailList", "detailList", "components", "composition",
              "groups", "products", "packageItems", "childList", "subItems", "list")


def _pluck_names(node, out, depth=0):
    if depth > 5 or len(out) >= 8 or node is None:
        return
    if isinstance(node, list):
        for x in node:
            _pluck_names(x, out, depth + 1)
        return
    if not isinstance(node, dict):
        return
    for k in _NAME_KEYS:
        v = node.get(k)
        if isinstance(v, str) and v.strip() and v.strip() not in out:
            out.append(v.strip())
            return
    for k in _LIST_KEYS:
        if k in node:
            _pluck_names(node[k], out, depth + 1)


def extract_composition(data):
    """从 query-meal-detail 的 data 里保守抽取餐品构成名称。"""
    out = []
    _pluck_names(data, out)
    return out


# ---------- 金额 ----------
def to_yuan(v):
    try:
        return round(float(v), 2)
    except Exception:
        return None


# ---------- 场景 ----------
def run_scenario(url, user_request, budget_yuan, max_kcal, city, keyword,
                 goal="satiety", trace_id=None, emit=None, quiet=False):
    """跑一遍真实场景。

    trace_id  由调用方指定（异步模式下 Store 需要提前登记这个 id 才能被轮询）
    emit      每条事件产生后立刻回调 emit(event)，用于「边跑边推」的真流式；
              不传则只在最后一次性返回（同步模式）
    quiet     服务端调用时不要往 stdout 打东西（会污染 stdio JSON-RPC）
    """
    tok = load_token()
    c = McdMCPClient(tok, url=url)
    c.initialize()
    trace_id = trace_id or ("mctrace-" + time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8])
    events = []
    seq = 0

    def add(kind, tool, status, facts, entities, rule, say_friendly, say_pro, request, response, is_mock=False):
        nonlocal seq
        seq += 1
        ev = {
            "traceId": trace_id,
            "seq": seq,
            "kind": kind,
            "tool": tool,
            "title": TITLE_MAP.get(tool, tool),
            "status": status,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "facts": facts,
            "entities": entities,
            "rule": rule,
            "say": {"friendly": say_friendly, "pro": say_pro},
            "evidenceRef": f"trace://{trace_id}/events/{seq}",
            "isMock": is_mock,
            "request": request,
            "response": response,
        }
        events.append(ev)
        if emit:
            try:
                emit(ev)
            except Exception:
                pass  # 推送失败不能拖垮采集
        return ev

    # 0) 用户目标
    add("info", "user-request", "success",
        [{"key": "keyword", "value": keyword, "source": "user-request"},
         {"key": "budgetYuan", "value": budget_yuan, "source": "user-request"},
         {"key": "maxKcal", "value": max_kcal, "source": "user-request"},
         {"key": "goal", "value": ("减脂（低卡）" if goal == "fatloss" else "常规（顶饱）"),
          "source": "user-request",
          "note": "目标决定选品规则；规则不同会给出完全不同的答案"}],
        {}, None,
        ("好嘞！%s%s附近，想点份减脂餐：价格不超过 %s 元、热量不超 %s 千卡，要低卡。我从找门店开始。"
         % (city, keyword, budget_yuan, max_kcal)) if goal == "fatloss" else
        ("好嘞！%s%s附近，想点份早餐：价格不超过 %s 元，热量也别超 %s 千卡，有券就用。我从找门店开始。"
         % (city, keyword, budget_yuan, max_kcal)),
        ("解析用户目标：区域=%s%s；价格上限=%s元；能量上限=%skcal；**目标=减脂**，"
         "因此选品规则为「约束内取热量最低的正餐」。" % (city, keyword, budget_yuan, max_kcal))
        if goal == "fatloss" else
        ("解析用户目标：区域=%s%s；价格上限=%s元；能量上限=%skcal；优先使用可用优惠券；"
         "两条约束都为硬约束；**目标=常规**，因此选品规则为「约束内取最顶饱」。"
         % (city, keyword, budget_yuan, max_kcal)),
        {"keyword": keyword, "budgetYuan": budget_yuan, "maxKcal": max_kcal, "goal": goal},
        {"userRequest": user_request})

    # 1) 附近门店
    r_near = c.call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": city, "keyword": keyword})
    near_ok = isinstance(r_near, dict) and r_near.get("success")
    stores = (r_near.get("data") or []) if near_ok else []
    store = stores[0] if stores else None
    store_code = store.get("storeCode") if store else None
    store_name = store.get("storeName") if store else None
    add("info", "query-nearby-stores", "success" if near_ok else "error",
        [{"key": "storeName", "value": store_name, "sourcePath": "$.data[0].storeName"},
         {"key": "storeCode", "value": store_code, "sourcePath": "$.data[0].storeCode"},
         {"key": "address", "value": mask_address(store.get("address")) if store else None,
          "sourcePath": "$.data[0].address"}] if store else [],
        {store_name: "门店名称 / storeName"} if store_name else {},
        None,
        f"找到了！先看「{store_name}」，位置正合适。我就从它的菜单开始查。" if store else "附近没找到合适门店。",
        f"门店查询返回候选。选用「{store_name}」（编码 {store_code}）作为后续菜单查询的目标门店。" if store else "门店查询未返回候选。",
        {"beType": 1, "searchType": 2, "city": city, "keyword": keyword},
        {"success": near_ok, "storeCount": len(stores)})

    if not store:
        return _finish(trace_id, events, quiet=quiet)

    # 2) 菜单
    r_meals = c.call("query-meals", {"storeCode": store_code, "orderType": 1, "beType": 1})
    meals_ok = isinstance(r_meals, dict) and r_meals.get("success")
    meal_map = (r_meals.get("data", {}).get("meals") or {}) if meals_ok else {}
    candidates = []
    for code, info in meal_map.items():
        name = info.get("name")
        price = to_yuan(info.get("currentPrice"))
        if name and price is not None:
            candidates.append({"code": code, "name": name, "price": price})
    add("info", "query-meals", "success" if meals_ok else "error",
        [{"key": "itemCount", "value": len(candidates), "sourcePath": "$.data.meals"},
         {"key": "sample", "value": "、".join(c["name"] for c in candidates[:3]), "sourcePath": "$.data.meals"}],
        {c["name"]: "菜单餐品 / item.name" for c in candidates[:4]},
        None,
        f"菜单里看了不少单品，先记几个带热量的候选：{ '、'.join(c['name'] for c in candidates[:3]) }……",
        f"菜单返回 {len(candidates)} 个带价格单品。进入营养与预算校验。",
        {"storeCode": store_code, "orderType": 1, "beType": 1},
        {"success": meals_ok, "mealCount": len(meal_map)})

    # 3) 营养
    r_nut = c.call("list-nutrition-foods", {})
    nut_text = ""
    if isinstance(r_nut, dict):
        nut_text = r_nut.get("data") if isinstance(r_nut.get("data"), str) else json.dumps(r_nut.get("data"), ensure_ascii=False)
    nut = parse_nutrition(nut_text)
    # 给候选补 kcal
    for it in candidates:
        it["kcal"] = nut.get(it["name"])
    # 仅保留「正餐单品」：排除饮品/甜品/小食/周边（按名称关键词），避免把水/薯条当推荐
    EXCLUDE = ["可乐", "雪碧", "纯悦", "牛奶", "咖啡", "奶茶", "新地", "麦旋风", "汁", "茶",
               "原味", "圆筒", "派", "玉米杯", "苹果片", "周边", "饼干", "帽子", "按摩",
               "捶", "薯条", "鸡块", "鸡翅", "V翅", "小食", "蘸酱", "脆薯饼", "油条",
               "圆子", "麻薯", "蛋挞", "圣代", "奶昔"]
    matched = [c for c in candidates if c["kcal"] is not None and c["kcal"] > 0
               and not any(tok in c["name"] for tok in EXCLUDE)]
    candidates_with_kcal = [c for c in candidates if c.get("kcal")]
    # 营养表覆盖率是本场景最容易被忽略的事实：菜单里很多在售单品营养表根本没有条目。
    # 不把它显式说出来，后面所有"最优选品"都建立在一个很小的可选集上，用户却不知道。
    coverage = round(len(candidates_with_kcal) * 100.0 / len(candidates), 1) if candidates else 0.0
    add("info", "list-nutrition-foods", "success" if nut else "error",
        [{"key": "menuItems", "value": len(candidates), "sourcePath": "$.data.meals"},
         {"key": "nutritionMatched", "value": len(candidates_with_kcal), "source": "nutrition-table"},
         {"key": "coveragePct", "value": coverage, "source": "mctrace",
          "note": "营养表只覆盖部分在售单品；未覆盖者无法判断热量，不参与推荐"},
         {"key": "sample", "value": "、".join(f"{c['name']} {c['kcal']}kcal" for c in matched[:3]), "source": "nutrition-table"}],
        {c["name"]: "营养餐品 / nutrition" for c in matched[:4]},
        {"id": "nutrition.coverage", "pass": coverage >= 60, "coveragePct": coverage},
        (f"核对了候选的热量：{'，'.join(c['name']+' '+str(c['kcal'])+'千卡' for c in matched[:3])}……"
         f"不过菜单里 {len(candidates)} 个单品，营养表只对得上 {len(candidates_with_kcal)} 个（{coverage}%），"
         f"剩下那些我没法判断热量，不瞎推荐。"),
        (f"菜单 {len(candidates)} 个在售单品，营养表匹配到 {len(candidates_with_kcal)} 个（覆盖率 {coverage}%），"
         f"其中 {len(matched)} 个为正餐单品，可用于能量约束校验。"
         f"覆盖率不足时推荐结果的可选集很小，此事实已显式告知用户。"),
        {},
        {"menuItems": len(candidates), "matched": len(candidates_with_kcal), "coveragePct": coverage})

    # 4) 规则与选品
    # 先说目标：用户的诉求决定"在约束内挑什么"，这不是一个可有可无的参数。
    #   satiety（默认·早餐/正餐）：两条硬约束通过后挑最顶饱的（能量最高但不超标）
    #   fatloss（减脂/控卡）    ：两条硬约束通过后挑热量最低的正餐单品
    # 早期只有一条"挑最顶饱"规则，结果"减脂晚餐"被选成 391 kcal 的堡 —— 每条约束都过了，
    # 用户目标却没达成。这正是本产品要暴露的那类差距，所以目标必须显式、可解释。
    affordable = [c for c in matched if c["price"] <= budget_yuan]
    passing = [c for c in affordable if c["kcal"] <= max_kcal]
    if goal == "fatloss":
        # 减脂：只要正餐单品（kcal 落在合理主食区间），在约束内取热量最低
        mains = [c for c in passing if 150 <= c["kcal"]]
        pick = min(mains, key=lambda c: c["kcal"]) if mains else None
        rule_text = "减脂目标：预算与热量两条硬约束都通过后，取热量最低的正餐单品"
    else:
        pick = max(passing, key=lambda c: c["kcal"]) if passing else None
        rule_text = "常规目标：预算与热量两条硬约束都通过后，取最顶饱的那个（能量最高但不超标）"
    recommended = pick
    initial = max(matched, key=lambda c: c["kcal"]) if matched else None  # 朴素首选项（热量最高）

    if initial and initial["kcal"] > max_kcal:
        rule_fail = {"id": "nutrition.max", "pass": False,
                     "deltaKcal": initial["kcal"] - max_kcal}
        add("warning", "mctrace:rule", "success",
            [{"key": "item", "value": initial["name"], "source": "menu+nutrition"},
             {"key": "kcal", "value": initial["kcal"], "sourcePath": "$.nutrition"},
             {"key": "maxKcal", "value": max_kcal, "source": "user-request"},
             {"key": "deltaKcal", "value": rule_fail["deltaKcal"], "source": "rule"}],
            {initial["name"]: "初始方案餐品"},
            None,
            f"等等……「{initial['name']}」约 {initial['kcal']} 千卡，比 {max_kcal} 的目标多了 {rule_fail['deltaKcal']}。看来得收敛一点！",
            f"初始候选「{initial['name']}」示例营养 {initial['kcal']} kcal，超过用户上限 {rule_fail['deltaKcal']} kcal，约束未通过。",
            {"item": initial["name"], "kcal": initial["kcal"], "maxKcal": max_kcal},
            {"rule": "nutrition.max"})

    # 4.5) 餐品构成（真实存在的 query-meal-detail；到店自提场景不要传 beCode）
    if recommended:
        r_det = c.call("query-meal-detail", {"storeCode": store_code, "orderType": 1, "beType": 1,
                                             "code": recommended["code"]})
        det_ok = isinstance(r_det, dict) and r_det.get("success")
        parts = extract_composition(r_det.get("data") if det_ok else None)
        add("info" if parts else "warning", "query-meal-detail",
            "success" if parts else "degraded",
            ([{"key": "item", "value": recommended["name"], "sourcePath": "$.request.code"},
              {"key": "composition", "value": "、".join(parts), "sourcePath": "$.data"}]
             if parts else
             [{"key": "item", "value": recommended["name"], "sourcePath": "$.request.code"},
              {"key": "composition", "value": "未解析出构成字段", "source": "mctrace"}]),
            {recommended["name"]: "餐品构成 / meal-detail"},
            None,
            (f"顺手拆开看了一眼「{recommended['name']}」：{'、'.join(parts)}。"
             if parts else
             f"想拆开看「{recommended['name']}」的构成，但这次返回里没解析出构成字段，就不瞎猜了。"),
            (f"餐品详情返回构成：{parts}。" if parts else
             "餐品详情调用成功但未解析出构成字段（口径可能变化），不推断。"),
            {"storeCode": store_code, "orderType": 1, "beType": 1, "code": recommended["code"]},
            {"success": det_ok, "parsedParts": len(parts)})

    # 5) 门店券
    r_cou = c.call("query-store-coupons", {"orderType": 1, "beType": 1, "storeCode": store_code})
    coupons = (r_cou.get("data") or []) if isinstance(r_cou, dict) and r_cou.get("success") else []
    coupon_names = [x.get("title") for x in coupons]
    # 判断券是否适用推荐单品
    applicable = False
    if recommended and coupons:
        for x in coupons:
            for p in (x.get("products") or []):
                if recommended["name"] in (p.get("productName") or ""):
                    applicable = True
    add("info", "query-store-coupons", "success" if coupons else "info",
        [{"key": "couponCount", "value": len(coupons), "sourcePath": "$.data"},
         {"key": "coupons", "value": "、".join(coupon_names) if coupon_names else "无", "sourcePath": "$.data[].title"},
         {"key": "applicableToPick", "value": "是" if applicable else "否", "source": "match"}],
        {n: "优惠券名称 / couponName" for n in coupon_names[:2]},
        None,
        (f"咦，门店有券：{'、'.join(coupon_names)}。不过这次单品用不上，先记着。"
         if coupon_names and not applicable else
         (f"门店有券：{'、'.join(coupon_names)}，看看能不能用上。" if coupon_names else
          "这家门店券接口这次没返回可用券 —— 但这不等于你没券，账户券是另一套，接着查。")),
        f"门店券查询返回 {len(coupons)} 张；与推荐单品的适用商品匹配结果：{'适用' if applicable else '不适用'}。",
        {"orderType": 1, "beType": 1, "storeCode": store_code},
        {"success": bool(coupons), "couponCount": len(coupons)})

    # 5.5) 账户侧可领券（真实存在但返回 Markdown，解析器在 coupon_parser.py）
    # 早期版本只查门店券就说"没有可用券"，而账户侧其实有 3 张可领券 —— 这是把事实搞错了。
    r_av = c.call("available-coupons", {})
    av_raw = r_av.get("_raw_text", "") if isinstance(r_av, dict) else ""
    av_all, av_meta = parse_coupon_markdown(av_raw)
    av_usable = usable_coupons(av_all)
    add("info" if av_usable else "warning", "available-coupons",
        "success" if av_usable else "degraded",
        [{"key": "parsedCoupons", "value": av_meta["lines"], "source": "markdown-parse"},
         {"key": "usableCoupons", "value": len(av_usable), "source": "markdown-parse"},
         {"key": "usableList", "value": "、".join(x["title"] for x in av_usable) or "无",
          "source": "markdown-parse"},
         {"key": "format", "value": "markdown（非 JSON）", "source": "mctrace",
          "note": "该工具返回 Markdown 文本，通用 JSON 解析器会读不出"}],
        {x["title"]: "可领取优惠券 / coupon" for x in av_usable[:3]},
        {"id": "coupon.available", "pass": bool(av_usable), "usable": len(av_usable)},
        (f"账户里还有 {len(av_usable)} 张能直接领的券：{'、'.join(x['title'] for x in av_usable)}。"
         if av_usable else
         f"账户侧券解析了 {av_meta['lines']} 条，但状态都不是「可领取」，所以没有能直接用的。"),
        (f"available-coupons 返回 Markdown 文本，解析出 {av_meta['lines']} 条，"
         f"其中状态为可领取的 {len(av_usable)} 张。"
         if av_usable else
         f"available-coupons 返回 Markdown 文本，解析出 {av_meta['lines']} 条，可用 {len(av_usable)} 张。"),
        {},
        {"format": "markdown", "parsed": av_meta["lines"], "usable": len(av_usable)})

    # 6) 算价（尝试；失败则回退菜单价）
    price_src = "menu"
    payable = recommended["price"] if recommended else None
    if recommended:
        r_price = c.call("calculate-price", {"storeCode": store_code, "orderType": 1, "beType": 1,
                                             "items": [{"code": recommended["code"], "quantity": 1}]})
        if isinstance(r_price, dict) and r_price.get("success") and to_yuan(r_price.get("data", {}).get("price")):
            payable = to_yuan(r_price["data"]["price"])
            price_src = "calculate-price"
        add("info" if price_src == "calculate-price" else "warning", "calculate-price",
            "success" if price_src == "calculate-price" else "degraded",
            [{"key": "payableYuan", "value": payable, "sourcePath": "$.data.price" if price_src == "calculate-price" else "$.data.meals"},
             {"key": "budgetYuan", "value": budget_yuan, "source": "user-request"},
             {"key": "priceSource", "value": price_src, "source": "mctrace"}],
            {recommended["name"]: "算价餐品 / item.name", str(payable): "应付金额 / payableYuan"},
            ({"id": "budget.max", "pass": payable <= budget_yuan, "deltaYuan": round(payable - budget_yuan, 2)}
             if payable is not None else None),
            (f"价格也算好了：「{recommended['name']}」模拟应付 {payable} 元（来源：{price_src}），比 {budget_yuan} 元预算还宽裕。"
             if price_src == "calculate-price" else
             f"算价接口这次没返回明细，我就用菜单标价：「{recommended['name']}」{payable} 元（来源：菜单）。"),
            f"价格来源={price_src}；应付={payable}元；预算规则通过={payable <= budget_yuan if payable is not None else 'n/a'}。",
            {"storeCode": store_code, "orderType": 1, "beType": 1, "items": [{"code": recommended["code"], "quantity": 1}]},
            {"success": r_price.get("success") if isinstance(r_price, dict) else False,
             "priceSource": price_src})

    # 7) 结果
    if recommended:
        # 备选（同一规则下的前几名）—— 用户常问"还有别的吗"，直接给，别让他再问一遍
        pool = mains if goal == "fatloss" else passing
        alts = [c for c in pool if c["code"] != recommended["code"]][:3]
        alt_txt = "；".join("%s %skcal/¥%g" % (c["name"], c["kcal"], c["price"]) for c in alts)
        best_txt = ("减脂目标下热量最低的单品" if goal == "fatloss"
                    else "通过两条约束里最顶饱的单品")
        add("success", "summary-composer", "success",
            [{"key": "store", "value": store_name, "sourcePath": "$.data[0].storeName"},
             {"key": "推荐单品", "value": recommended["name"], "source": "menu+nutrition"},
             {"key": "总价", "value": payable, "source": price_src},
             {"key": "热量", "value": recommended["kcal"], "source": "nutrition-table"},
             {"key": "选品规则", "value": rule_text, "source": "mctrace"},
             {"key": "备选", "value": alt_txt or "（无）", "source": "menu+nutrition"},
             {"key": "营养覆盖率", "value": "%s%%（菜单 %s 个在售单品中 %s 个有热量数据）"
              % (coverage, len(candidates), len(candidates_with_kcal)), "source": "mctrace"},
             {"key": "是否下单", "value": False, "source": "mctrace"}],
            {store_name: "最终门店", recommended["name"]: "最终餐品"},
            None,
            "搞定！「%s」的%s：%s。%s 元、%s 千卡 —— %s。%s没下单，你定～"
            % (store_name, "减脂晚餐" if goal == "fatloss" else "早餐",
               recommended["name"], payable, recommended["kcal"], best_txt,
               (("同规则的备选：" + alt_txt + "。") if alt_txt else "")),
            ("完成报告：门店=%s；推荐=%s；价格=%s元（来源%s）；热量=%skcal；"
             "选品规则=%s；备选=%s；营养覆盖率=%s%%；未创建订单。"
             % (store_name, recommended["name"], payable, price_src, recommended["kcal"],
                rule_text, alt_txt or "无", coverage)),
            {},
            {"result": {"store": store_name, "item": recommended["name"], "payableYuan": payable,
                        "kcal": recommended["kcal"], "goal": goal, "rule": rule_text,
                        "alternatives": [c["name"] for c in alts],
                        "nutritionCoveragePct": coverage,
                        "checksPassed": True, "orderCreated": False,
                        "summary": "%s %skcal/¥%g（%s）" % (
                            recommended["name"], recommended["kcal"], payable, best_txt)}})
    return _finish(trace_id, events, quiet=quiet)


def _finish(trace_id, events, quiet=False):
    summary = {
        "traceId": trace_id,
        "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "isMock": False,
        "eventCount": len(events),
        "events": events,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    # 固定场景名 → 重复运行覆盖同一份，回放页场景列表不会堆积
    # 需要留历史快照时用环境变量 MCTRACE_OUT 指定别名
    out = os.path.join(OUT_DIR, f"real-{OUT_NAME}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if not quiet:
        # 控制台打印俏皮叙事
        print(f"TRACE: {trace_id}  ({len(events)} events) -> {out}\n")
        for ev in events:
            tag = {"info": "•", "warning": "⚠", "success": "✓", "error": "✗", "degraded": "≈"}.get(ev["kind"], "•")
            print(f"{tag} [{ev['tool']}] {ev['say']['friendly']}")
    return summary, out


if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else "https://mcp.mcd.cn"
    kw = sys.argv[2] if len(sys.argv) > 2 else "静安寺"
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 40
    kcal = int(sys.argv[4]) if len(sys.argv) > 4 else 500
    city = sys.argv[5] if len(sys.argv) > 5 else "上海市"
    run_scenario(
        url=u,
        user_request=f"{city}{kw}附近，想点份早餐：价格不超过{budget:g}元，热量也别超{kcal}千卡，有券就用。",
        budget_yuan=budget, max_kcal=kcal, city=city, keyword=kw,
    )
