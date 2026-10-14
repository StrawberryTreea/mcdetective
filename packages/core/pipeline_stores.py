# -*- coding: utf-8 -*-
"""
McTrace · 麦探长场景流水线（多门店巡查比价）

用户报案「想吃 X，哪家便宜」→ 探长按距离划定巡查范围，逐店取证：
  query-nearby-stores →（按方圆 radius_km 过滤 + max_stores 封顶）→
  逐店 query-meals + query-store-coupons → 跨店比对 → 结案报告

产出与其他场景完全同构的 trace.json（同一事件契约），可被 Studio / 办案页直接回放。

探长办案纪律（写进代码）：
1. 只汇报亲眼所见：不在返回数据之外补全任何信息；
2. 没线索就老实说：各店同价 → 明言「无从比起」，不制造假价差；
3. 特殊店型单独标注（快捷小站等），不混入常规店比价；
4. 每个数字可回溯到接口字段；
5. 全程只读，绝不触发下单 / 领券 / 抽奖。
"""
import os
import sys
import json
import re
import time
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import McdMCPClient, load_token

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO, "examples", "traces")
OUT_NAME = os.environ.get("MCTRACE_OUT") or "detective-patrol"

TITLE_MAP = {
    "user-request": "接报案",
    "query-nearby-stores": "划定巡查范围",
    "query-meals": "巡查门店菜单",
    "query-store-coupons": "核查门店券",
    "mctrace:rule": "比对发现线索",
    "summary-composer": "结案报告",
}

SLEEP = 0.35  # 限流 600 次/分钟，留足余量
DEFAULT_RADIUS_KM = 3.0
DEFAULT_MAX_STORES = 10


def mask_address(addr):
    if not addr:
        return ""
    m = re.match(r"^(.+?[路街巷道号])", addr)
    if m:
        return m.group(1).rstrip("号") + "**号"
    return addr[:4] + "***"


def to_yuan(v):
    try:
        return round(float(v), 2)
    except Exception:
        return None


def parse_distance_m(v):
    """接口返回的 distance 是米为单位的数值；异常时返回 None（上层做诚实降级）。"""
    try:
        d = float(v)
        return d if d >= 0 else None
    except (TypeError, ValueError):
        return None


def fmt_km(m):
    if m is None:
        return "未知"
    return f"{m/1000:.1f} km" if m >= 1000 else f"{int(round(m))} m"


