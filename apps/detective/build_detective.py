# -*- coding: utf-8 -*-
"""
麦探长 · 办案现场页面生成器（多案卷 + 接案台）

读取 examples/traces/real-detective-*.json（真实巡查 trace），生成麦探长专属的单文件
办案页 detective.html：

  顶栏：警长徽章 + 麦探长 · 麦当劳物价侦探
  接案台：输入 城市/区域/目标餐品/半径/店数 → 调档已归档真实案卷；
          未归档的报案 → 诚实面板（给出一条可粘贴的出勤命令，不装能直连）
  案卷视图（每册一份，JS 切换）：
    案卷卡 / 巡查路线（按距离近→远，最便宜金色、最贵红色）/
    线索一 价差榜（0 起 honest scale，限定同一形态比价）/
    线索二 可得性 / 线索三 券核查 / 结案报告印章 / 案卷附录（逐条可展开原始请求返回）
  办案纪律：五条（写进代码的原则）

原则：页面只叙述 trace 里已观测到的真实事实；数字与文案均从 trace 提取，不额外编造。
静态页不含任何 Token——参赛规则要求，也是安全边界。
"""
import json
import os
import glob
import base64
import html as H

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
TRACES_DIR = os.path.join(REPO, "examples", "traces")
ASSETS = os.path.join(REPO, "assets")
OUT = os.path.join(HERE, "detective.html")


def _b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")


# 警徽（用户生成的 AI 徽章图）：页头用 512 版，favicon 用 64 版，均内联保持单文件自包含
_badge_head = os.path.join(ASSETS, "badge-512.png")
_badge_icon = os.path.join(ASSETS, "badge-64.png")
BADGE_IMG = (f'<img src="data:image/png;base64,{_b64(_badge_head)}" width="52" height="52" '
             f'alt="麦探长警徽" style="display:block;border-radius:10px"/>') if os.path.exists(_badge_head) else ""
BADGE_ICON = (f"data:image/png;base64,{_b64(_badge_icon)}") if os.path.exists(_badge_icon) else ""

# 归档登记表：trace 文件名 → 展示标签（按此顺序排列）
ARCHIVE = [
    ("real-detective-patrol.json", "北京 · 中关村"),
    ("real-detective-jingan.json", "上海 · 静安寺"),
    ("real-detective-huanggang.json", "黄冈 · 万达"),
]


def esc(s):
    return H.escape(str(s), quote=True)


def short(name):
    return (name.replace("麦当劳北京", "").replace("麦当劳上海", "").replace("麦当劳", "")
                .replace("餐厅", "").strip() or name)


def facts_of(ev):
    return {f["key"]: f["value"] for f in ev.get("facts", [])}


