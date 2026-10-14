# -*- coding: utf-8 -*-
"""
案卷渲染内核（办案页生成器与在线后端共用）。

同一份 trace → 同一套 HTML，保证「归档案卷」和「实时跑出来的案卷」外观完全一致，
不存在「demo 一个样、真跑另一个样」的问题。

原则：只叙述 trace 里已观测到的真实事实；数字与文案均从 trace 提取，不额外编造。
"""
import html as H
import json


def esc(s):
    return H.escape(str(s), quote=True)


def short(name):
    return (name.replace("麦当劳北京", "").replace("麦当劳上海", "").replace("麦当劳", "")
                .replace("餐厅", "").strip() or name)


def facts_of(ev):
    return {f["key"]: f["value"] for f in ev.get("facts", [])}


def render_case(T):
    """把一份 trace 渲染成一册案卷的 HTML（section 片段）。"""
    EVENTS = T["events"]
    RESULT = next((e["response"]["result"] for e in EVENTS
                   if (e.get("response") or {}).get("result")), {})
    PRICE_EV = next((e for e in EVENTS if (e.get("rule") or {}).get("id") == "price.cross-store"), None)
    ROWS = (PRICE_EV["response"].get("rows") or []) if PRICE_EV else []
    OVERVIEW = (PRICE_EV["response"].get("overview") or None) if PRICE_EV else None
    AVAIL_EV = next((e for e in EVENTS if (e.get("rule") or {}).get("id") == "availability.coverage"), None)
    COUPON_EV = next((e for e in EVENTS if (e.get("rule") or {}).get("id") == "coupon.cross-store"), None)
    STORES_EV = next((e for e in EVENTS if e["tool"] == "query-nearby-stores"), None)
    CASE_EV = EVENTS[0]

    low = ROWS[0] if ROWS else None
    high = ROWS[-1] if ROWS else None
    delta = round(high["price"] - low["price"], 2) if (low and high) else 0
    pct = round(delta / low["price"] * 100, 1) if (low and low["price"]) else 0
    avail_facts = facts_of(AVAIL_EV) if AVAIL_EV else {}
    coupon_facts = facts_of(COUPON_EV) if COUPON_EV else {}
    case_facts = facts_of(CASE_EV)
    stores_facts = facts_of(STORES_EV) if STORES_EV else {}
    price_facts = facts_of(PRICE_EV) if PRICE_EV else {}
    primary_form = price_facts.get("comparedForm", case_facts.get("target", ""))
    other_forms = price_facts.get("otherForms", "无")

    # 每店聚合（菜单事件 + 券事件按门店名配对）
    store_cards = {}
    for e in EVENTS:
        if e["tool"] == "query-meals":
            name = next((f["value"] for f in e["facts"] if f["key"] == "storeName"), "")
            store_cards.setdefault(name, {})["mealCount"] = next(
                (f["value"] for f in e["facts"] if f["key"] == "mealCount"), 0)
            store_cards[name]["distance"] = next(
                (f["value"] for f in e["facts"] if f["key"] == "distance"), "未知")
        elif e["tool"] == "query-store-coupons":
            name = next((f["value"] for f in e["facts"] if f["key"] == "storeName"), "")
            store_cards.setdefault(name, {})["coupons"] = next(
                (f["value"] for f in e["facts"] if f["key"] == "coupons"), "无")

    # 价差条形图（0 起 honest scale）
    pmax = max((r["price"] for r in ROWS), default=1) or 1
    bars = []
    for r in ROWS:
        w = round(r["price"] / (pmax * 1.06) * 100, 1)
        tag, cls = "", ""
        if r is ROWS[0] and delta > 0:
            tag, cls = '<span class="badge cheap">最便宜</span>', "cheap"
        if r is ROWS[-1] and len(ROWS) > 1 and delta > 0:
            tag = '<span class="badge pricey">最贵</span>'
            cls = "pricey" if not cls else cls
        bars.append(
            f'<div class="brow {cls}"><div class="bname">{esc(short(r["store"]))}{tag}</div>'
            f'<div class="btrack"><i style="width:{w}%"></i></div>'
            f'<div class="bval">¥{r["price"]:g}</div></div>')

    if OVERVIEW:
        ovl_rows = "".join(
            f'<div class="ovrow"><div class="ovname">{esc(r["name"])}</div>'
            f'<div class="ovcov">{r["stores"]} 家有售</div>'
            f'<div class="ovprice">¥{r["low"]:g}–{r["high"]:g}</div></div>'
            for r in OVERVIEW)
        delta_html = ('<div class="ovl"><div class="ovh"><span>在售单品</span><span>覆盖面</span>'
                      '<span>价格区间</span></div>' + ovl_rows +
                      '<div class="ovnote">只列覆盖面最广的前几款，完整菜单在案卷附录里；'
                      '想比哪一款，指个名，探长再去比。</div></div>')
    elif not ROWS:
        delta_html = '<div class="delta">巡查门店均未发现该餐品——此案无从比起。</div>'
    elif delta > 0:
        delta_html = (f'<div class="delta">差价 <b>¥{delta:g}</b>：{esc(short(high["store"]))} 比 '
                      f'{esc(short(low["store"]))} 贵 {pct}%</div>')
    else:
        delta_html = (f'<div class="delta">各店同价 <b>¥{low["price"]:g}</b>——本案无从比起，如实记录。</div>')

    if OVERVIEW:
        stamp_html = ('<div class="stamp">在售 {n} 款 · 没替你选</div>'
                      .format(n=esc(price_facts.get("soldItems", ""))))
    elif not ROWS:
        stamp_html = '<div class="stamp">未发现目标餐品</div>'
    elif delta > 0:
        stamp_html = f'<div class="stamp">差价 ¥{delta:g} · {esc(short(low["store"]))}最便宜</div>'
    else:
        stamp_html = f'<div class="stamp">无从比起 · 各店同价 ¥{low["price"]:g}</div>'

    # 巡查站点卡（按距离近→远）
    stations = []
    for i, (name, info) in enumerate(store_cards.items(), 1):
        row = next((r for r in ROWS if r["store"] == name), None)
        price_txt = f'¥{row["price"]:g}' if row else "未在售"
        pcls = ("p-cheap" if (row and row is ROWS[0] and delta > 0) else
                ("p-high" if (row and row is ROWS[-1] and delta > 0) else ""))
        stations.append(
            f'<div class="station {pcls}"><div class="sno">{i}</div>'
            f'<div class="sbody"><div class="sname">{esc(short(name))}</div>'
            f'<div class="smeta">{esc(info.get("distance","未知"))} · 菜单 {info.get("mealCount", 0)} 款 · 门店券 {esc(info.get("coupons", "无"))}</div></div>'
            f'<div class="sprice">{price_txt}</div></div>')

    forms_note = ""
    if other_forms and other_forms != "无":
        forms_note = (f'<div class="note">目标关键词还命中其他形态，单独列示、不混入比价：'
                      f'{esc(other_forms)}。</div>')
    fallback_note = ""
    if str(price_facts.get("targetOnSale") or "").startswith("否"):
        fallback_note = (f'<div class="warnbar">报案要的「{esc(price_facts.get("targetForm",""))}」'
                         f'当前不在这些店的菜单上（多为时段下架）——探长不拿别的形态冒充它，'
                         f'下面的价差榜是核心单品「{esc(price_facts.get("fallbackForm",""))}」。</div>')

    # 案卷附录
    KIND_DOT = {"info": "•", "warning": "⚠", "success": "✓", "error": "✗", "degraded": "≈"}
    evidence = []
    for e in EVENTS:
        dot = KIND_DOT.get(e["kind"], "•")
        req = json.dumps(e.get("request") or {}, ensure_ascii=False, indent=1)
        resp = json.dumps(e.get("response") or {}, ensure_ascii=False, indent=1)
        evidence.append(
            f'<details class="ev"><summary><span class="kdot kdot-{e["kind"]}">{dot}</span>'
            f'<span class="seq">{e["seq"]:02d}</span>'
            f'<span class="ttl">{esc(e["title"])}</span>'
            f'<span class="tool">{esc(e["tool"])}</span></summary>'
            f'<div class="say">{esc(e["say"]["friendly"])}</div>'
            f'<div class="raw"><div class="rawt">请求</div><pre>{esc(req)}</pre></div>'
            f'<div class="raw"><div class="rawt">返回（节选）</div><pre>{esc(resp[:1600])}</pre></div>'
            f'<div class="ref">{esc(e["evidenceRef"])}</div></details>')

    live_badge = ('<span class="live-dot" title="本册为实时巡查结果"></span>') if T.get("live") else ""
    return f"""
<section class="caseview">
<section class="card">
  <h2><span class="no">卷</span>案卷 · {esc(case_facts.get("city",""))}{esc(case_facts.get("keyword",""))}片区{live_badge}</h2>
  <div class="casefile">
    <div class="cf"><div class="k">报案诉求</div><div class="v">「{esc(case_facts.get("target",""))}」哪家卖得便宜？</div></div>
    <div class="cf"><div class="k">巡查范围</div><div class="v">方圆 {esc(case_facts.get("radiusKm",""))} km · 命中 {esc(stores_facts.get("withinRadius",""))} 家</div></div>
    <div class="cf"><div class="k">实际覆盖</div><div class="v">{esc(stores_facts.get("distanceRange",""))} · 巡查 {esc(stores_facts.get("patrolCount",""))} 家</div></div>
    <div class="cf"><div class="k">立案时间</div><div class="v">{esc(T["generatedAt"])}</div></div>
    <div class="cf"><div class="k">案号</div><div class="v" style="font-size:12px">{esc(T["traceId"])}</div></div>
    <div class="cf"><div class="k">状态</div><div class="v big">已结案 ✓</div></div>
  </div>
</section>

<section class="card">
  <h2><span class="no">1</span>巡查路线 · 逐店取证</h2>
  {''.join(stations)}
  <div class="note">站点按距离由近到远排列；距离取自 query-nearby-stores 的 distance 字段（米），标价取自各店 query-meals 的 currentPrice 字段，门店券数取自 query-store-coupons。</div>
</section>

<section class="card">
  <h2><span class="no">2</span>{"现在这几家在卖什么（用户没点菜名，探长不替他选）" if OVERVIEW else f"线索一 · 价差榜（{esc(primary_form)}）"}</h2>
  {''.join(bars)}
  {delta_html}
  {fallback_note}
  <div class="note">条形图自 ¥0 起按真实标价等比绘制，未做视觉放大；只与同一形态比价。</div>
  {forms_note}
</section>

<section class="card">
  <h2><span class="no">3</span>线索二 · 餐品可得性</h2>
  <div class="stats">
    <div class="stat"><div class="n">{esc(avail_facts.get("unionItems",""))}</div><div class="l">单品并集（款）</div></div>
    <div class="stat"><div class="n">{esc(avail_facts.get("commonItems",""))}</div><div class="l">全门店共有（款）</div></div>
    <div class="stat"><div class="n">{esc(avail_facts.get("coveragePct",""))}%</div><div class="l">共有覆盖率</div></div>
  </div>
  <div class="note" style="margin-top:10px">{esc(avail_facts.get("example",""))}。想吃限定款，门店选址比几块钱更要命。</div>
</section>

<section class="card">
  <h2><span class="no">4</span>线索三 · 门店券核查</h2>
  <div class="casefile">
    <div class="cf"><div class="k">不同券集合数</div><div class="v">{esc(coupon_facts.get("uniqueCouponSets",""))}</div></div>
    <div class="cf"><div class="k">结论</div><div class="v big">{esc(coupon_facts.get("verdict",""))}</div></div>
  </div>
  <div class="note" style="margin-top:10px">所以本案不比券，只比价和货——没差异的维度不硬凑戏。</div>
</section>

<section class="card">
  <h2><span class="no">5</span>结案报告</h2>
  <div class="verdict">
    {stamp_html}
    <div class="sub">{esc(RESULT.get("verdict",""))} · 可得性覆盖率 {esc(RESULT.get("coveragePct",""))}% · 未创建任何订单</div>
  </div>
  <div class="repro">$ python skills/mctrace/scripts/run_trace.py --detective {esc(case_facts.get("city",""))} {esc(case_facts.get("keyword",""))} {esc(case_facts.get("target",""))} {esc(case_facts.get("radiusKm","3"))} 10</div>
</section>

<section class="card">
  <h2><span class="no">附</span>案卷附录 · {len(EVENTS)} 条证据</h2>
  {''.join(evidence)}
</section>
</section>
"""