def run_scenario(url, city, keyword, target,
                 radius_km=DEFAULT_RADIUS_KM, max_stores=DEFAULT_MAX_STORES,
                 trace_id=None, emit=None, quiet=False, token=None, mode="compare"):
    """跑一次真实巡查。

    mode   "compare"（默认）用户点了菜名 → 跨店比价（同形态分组、时段退路）
           "recommend" 用户问「什么好吃」→ 不替他决定吃什么，只报「现在这几家在卖什么」
    token  显式传入 MCP Token（在线服务按访客自带 Token 跑时用）；
           不传则回落到本机配置（环境变量 / token.txt / mcp.json）。
    """
    tok = token or load_token()
    c = McdMCPClient(tok, url=url)
    c.initialize()
    trace_id = trace_id or ("mcdetective-" + time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8])
    events = []
    seq = 0

    def add(kind, tool, status, facts, entities, rule, say_friendly, say_pro, request, response):
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
            "isMock": False,
            "request": request,
            "response": response,
        }
        events.append(ev)
        if emit:
            try:
                emit(ev)
            except Exception:
                pass
        return ev

    # 0) 接报案
    add("info", "user-request", "success",
        [{"key": "city", "value": city, "source": "user-request"},
         {"key": "keyword", "value": keyword, "source": "user-request"},
         {"key": "target", "value": target, "source": "user-request"},
         {"key": "radiusKm", "value": radius_km, "source": "user-request",
          "note": "巡查半径；只查方圆该距离内的门店"},
         {"key": "maxStores", "value": max_stores, "source": "user-request",
          "note": "巡查门店数上限，防止商圈过大时无限扫店"}],
        {target: "目标餐品 / target"},
        None,
        ((f"接到报案：{city}{keyword}附近，有人想知道现在有什么好吃的。"
          f"探长出动了——他不替用户决定吃什么，只把方圆 {radius_km:g} 公里内这几家在卖什么报清楚。"
          if mode == "recommend" else
          f"接到报案：{city}{keyword}附近，有人想查「{target}」哪家卖得便宜。"
          f"探长出动了，先按方圆 {radius_km:g} 公里划定巡查范围。")),
        (f"解析报案：区域={city}{keyword}；目标餐品={target}；"
         f"巡查半径={radius_km:g}km；门店上限={max_stores}。"),
        {"city": city, "keyword": keyword, "target": target,
         "radiusKm": radius_km, "maxStores": max_stores},
        {"case": f"{city}{keyword} {target}"})

    # 1) 划定巡查范围（按距离过滤）
    r_near = c.call("query-nearby-stores", {"beType": 1, "searchType": 2, "city": city, "keyword": keyword})
    near_ok = isinstance(r_near, dict) and r_near.get("success")
    all_stores = (r_near.get("data") or []) if near_ok else []
    dist_known = [s for s in all_stores if parse_distance_m(s.get("distance")) is not None]
    dist_missing = len(all_stores) - len(dist_known)
    if dist_known:
        within = [s for s in dist_known if parse_distance_m(s["distance"]) <= radius_km * 1000]
        range_txt = (fmt_km(min(parse_distance_m(s["distance"]) for s in within)) + "–" +
                     fmt_km(max(parse_distance_m(s["distance"]) for s in within))) if within else "无"
    else:
        within, range_txt = [], "未知"
    stores = (within or all_stores)[:max_stores]
    add("info" if stores else "error", "query-nearby-stores",
        "success" if stores else ("degraded" if near_ok else "error"),
        [{"key": "hitCount", "value": len(all_stores), "sourcePath": "$.data"},
         {"key": "withinRadius", "value": len(within), "source": "mctrace",
          "note": f"方圆 {radius_km:g} km 内的门店数"},
         {"key": "patrolCount", "value": len(stores), "source": "mctrace",
          "note": f"上限 {max_stores} 家后的实际巡查数"},
         ({"key": "distanceRange", "value": range_txt, "sourcePath": "$.data[].distance",
           "note": "接口返回距离为米"} if range_txt != "未知" else
          {"key": "distanceRange", "value": "接口未返回距离", "source": "mctrace",
           "note": "按接口返回顺序取前 N 家，不做距离承诺"}),
         {"key": "patrolList", "value": "、".join(s.get("storeName", "") for s in stores),
          "sourcePath": "$.data[].storeName"}],
        {s.get("storeName"): "巡查对象门店" for s in stores[:6]},
        None,
        (f"范围划定：{keyword}方圆 {radius_km:g} 公里命中 {len(within)} 家（距离 {range_txt}），"
         f"逐家查，最多 {max_stores} 家。"
         if dist_known and within else
         (f"范围划定：{keyword}命中 {len(all_stores)} 家，接口没给距离数据，"
          f"按返回顺序查前 {len(stores)} 家——范围这事不装懂。" if near_ok else
          "附近没找到门店，此案挂起。")),
        (f"门店查询命中 {len(all_stores)} 家；方圆 {radius_km:g}km 内 {len(within)} 家"
         f"（距离 {range_txt}）；取前 {len(stores)} 家巡查。"
         + (f"注意：{dist_missing} 家门店无距离字段，未纳入半径过滤。" if dist_missing else "")),
        {"beType": 1, "searchType": 2, "city": city, "keyword": keyword},
        {"success": near_ok, "hitCount": len(all_stores), "withinRadius": len(within),
         "distanceMissing": dist_missing})

    if not stores:
        return _finish(trace_id, events, quiet=quiet)

    # 2) 逐店巡查：菜单 + 门店券（每次真实调用一条事件）
    store_data = {}
    for i, s in enumerate(stores, 1):
        code = str(s.get("storeCode"))
        name = s.get("storeName") or code
        dist_m = parse_distance_m(s.get("distance"))
        info = {"name": name, "meals": {}, "coupons": [], "distM": dist_m}
        store_data[code] = info

        time.sleep(SLEEP)
        r_meals = c.call("query-meals", {"storeCode": code, "orderType": 1, "beType": 1})
        meals_ok = isinstance(r_meals, dict) and r_meals.get("success")
        meal_map = (r_meals.get("data", {}).get("meals") or {}) if meals_ok else {}
        for mcode, m in meal_map.items():
            if isinstance(m, dict) and m.get("name") is not None:
                info["meals"][mcode] = (m.get("name"), to_yuan(m.get("currentPrice")))
        hit = [(mc, v) for mc, v in info["meals"].items() if target in (v[0] or "")]
        hit_txt = (f"发现目标「{hit[0][1][0]}」，标价 ¥{hit[0][1][1]:g}"
                   if hit and hit[0][1][1] is not None else
                   ("发现目标但未取到标价" if hit else "本店无此餐品"))
        add("info", "query-meals", "success" if meals_ok else "error",
            [{"key": "storeName", "value": name, "sourcePath": "$.data.meals"},
             {"key": "distance", "value": fmt_km(dist_m), "sourcePath": "$.data[].distance"},
             {"key": "mealCount", "value": len(info["meals"]), "source": "mctrace"},
             {"key": "targetHit", "value": hit_txt, "source": "mctrace"}],
            {name: "巡查门店", target: "目标餐品"},
            None,
            f"第 {i} 站（{fmt_km(dist_m)}）：{name}，菜单 {len(info['meals'])} 个单品，{hit_txt}。",
            f"门店「{name}」（距离 {fmt_km(dist_m)}）菜单返回 {len(info['meals'])} 个单品；"
            f"目标餐品状态：{hit_txt}。",
            {"storeCode": code, "orderType": 1, "beType": 1},
            {"success": meals_ok, "mealCount": len(meal_map)})

        time.sleep(SLEEP)
        r_cou = c.call("query-store-coupons", {"orderType": 1, "beType": 1, "storeCode": code})
        cou_ok = isinstance(r_cou, dict) and r_cou.get("success")
        cou_data = (r_cou.get("data") or []) if cou_ok else []
        info["coupons"] = [x.get("title") for x in cou_data if isinstance(x, dict)]
        add("info", "query-store-coupons", "success" if cou_ok else "info",
            [{"key": "storeName", "value": name, "sourcePath": "$.data"},
             {"key": "couponCount", "value": len(info["coupons"]), "sourcePath": "$.data"},
             {"key": "coupons", "value": "、".join(info["coupons"]) or "无", "sourcePath": "$.data[].title"}],
            {t: "门店券 / coupon" for t in info["coupons"][:2]},
            None,
            f"{name} 门店券 {len(info['coupons'])} 张：{'、'.join(info['coupons']) or '无'}，记下。",
            f"门店「{name}」券查询返回 {len(info['coupons'])} 张。",
            {"orderType": 1, "beType": 1, "storeCode": code},
            {"success": cou_ok, "couponCount": len(info["coupons"])})

    # 3) 比对一：目标餐品跨店价差
    # 按「同一精确品名」分组比对——「麦香鱼」会同时命中单品（¥22）和套餐（¥33），
    # 混在一起比就会得出「差价 ¥11」这种把形态差异当成跨店差价的假线索。
    # 探长纪律：只跟同一种东西比价。
    groups = {}  # 精确品名 -> {门店名: 价格}
    for code, info in store_data.items():
        for mc, (mname, price) in info["meals"].items():
            # target 为空（recommend 模式）时不能进比价：'' in 名称 恒为真，会把整本菜单当成命中
            if target and mname and target in mname and price is not None:
                groups.setdefault(mname, {})[info["name"]] = price
    group_rows = []
    for gname, sp in groups.items():
        lo_store = min(sp, key=sp.get)
        hi_store = max(sp, key=sp.get)
        group_rows.append({
            "name": gname, "stores": sp,
            "low": lo_store, "lowPrice": sp[lo_store],
            "high": hi_store, "highPrice": sp[hi_store],
            "delta": round(sp[hi_store] - sp[lo_store], 2),
            "exact": gname == target})
    # 主对比组：优先精确同名，其次覆盖门店最多，再按差价大小
    group_rows.sort(key=lambda g: (not g["exact"], -len(g["stores"]), -g["delta"]))
    primary = group_rows[0] if group_rows else None
    overview = None          # recommend 模式才有；比价模式下保持 None
    total_items = None      # 同上
    top = None              # 同上
    if primary:
        price_rows = sorted(
            ({"store": s, "storeCode": "", "price": p, "distM": None}
             for s, p in primary["stores"].items()),
            key=lambda r: r["price"])
        low, high = price_rows[0], price_rows[-1]
        delta = primary["delta"]
        same = delta <= 0.001
        other_forms = [g for g in group_rows[1:]]
        forms_note = ("；".join(
            f"「{g['name']}」" + (f"差价 ¥{g['delta']:g}" if g["delta"] > 0.001 else "各店同价")
            for g in other_forms)) or "无"
        price_facts = [{"key": "comparedForm", "value": primary["name"], "source": "mctrace",
                        "note": "目标关键词可能命中多种形态（单品/套餐），只与同一形态比价"},
                       {"key": "lowest", "value": f"{low['store']} ¥{low['price']:g}", "source": "menu"},
                       {"key": "highest", "value": f"{high['store']} ¥{high['price']:g}", "source": "menu"},
                       {"key": "deltaYuan", "value": delta, "source": "mctrace"},
                       {"key": "comparedStores", "value": len(price_rows), "source": "mctrace"},
                       {"key": "otherForms", "value": forms_note, "source": "mctrace",
                        "note": "其他命中形态的结论，单独列示，不混入主对比"}]
        price_friendly = (f"线索比对完成：「{primary['name']}」{len(price_rows)} 家在售。"
                          f"最低 {low['store']} ¥{low['price']:g}，最高 {high['store']} ¥{high['price']:g}。")
        price_pro = (f"目标餐品跨店比价（限定同形态「{primary['name']}」）：{len(price_rows)} 家门店在售；"
                     f"最低 {low['store']} ¥{low['price']:g}，最高 {high['store']} ¥{high['price']:g}，"
                     f"价差 ¥{delta:g}。其他命中形态：{forms_note}。")
        if same:
            price_friendly += "各店同价——本案无从比起，如实记录。"
            price_pro += "价差为 0，结论：各店同价。"
        if other_forms:
            price_friendly += f"另外还命中 {len(other_forms)} 种形态（{forms_note}），没混进来一起比。"
        price_kind = "info" if same else "success"
    elif mode == "recommend":
        # 用户问「什么好吃」→ 探长不替他决定吃什么，只把「现在这几家在卖什么」摊开：
        # 覆盖面（几家都有）、价格区间、在售款数。想比哪款，用户自己指。
        EXCLUDE_RE = re.compile(r"(可乐|雪碧|咖啡|牛奶|纯悦|鲜奶|冰奶|豆浆|豆奶|浆|茶饮|果饮|饮料"
                               r"|周边|毛绒|玩偶|玩具|手办|盲盒|挂件|钥匙扣|贴纸|徽章|帽子|头饰|发卡"
                               r"|水手帽|杯|勺|筷|叉|吸管|纸袋|餐巾|托盘|保鲜膜|兑换券|券|币|卡|包|袋|伞|鞋|袜)")
        cov = {}
        for info in store_data.values():
            for mc, (mname, price) in info["meals"].items():
                if mname and price is not None and not EXCLUDE_RE.search(mname):
                    cov.setdefault(mname, {})[info["name"]] = price
        rows = []
        for nm, sp in cov.items():
            rows.append({"name": nm, "stores": len(sp),
                         "low": round(min(sp.values()), 2), "high": round(max(sp.values()), 2)})
        rows.sort(key=lambda r: (-r["stores"], -r["high"]))
        overview = rows[:8]
        top = overview[0] if overview else None
        total_items = len(cov)
        price_rows = []
        primary = None
        low = high = None
        delta = 0
        price_facts = [
            {"key": "mode", "value": "recommend（用户没点菜名，只问有什么好吃）", "source": "mctrace"},
            {"key": "patrolStores", "value": len(stores), "source": "mctrace"},
            {"key": "soldItems", "value": total_items, "source": "menu",
             "note": "剔除饮品与周边后的在售单品数（以本次巡查时点为准）"},
            {"key": "topItem", "value": (f"{top['name']}（{top['stores']} 家都有，¥{top['low']:g}–¥{top['high']:g})"
                                          if top else "无"), "source": "menu"},
            {"key": "noPick", "value": "探长不替用户决定吃什么", "source": "mctrace"},
        ]
        menu_txt = "；".join(f"「{r['name']}」{r['stores']}家 ¥{r['low']:g}–¥{r['high']:g}" for r in overview[:4])
        price_friendly = (f"方圆 {radius_km:g} 公里这 {len(stores)} 家店现在共在售 {total_items} 款（已剔除饮品与周边）。"
                          f"覆盖面最广的几款：{menu_txt}。"
                          f"探长不替你决定吃什么——想比哪一款，指个名就行。")
        price_pro = (f"用户未指定餐品（mode=recommend）：{len(stores)} 家门店当前在售非饮品单品 {total_items} 款；"
                     f"按门店覆盖面排序的前 8 款见 overview；未做价格结论，未替用户选择。")
        price_kind = "info"
    else:
        # 时段感知：目标形态不在售（例：早时段只卖早餐）→ 不说「换案吧」的死胡同，
        # 而是找出这几家店卖得最齐的在售主食，给出可切换的替代案并照样比价。
        # 排除饮品与周边/玩具——替代案必须是能吃的东西，不能给用户推一个水手帽
        EXCLUDE = re.compile(r"(可乐|雪碧|咖啡|牛奶|纯悦|鲜奶|冰奶|豆浆|豆奶|浆|茶饮|果饮|饮料"
                             r"|周边|毛绒|玩偶|玩具|手办|盲盒|挂件|钥匙扣|贴纸|徽章|帽子|头饰|发卡"
                             r"|水手帽|杯|勺|筷|叉|吸管|纸袋|餐巾|托盘|保鲜膜|兑换券|券|币|卡|包|袋|伞|鞋|袜)")
        coverage_map = {}
        for info in store_data.values():
            for mc, (mname, price) in info["meals"].items():
                if mname and price is not None:
                    coverage_map.setdefault(mname, {})[info["name"]] = price
        need_n = max(2, len(stores) - 1)
        cands = [(nm, sp) for nm, sp in coverage_map.items()
                 if not EXCLUDE.search(nm) and len(sp) >= need_n]
        cands.sort(key=lambda kv: (-len(kv[1]), -max(kv[1].values())))
        alt = cands[0] if cands else None
        if alt:
            aname, asp = alt
            lo_s, hi_s = min(asp, key=asp.get), max(asp, key=asp.get)
            primary = {"name": aname}
            price_rows = sorted(({"store": s, "storeCode": "", "price": p, "distM": None}
                                 for s, p in asp.items()), key=lambda r: r["price"])
            low, high = price_rows[0], price_rows[-1]
            delta = round(high["price"] - low["price"], 2)
            same = delta <= 0.001
            price_facts = [{"key": "targetForm", "value": target, "source": "user-request"},
                           {"key": "targetOnSale", "value": "否——该形态当前不在这些店的菜单上",
                            "source": "mctrace", "note": "多为时段下架；如实记录，不冒充"},
                           {"key": "fallbackForm", "value": aname, "source": "menu",
                            "note": f"这几家店卖得最齐的在售主食（{len(asp)} 家都有），作为替代案比价"},
                           {"key": "comparedForm", "value": aname, "source": "mctrace",
                            "note": "价差榜比对的是替代案形态，不是报案要的那个形态"},
                           {"key": "lowest", "value": f"{low['store']} ¥{low['price']:g}", "source": "menu"},
                           {"key": "highest", "value": f"{high['store']} ¥{high['price']:g}", "source": "menu"},
                           {"key": "deltaYuan", "value": delta, "source": "mctrace"},
                           {"key": "comparedStores", "value": len(price_rows), "source": "mctrace"}]
            price_friendly = (f"翻遍 {len(stores)} 家店，「{target}」现在都不在菜单上——时段问题，"
                              f"探长不拿别的形态冒充它。这几家现在卖得最齐的是「{aname}」"
                              f"（{len(asp)} 家都有）：最低 {low['store']} ¥{low['price']:g}，"
                              f"最高 {high['store']} ¥{high['price']:g}。想比别的，报个案就行。")
            price_pro = (f"目标形态「{target}」在 {len(stores)} 家门店当前菜单中均未出现；"
                         f"替代案「{aname}」（{len(asp)} 家在售，¥{low['price']:g}–¥{high['price']:g}，"
                         f"价差 ¥{delta:g}）。")
            price_kind = "warning"
        else:
            price_rows = []
            price_facts = [{"key": "target", "value": target, "source": "user-request"},
                           {"key": "found", "value": "巡查门店均未发现该餐品", "source": "mctrace"}]
            price_friendly = f"翻遍 {len(stores)} 家店，都没找到「{target}」——换个时段或换个餐品再来。"
            price_pro = f"目标餐品「{target}」在 {len(stores)} 家巡查门店中均未出现。"
            price_kind = "warning"
    def _pfact(key, default=None):
        return next((f["value"] for f in price_facts if f["key"] == key), default)
    alt_form = str(_pfact("targetOnSale") or "").startswith("否")
    add(price_kind, "mctrace:rule", "success",
        price_facts,
        {r["store"]: "价差榜门店" for r in price_rows[:6]},
        {"id": "price.cross-store", "pass": bool(price_rows) and delta > 0.001,
         "deltaYuan": delta},
        price_friendly, price_pro,
        {"target": target, "stores": len(stores)},
        {"rows": price_rows, "deltaYuan": delta,
         "mode": mode,
         "overview": (overview if mode == "recommend" else None),
         "primaryForm": primary["name"] if primary else None,
         "targetOnSale": _pfact("targetOnSale"),
         "groups": [{"name": g["name"], "delta": g["delta"], "stores": len(g["stores"])}
                    for g in group_rows]})

    # 4) 比对二：餐品可得性（并集 vs 交集）
    code_sets = [set(info["meals"].keys()) for info in store_data.values()]
    common = set.intersection(*code_sets) if code_sets else set()
    union = set.union(*code_sets) if code_sets else set()
    partial = union - common
    example_txt = "无"
    if partial:
        for code, info in store_data.items():
            only_here = [mc for mc in partial if mc in info["meals"]]
            if only_here:
                mc = only_here[0]
                short = info["name"].replace("麦当劳北京", "").replace("麦当劳", "").replace("餐厅", "")
                example_txt = (f"「{info['meals'][mc][0]}」仅{short}有售；"
                               f"此类非全部巡查门店共有的单品共 {len(partial)} 款")
                break
    coverage = round(len(common) * 100.0 / len(union), 1) if union else 0.0
    add("info", "mctrace:rule", "success",
        [{"key": "unionItems", "value": len(union), "source": "mctrace"},
         {"key": "commonItems", "value": len(common), "source": "mctrace"},
         {"key": "coveragePct", "value": coverage, "source": "mctrace",
          "note": "全部门店都有售的单品占比；其余为部分门店限定"},
         {"key": "example", "value": example_txt, "source": "mctrace"}],
        {},
        {"id": "availability.coverage", "pass": True, "coveragePct": coverage},
        (f"顺手记一笔：{len(stores)} 家店合起来 {len(union)} 款单品，家家都有的只有 {len(common)} 款（{coverage}%）。"
         f"想吃限定款的话，门店选址比几块钱更要命：{example_txt}。"),
        (f"餐品可得性：并集 {len(union)} 款，交集 {len(common)} 款（覆盖率 {coverage}%）。"
         f"部分门店限定示例：{example_txt}。"),
        {"stores": len(stores)},
        {"union": len(union), "common": len(common), "coveragePct": coverage})

    # 5) 比对三：门店券一致性（探长纪律：不比券，只比价和货）
    coupon_sets = {code: tuple(sorted(info["coupons"])) for code, info in store_data.items()}
    unique_sets = set(coupon_sets.values())
    if len(unique_sets) == 1:
        coupon_friendly = "券也核查完了：各家门店券完全一致——所以这单不比券，只比价和货。"
        coupon_pro = "门店券跨店比对：所有巡查门店券集合完全一致，券维度不存在跨店差异。"
    else:
        coupon_friendly = (f"券核查完毕：{len(stores)} 家店出现了 {len(unique_sets)} 种不同券集合，"
                           f"差异已记录在案。")
        coupon_pro = (f"门店券跨店比对：发现 {len(unique_sets)} 种不同券集合，逐店明细见上方各事件证据。")
    add("info", "mctrace:rule", "success",
        [{"key": "uniqueCouponSets", "value": len(unique_sets), "source": "mctrace"},
         {"key": "verdict", "value": "完全一致" if len(unique_sets) == 1 else "存在差异", "source": "mctrace"}],
        {},
        {"id": "coupon.cross-store", "pass": True, "uniqueSets": len(unique_sets)},
        coupon_friendly, coupon_pro,
        {"stores": len(stores)},
        {"uniqueSets": len(unique_sets)})

    # 6) 结案报告
    form_txt = f"（{primary['name']}）" if primary and primary["name"] != target else ""
    if mode == "recommend":
        verdict = f"现在在售 {total_items} 款，覆盖面最广的是「{top['name'] if top else '—'}」"
    else:
        verdict = ("无从比起（各店同价）" if (price_rows and delta <= 0.001)
                   else (f"差价 ¥{delta:g}：{low['store']} 最便宜" if price_rows else "未发现目标餐品"))
    if alt_form:
        verdict = ("「" + target + "」当前不在售，替代案「" + _pfact("fallbackForm", "")
                   + "」" + verdict)
    dists = [info["distM"] for info in store_data.values() if info["distM"] is not None]
    patrol_range = f"{fmt_km(min(dists))}–{fmt_km(max(dists))}" if dists else "未知"
    result_facts = [
        {"key": "巡查门店", "value": len(stores), "source": "mctrace"},
        {"key": "巡查半径", "value": f"方圆 {radius_km:g} km（实际 {patrol_range}）", "source": "mctrace"},
        {"key": "目标餐品", "value": target, "source": "user-request"},
        ({"key": "在售款数", "value": total_items, "source": "menu"} if mode == "recommend"
         else {"key": "在售门店", "value": len(price_rows), "source": "mctrace"}),
        {"key": "结论", "value": verdict, "source": "mctrace"},
        {"key": "可得性覆盖率", "value": f"{coverage}%", "source": "mctrace"},
        {"key": "是否下单", "value": False, "source": "mctrace"},
    ]
    if price_rows:
        result_facts.insert(4, {"key": "最低价", "value": f"{low['store']} ¥{low['price']:g}", "source": "menu"})
        result_facts.insert(5, {"key": "最高价", "value": f"{high['store']} ¥{high['price']:g}", "source": "menu"})
        result_facts.insert(6, {"key": "比对形态", "value": primary["name"], "source": "mctrace",
                                "note": "只与同一形态比价；其他命中形态见价差线索"})
    add("success", "summary-composer", "success",
        result_facts,
        {target: "目标餐品", (low["store"] if low else keyword): "结论门店"},
        None,
        ((f"结案！方圆 {radius_km:g} 公里 {len(stores)} 家店巡查完毕：现在在售 {total_items} 款，"
          f"覆盖面最广的是「{top['name'] if top else '—'}」。探长没替你选——想比哪款，指个名。"
          f"每一步的原始调用都能点开核验。没下单，你定～") if mode == "recommend" else
         (f"结案！方圆 {radius_km:g} 公里 {len(stores)} 家店巡查完毕："
          + (verdict if alt_form else f"「{primary['name'] if primary else target}」{verdict}") + "。"
          + "每一步的原始调用都能点开核验。没下单，你定～")),
        (f"结案报告：巡查 {len(stores)} 家门店（半径 {radius_km:g}km，实际覆盖 {patrol_range}）；"
         f"目标「{target}」主比对形态「{primary['name'] if primary else '-'}」在售 {len(price_rows)} 家；"
         f"结论：{verdict}；可得性覆盖率 {coverage}%；未创建订单。"),
        {},
        {"result": {"patrolStores": len(stores), "patrolRange": patrol_range,
                    "target": target,
                    "mode": mode,
                    "soldItems": (total_items if mode == "recommend" else None),
                    "primaryForm": primary["name"] if primary else None,
                    "inStockStores": len(price_rows), "verdict": verdict,
                    "lowest": f"{low['store']} ¥{low['price']:g}" if low else None,
                    "highest": f"{high['store']} ¥{high['price']:g}" if high else None,
                    "deltaYuan": delta,
                    "coveragePct": coverage, "orderCreated": False}})
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
    out = os.path.join(OUT_DIR, f"real-{OUT_NAME}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if not quiet:
        print(f"TRACE: {trace_id}  ({len(events)} events) -> {out}\n")
        for ev in events:
            tag = {"info": "•", "warning": "⚠", "success": "✓", "error": "✗", "degraded": "≈"}.get(ev["kind"], "•")
            print(f"{tag} [{ev['tool']}] {ev['say']['friendly']}")
    return summary, out


if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else "https://mcp.mcd.cn"
    city = sys.argv[2] if len(sys.argv) > 2 else "北京市"
    kw = sys.argv[3] if len(sys.argv) > 3 else "中关村"
    target = sys.argv[4] if len(sys.argv) > 4 else "精选单人餐三件套"
    radius = float(sys.argv[5]) if len(sys.argv) > 5 else DEFAULT_RADIUS_KM
    n = int(sys.argv[6]) if len(sys.argv) > 6 else DEFAULT_MAX_STORES
    run_scenario(url=u, city=city, keyword=kw, target=target, radius_km=radius, max_stores=n)