def render_case(T):
    """把一份 trace 渲染成一册案卷的 HTML（不含外壳）。"""
    EVENTS = T["events"]
    RESULT = next((e["response"]["result"] for e in EVENTS
                   if (e.get("response") or {}).get("result")), {})
    PRICE_EV = next(e for e in EVENTS if (e.get("rule") or {}).get("id") == "price.cross-store")
    ROWS = PRICE_EV["response"].get("rows") or []
    AVAIL_EV = next(e for e in EVENTS if (e.get("rule") or {}).get("id") == "availability.coverage")
    COUPON_EV = next(e for e in EVENTS if (e.get("rule") or {}).get("id") == "coupon.cross-store")
    STORES_EV = next(e for e in EVENTS if e["tool"] == "query-nearby-stores")
    CASE_EV = EVENTS[0]

    low = ROWS[0] if ROWS else None
    high = ROWS[-1] if ROWS else None
    delta = round(high["price"] - low["price"], 2) if (low and high) else 0
    pct = round(delta / low["price"] * 100, 1) if (low and low["price"]) else 0
    avail_facts = facts_of(AVAIL_EV)
    coupon_facts = facts_of(COUPON_EV)
    case_facts = facts_of(CASE_EV)
    stores_facts = facts_of(STORES_EV)
    price_facts = facts_of(PRICE_EV)
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

    if not ROWS:
        delta_html = '<div class="delta">巡查门店均未发现该餐品——此案无从比起。</div>'
    elif delta > 0:
        delta_html = (f'<div class="delta">差价 <b>¥{delta:g}</b>：{esc(short(high["store"]))} 比 '
                      f'{esc(short(low["store"]))} 贵 {pct}%</div>')
    else:
        delta_html = (f'<div class="delta">各店同价 <b>¥{low["price"]:g}</b>——本案无从比起，如实记录。</div>')

    if not ROWS:
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

    forms_note = ""
    if other_forms and other_forms != "无":
        forms_note = f'<div class="note">目标关键词还命中其他形态，单独列示、不混入比价：{esc(other_forms)}。</div>'

    return f"""
<section class="caseview" data-city="{esc(case_facts.get('city',''))}" data-keyword="{esc(case_facts.get('keyword',''))}">
<section class="card">
  <h2><span class="no">卷</span>案卷 · {esc(case_facts.get("city",""))}{esc(case_facts.get("keyword",""))}片区</h2>
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
  <h2><span class="no">2</span>线索一 · 价差榜（{esc(primary_form)}）</h2>
  {''.join(bars)}
  {delta_html}
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


# ---------- 组装页面 ----------
cases = []
for fname, label in ARCHIVE:
    path = os.path.join(TRACES_DIR, fname)
    if not os.path.exists(path):
        continue
    with open(path, encoding="utf-8") as f:
        T = json.load(f)
    key = fname.replace("real-detective-", "").replace(".json", "")
    case_facts = facts_of(T["events"][0])
    cases.append({"key": key, "label": label, "city": case_facts.get("city", ""),
                  "keyword": case_facts.get("keyword", ""),
                  "target": case_facts.get("target", ""),
                  "html": render_case(T)})

views_html = "\n".join(
    f'<div class="caseview-wrap" id="case-{c["key"]}"{" style=\"display:none\"" if i else ""}>{c["html"]}</div>'
    for i, c in enumerate(cases))
chips_html = "".join(
    f'<button class="casechip{" on" if i == 0 else ""}" data-key="{c["key"]}">{esc(c["label"])}</button>'
    for i, c in enumerate(cases))
case_meta = json.dumps(
    [{"key": c["key"], "label": c["label"], "city": c["city"], "keyword": c["keyword"],
      "target": c["target"]}
     for c in cases], ensure_ascii=False)

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{background:#F6F2EA;color:#2C2C2A;font:14px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}
.wrap{max-width:920px;margin:0 auto;padding:18px 16px 60px}
.top{background:#fff;border:1.5px solid #E5DCC9;border-radius:16px;padding:14px 18px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;box-shadow:0 2px 10px rgba(120,100,60,.06)}
.top .logo{display:flex;align-items:center;gap:8px}
.top h1{font-size:19px;font-weight:800;letter-spacing:.5px}
.top h1 small{font-size:12px;font-weight:600;color:#8a7f68;margin-left:6px}
.card{background:#fff;border:1.5px solid #E5DCC9;border-radius:16px;padding:18px 20px;margin-top:14px;box-shadow:0 2px 10px rgba(120,100,60,.05)}
.card h2{font-size:15px;font-weight:800;display:flex;align-items:center;gap:8px;margin-bottom:12px}
.card h2 .no{width:22px;height:22px;border-radius:7px;background:#DA291C;color:#fff;font-size:12px;display:inline-flex;align-items:center;justify-content:center;font-weight:800}
.intake{background:linear-gradient(135deg,#FFFDF8,#FFF6E3);border:1.5px solid #F2A900}
.intake .lead{font-size:12.5px;color:#8a6a1a;font-weight:700;margin-bottom:10px}
.formrow{display:flex;gap:8px;align-items:stretch}
.qbox{flex:1;min-width:0}
.qbox input{font:14px/1.4 inherit;padding:10px 14px;border:1.5px solid #E5DCC9;border-radius:10px;background:#fff;color:#2C2C2A;width:100%}
.qbox input:focus{outline:none;border-color:#F2A900}
.gobtn{cursor:pointer;border:0;background:#DA291C;color:#fff;font:800 14px inherit;padding:9px 24px;border-radius:10px;box-shadow:0 3px 10px rgba(218,41,28,.25);white-space:nowrap}
.gobtn:hover{filter:brightness(1.06)}
.hint{margin-top:8px;font-size:11.5px;color:#a08c5a}
.archrow{margin-top:12px;display:flex;gap:7px;flex-wrap:wrap;align-items:center}
.archrow .lab{font-size:11.5px;color:#8a7f68;font-weight:700}
.casechip{cursor:pointer;font:700 12px inherit;padding:5px 13px;border-radius:999px;border:1.5px solid #E5DCC9;background:#fff;color:#6b6350}
.casechip:hover{border-color:#F2A900}
.casechip.on{background:#2C2C2A;border-color:#2C2C2A;color:#FFC72C}
.intake-msg{margin-top:10px;font-size:12.5px;border-radius:9px;padding:9px 12px;display:none}
.intake-msg.show{display:block}
.intake-msg.ok{background:#EAF3DE;border:1px solid #97C459;color:#3B6D11}
.intake-msg.new{background:#E6F1FB;border:1px solid #85B7EB;color:#185FA5}
.intake-msg code{background:rgba(0,0,0,.07);border-radius:5px;padding:1px 6px;font:12px ui-monospace,monospace}
.casefile{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}
.cf{background:#FAF7EF;border:1px dashed #D8CDB4;border-radius:10px;padding:10px 12px}
.cf .k{font-size:11.5px;color:#8a7f68;font-weight:700}
.cf .v{font-size:13.5px;font-weight:600;margin-top:2px}
.cf .v.big{font-size:16px;color:#DA291C;font-weight:800}
.station{display:flex;align-items:center;gap:12px;background:#FAF7EF;border:1px solid #E5DCC9;border-radius:12px;padding:10px 12px;margin-top:8px}
.station.p-cheap{border-color:#F2A900;background:#FFF8E8;box-shadow:inset 3px 0 0 #F2A900}
.station.p-high{box-shadow:inset 3px 0 0 #DA291C}
.sno{width:26px;height:26px;border-radius:50%;background:#2C2C2A;color:#fff;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center;flex:0 0 26px}
.p-cheap .sno{background:#F2A900;color:#3a2c00}
.p-high .sno{background:#DA291C}
.sbody{flex:1;min-width:0}
.sname{font-weight:700;font-size:13.5px}
.smeta{font-size:12px;color:#8a7f68;margin-top:1px}
.sprice{font-size:17px;font-weight:800;font-family:ui-monospace,monospace}
.p-cheap .sprice{color:#B57B00}
.p-high .sprice{color:#DA291C}
.brow{display:flex;align-items:center;gap:10px;margin-top:9px}
.bname{width:210px;font-size:12.5px;font-weight:600;flex:0 0 210px;text-align:right}
.badge{font-size:10.5px;font-weight:800;padding:1px 7px;border-radius:999px;margin-left:6px;vertical-align:1px}
.badge.cheap{background:#F2A900;color:#3a2c00}
.badge.pricey{background:#DA291C;color:#fff}
.btrack{flex:1;height:22px;background:#F1EBDC;border-radius:6px;overflow:hidden}
.btrack i{display:block;height:100%;background:#C9A24B;border-radius:6px}
.brow.cheap .btrack i{background:#F2A900}
.brow.pricey .btrack i{background:#DA291C}
.bval{width:56px;font:700 14px ui-monospace,monospace;text-align:right}
.delta{margin-top:12px;background:#FFF3D6;border:1px solid #F2A900;border-radius:10px;padding:9px 13px;font-size:13px;font-weight:700;color:#7a5200}
.delta b{color:#DA291C;font-size:15px}
.note{font-size:11.5px;color:#8a7f68;margin-top:8px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin-top:4px}
.stat{background:#FAF7EF;border:1px solid #E5DCC9;border-radius:10px;padding:10px;text-align:center}
.stat .n{font-size:20px;font-weight:800;font-family:ui-monospace,monospace}
.stat .l{font-size:11.5px;color:#8a7f68;font-weight:600;margin-top:2px}
.verdict{text-align:center;padding:10px 0 4px}
.stamp{display:inline-block;border:3px solid #DA291C;color:#DA291C;font-weight:800;font-size:19px;padding:8px 26px;border-radius:12px;transform:rotate(-2deg);letter-spacing:1px;background:#fff}
.verdict .sub{margin-top:10px;font-size:13.5px;color:#6b6350}
.rules{counter-reset:r;list-style:none}
.rules li{counter-increment:r;position:relative;padding:7px 0 7px 34px;font-size:13px;border-bottom:1px dashed #E5DCC9}
.rules li:last-child{border-bottom:0}
.rules li::before{content:counter(r);position:absolute;left:0;top:8px;width:22px;height:22px;border-radius:50%;background:#2C2C2A;color:#fff;font-size:12px;font-weight:800;display:flex;align-items:center;justify-content:center}
.rules b{color:#DA291C}
details.ev{border:1px solid #E5DCC9;border-radius:10px;margin-top:7px;background:#fff}
details.ev summary{cursor:pointer;list-style:none;display:flex;align-items:center;gap:8px;padding:8px 12px;font-size:13px}
details.ev summary::-webkit-details-marker{display:none}
.kdot{width:18px;text-align:center;font-weight:800}
.kdot-success{color:#2E7D32}.kdot-info{color:#378ADD}.kdot-warning{color:#B57B00}
.seq{font:700 11px ui-monospace,monospace;color:#8a7f68;width:22px}
.ttl{font-weight:700}
.tool{margin-left:auto;font:11.5px ui-monospace,monospace;color:#8a7f68;background:#FAF7EF;border:1px solid #E5DCC9;border-radius:6px;padding:1px 7px}
.say{padding:0 12px 8px 38px;font-size:12.5px;color:#5b5340}
.raw{margin:0 12px 8px 38px}
.rawt{font-size:11px;font-weight:800;color:#8a7f68;margin-bottom:2px}
.raw pre{background:#FAF7EF;border:1px solid #E5DCC9;border-radius:8px;padding:8px 10px;font:11px/1.55 ui-monospace,monospace;overflow-x:auto;white-space:pre-wrap;word-break:break-all}
.ref{font:10.5px ui-monospace,monospace;color:#B4AE9C;padding:0 12px 9px 38px}
footer{margin-top:22px;text-align:center;font-size:11.5px;color:#8a7f68;line-height:1.9}
.repro{margin-top:10px;background:#2C2C2A;color:#F1EBDC;border-radius:10px;padding:10px 14px;font:12px/1.6 ui-monospace,monospace;overflow-x:auto;white-space:pre-wrap}
"""

BADGE = """<svg width="46" height="46" viewBox="0 0 24 24" aria-label="麦探长警长徽章">
  <path d="M12 0.8 L15.53 7.15 L22.65 8.54 L17.71 13.85 L18.59 21.06 L12 18 L5.41 21.06 L6.29 13.85 L1.35 8.54 L8.47 7.15 Z"
        fill="#FFC72C" stroke="#D89A00" stroke-width="0.6" stroke-linejoin="round"/>
  <circle cx="15.53" cy="7.15" r="0.55" fill="#FFC72C" stroke="#D89A00" stroke-width="0.3"/>
  <circle cx="17.71" cy="13.85" r="0.55" fill="#FFC72C" stroke="#D89A00" stroke-width="0.3"/>
  <circle cx="12" cy="18" r="0.55" fill="#FFC72C" stroke="#D89A00" stroke-width="0.3"/>
  <circle cx="6.29" cy="13.85" r="0.55" fill="#FFC72C" stroke="#D89A00" stroke-width="0.3"/>
  <circle cx="8.47" cy="7.15" r="0.55" fill="#FFC72C" stroke="#D89A00" stroke-width="0.3"/>
  <circle cx="12" cy="12" r="5.6" fill="#DA291C"/>
  <g transform="translate(12,12) scale(0.33) translate(-12,-12)">
    <path d="M17.243 3.006c2.066 0 3.742 8.714 3.742 19.478H24c0-11.588-3.042-20.968-6.766-20.968-2.127 0-4.007 2.81-5.248 7.227-1.241-4.416-3.121-7.227-5.231-7.227C3.031 1.516 0 10.888 0 22.476h3.014c0-10.763 1.658-19.47 3.724-19.47 2.066 0 3.741 8.05 3.741 17.98h2.997c0-9.93 1.684-17.98 3.75-17.98Z" fill="#FFC72C"/>
  </g>
</svg>"""

JS = """
(function(){
  var CASES = __CASES__;
  var CITIES = ["北京","上海","广州","深圳","杭州","成都","武汉","南京","苏州","天津","重庆","西安","长沙","郑州","青岛","厦门","福州","合肥","南昌","贵阳","昆明","南宁","佛山","东莞","宁波","无锡","大连","沈阳","哈尔滨","长春","石家庄","太原","济南","温州","黄冈","鄂州","珠海","中山","惠州","汕头","湛江","柳州","桂林","海口","三亚","兰州","银川","西宁","乌鲁木齐","呼和浩特","宜昌","襄阳","洛阳","开封","徐州","常州","南通","扬州","泰州","盐城","芜湖","蚌埠","遵义","绵阳","泸州","唐山","烟台","潍坊","临沂","台州","嘉兴","绍兴","金华","湖州","丽水","衢州","舟山"];
  var MEALS = ["巨无霸","麦香鱼","板烧鸡腿堡","麦辣鸡腿堡","麦辣鸡翅","不素之霸","双层深海鳕鱼堡","安格斯厚牛堡","培根蔬牛堡","吉士汉堡","薯条","麦乐鸡","甜筒","麦旋风","新地","脆薯饼","玉米杯","苹果片","三件套","套餐"];
  var STOPS = ["哪家","哪个","哪家店","便宜","怎么","怎样","如何","查询","查一下","一下","附近","麦当劳","麦探长","帮我","请问","我想","想要","比较","比价","想吃","吃一份","点一份","来一份","多少","哪里","哪","家","店","的","了","吗","呢","吧","啊","和","跟","在","有","卖"];
  function norm(s){ return (s||'').replace(/\\s+/g,'').replace(/[省市]$/,''); }
  function parse(raw){
    var s = (raw||'').replace(/\\s+/g,'').replace(/[？?！!。，,、]/g,'');
    var city = '';
    for (var i=0;i<CITIES.length;i++){ if (s.indexOf(CITIES[i])>=0){ city = CITIES[i]; break; } }
    // 目标餐品：菜单词表命中（长的优先）
    var target = '';
    var sorted = MEALS.slice().sort(function(a,b){return b.length-a.length;});
    for (var j=0;j<sorted.length;j++){
      if (s.indexOf(sorted[j])>=0){ target = sorted[j]; break; }
    }
    // 归档命中：关键词在输入里
    for (var k=0;k<CASES.length;k++){
      var c = CASES[k];
      if (s.indexOf(c.keyword)>=0){
        return {hit:c, city:city||norm(c.city), area:c.keyword,
                target:c.target||target||'巨无霸'};
      }
    }
    // 未归档：城市 + 目标剥离后，剩余前几字当作区域（尽力而为，标注"我的理解"）
    var rest = s;
    if (city) rest = rest.replace(city,'');
    if (target) rest = rest.replace(target,'');
    STOPS.forEach(function(w){ rest = rest.split(w).join(''); });
    var area = rest.slice(0,4);
    return {hit:null, city:city||'', area:area, target:target||'巨无霸'};
  }
  function showCase(key){
    CASES.forEach(function(c){
      var el = document.getElementById('case-'+c.key);
      if(el) el.style.display = (c.key===key) ? '' : 'none';
    });
    document.querySelectorAll('.casechip').forEach(function(b){
      b.classList.toggle('on', b.dataset.key===key);
    });
    window.scrollTo({top:0,behavior:'smooth'});
  }
  document.querySelectorAll('.casechip').forEach(function(b){
    b.onclick = function(){ showCase(b.dataset.key); setMsg('ok','已调档：'+b.textContent+'。'); };
  });
  function setMsg(cls, html){
    var m = document.getElementById('intakeMsg');
    m.className = 'intake-msg show '+cls;
    m.innerHTML = html;
  }
  document.getElementById('intakeForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    var raw = document.getElementById('fQ').value.trim();
    if(!raw){ setMsg('new','先得说个案子，比如「中关村 精选单人餐三件套哪家便宜」。'); return; }
    var p = parse(raw);
    if (p.hit){
      showCase(p.hit.key);
      setMsg('ok','已调档：'+p.hit.label+'（探长理解为：'+p.city+' '+p.area+' · '+p.target+'）。');
    } else {
      var where = (p.city||'某城') + (p.area ? p.area : '');
      var cityTxt = p.city || '<城市>';
      var areaTxt = p.area || (p.city ? p.city : '<区域>');
      setMsg('new','探长的理解：<b>'+where+'</b>附近 · <b>'+p.target+'</b>（默认方圆 3 km、最多 10 店）。'
        +'这一页是案卷回放，不回放实时数据——探长出勤需要真实数据通道（MCP Token 按参赛规则不进页面）。'
        +'装上 WorkBuddy Skill 后说一句话就真跑，或粘贴这条命令：<br/>'
        +'<code>python skills/mctrace/scripts/run_trace.py --detective '+cityTxt+' '+areaTxt+' '+p.target+' 3 10</code><br/>'
        +'跑完用 <code>python apps/detective/build_detective.py</code> 重新生成本页，新案卷自动归档。');
    }
  });
})();
"""

PAGE = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>麦探长 · 麦当劳物价侦探</title>
<link rel="icon" href="{BADGE_ICON or "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M12 0.8 L15.53 7.15 L22.65 8.54 L17.71 13.85 L18.59 21.06 L12 18 L5.41 21.06 L6.29 13.85 L1.35 8.54 L8.47 7.15 Z' fill='%23FFC72C' stroke='%23D89A00' stroke-width='0.6'/%3E%3Ccircle cx='12' cy='12' r='5.6' fill='%23DA291C'/%3E%3Cg transform='translate(12,12) scale(0.33) translate(-12,-12)'%3E%3Cpath d='M17.243 3.006c2.066 0 3.742 8.714 3.742 19.478H24c0-11.588-3.042-20.968-6.766-20.968-2.127 0-4.007 2.81-5.248 7.227-1.241-4.416-3.121-7.227-5.231-7.227C3.031 1.516 0 10.888 0 22.476h3.014c0-10.763 1.658-19.47 3.724-19.47 2.066 0 3.741 8.05 3.741 17.98h2.997c0-9.93 1.684-17.98 3.75-17.98Z' fill='%23FFC72C'/%3E%3C/g%3E%3C/svg%3E"}"/>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header class="top">
  <div class="logo">
    {BADGE_IMG or BADGE}
    <h1>麦探长<small>麦当劳物价侦探</small></h1>
  </div>
</header>

<section class="card intake">
  <h2><span class="no">台</span>接案台 · 报个案</h2>
  <div class="lead">说一句话就行——城市、地段、想查的餐品，探长自己领会；库里有的直接调档，没有的告诉你怎么让他真跑。</div>
  <form id="intakeForm" class="formrow">
    <div class="qbox"><input id="fQ" type="text" autocomplete="off"
      placeholder="比如：中关村 精选单人餐三件套哪家便宜？"/></div>
    <button class="gobtn" type="submit">探长出勤</button>
  </form>
  <div class="hint">默认方圆 3 km、最多 10 店（可在命令里改）· 例如：静安寺 麦香鱼 / 黄冈万达 巨无霸 / 深圳科技园 麦辣鸡腿堡</div>
  <div class="archrow"><span class="lab">或调阅已归档案卷：</span>{chips_html}</div>
  <div class="intake-msg" id="intakeMsg"></div>
</section>

{views_html}

<section class="card">
  <h2><span class="no">纪</span>办案纪律（写进代码，不是口号）</h2>
  <ul class="rules">
    <li><b>只汇报亲眼所见</b>：不在返回数据之外补全任何信息</li>
    <li><b>没线索就老实说</b>：各店同价就明言「无从比起」，不制造假价差</li>
    <li><b>同一形态才比价</b>：「麦香鱼」命中单品和套餐时分开比，不拿形态差异冒充跨店差价</li>
    <li><b>特殊店型单独标注</b>：快捷小站等不混入常规店比价</li>
    <li><b>每个数字可回溯</b>：点开案卷附录，看它取自哪个接口的哪个字段</li>
    <li><b>全程只读</b>：绝不触发下单、领券、抽奖</li>
  </ul>
</section>

<footer>
  麦探长 · 麦当劳程序员创意开发大赛参赛作品 · 独立开发，非麦当劳官方产品<br/>
  证据链引擎：McTrace（事实是一等公民，拟人化 ≠ 编造）· 餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准<br/>
  <a href="https://github.com/StrawberryTreea/mcdetective" style="color:#185FA5">GitHub 仓库 · 源码与案卷全公开</a> ·
  <span style="color:#DA291C;font-weight:700">这场比赛按 Star 排名——探长称职的话，上去点个 Star</span>
</footer>

</div>
<script>{JS.replace("__CASES__", case_meta)}</script>
</body>
</html>
"""

os.makedirs(HERE, exist_ok=True)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(PAGE)
print(f"麦探长办案页 -> {OUT}")
print(f"  归档 {len(cases)} 册: {', '.join(c['label'] for c in cases)}")
