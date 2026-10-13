"""
McTrace · 单次运行的独立回放页生成器

宿主不渲染 MCP App 界面时，这是用户能看到的东西：一个自包含 HTML，
双击即开，离线可用，每一步都能点开看原始调用与返回。

设计要点：
- 完全自包含（CSS/JS/数据全内联），不依赖任何外部资源与网络
- 证据透镜：点工具名 / 点来源路径 / 点实体名都能展开真实返回片段
- 顶部给出结论与关键约束，底部写清边界与数据来源
"""
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))

TOOL_CN = {
    "query-nearby-stores": "找门店", "query-meals": "拉菜单",
    "list-nutrition-foods": "核热量", "query-meal-detail": "拆餐品构成",
    "query-store-coupons": "查门店券", "available-coupons": "查账户券",
    "calculate-price": "算价", "query-my-account": "查积分余额",
    "query-lottery-info": "查抽奖", "query-my-prizes": "查奖品",
    "order-list": "查历史订单", "query-survey-coupon": "查奖券",
    "mall-points-products": "查积分商城", "campaign-calendar": "查活动",
    "mall-create-order": "查商城订单", "mall-order-detail": "查商城订单明细",
    "mall-order-list": "查商城订单列表", "query-order": "查订单",
    "user-request": "解析你的要求", "mctrace:rule": "规则校验",
    "summary-composer": "整理结果", "mctrace:runner": "执行",
}
ICON = {"warning": "⚠", "success": "✓", "error": "✗", "degraded": "≈"}
STATUS = {"success": "成功", "warning": "告警", "error": "失败",
          "degraded": "降级", "info": "信息", "failed": "失败"}

CSS = r"""
*{box-sizing:border-box}
body{margin:0;background:#f4f6f8;color:#1b1f27;
  font:14px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.wrap{max-width:920px;margin:0 auto;padding:22px 20px 60px}

.hero{background:#fff;border:1px solid #e5e8ee;border-radius:14px;padding:20px 22px;
  margin-bottom:16px;box-shadow:0 1px 2px rgba(18,22,33,.05)}
.brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:14px;margin-bottom:12px}
.brand .dot{width:10px;height:10px;border-radius:50%;background:#E4002B;
  box-shadow:0 0 0 3px rgba(228,0,43,.12)}
.brand .tid{font-weight:400;font-size:11.5px;color:#98a1af}
.hero h1{margin:0 0 10px;font-size:19px;line-height:1.55}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
.chip{font-size:11.5px;padding:3px 10px;border-radius:999px;border:1px solid #e5e8ee;
  background:#fafbfc;color:#6d7683}
.chip.ok{color:#0a7d3c;border-color:#c6e8d3;background:#edfaf2}
.chip.warn{color:#b3261e;border-color:#f3c2bd;background:#fdecea}
.chip.mock{color:#b3261e;border-color:#f3c2bd;background:#fdecea}

.notice{background:#fff;border:1px solid #e5e8ee;border-left:4px solid #FFC72C;
  border-radius:11px;padding:12px 14px;margin-bottom:16px;font-size:13px;color:#5b5346}
.notice b{color:#1b1f27}
.notice.assumption{border-left-color:#2456c9}
.notice.assumption b{color:#2456c9}

.sec{margin:22px 0 12px;font-size:14px;font-weight:700;color:#1b1f27}
.sec small{font-weight:400;color:#98a1af;font-size:12px;margin-left:8px}

.ev{background:#fff;border:1px solid #e5e8ee;border-left-width:3px;border-radius:12px;
  padding:13px 16px;margin-bottom:10px;box-shadow:0 1px 2px rgba(18,22,33,.05)}
.ev.k-info{border-left-color:#d8dde5}
.ev.k-warning{border-left-color:#c9820f}
.ev.k-success{border-left-color:#1f9d55}
.ev.k-error{border-left-color:#E4002B}
.ev.k-degraded{border-left-color:#6f52b8}
.ehead{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:7px}
.seq{font-size:11px;font-weight:700;color:#fff;background:#98a1af;padding:1px 7px;border-radius:6px}
.ev.k-warning .seq{background:#c9820f}.ev.k-success .seq{background:#1f9d55}
.ev.k-error .seq{background:#E4002B}.ev.k-degraded .seq{background:#6f52b8}
.etitle{font-size:14px;font-weight:700}
.badge{font-size:11px;padding:1px 8px;border-radius:999px;border:1px solid #e5e8ee;
  background:#fafbfc;color:#6d7683}
.badge.warn{color:#b3261e;border-color:#f3c2bd;background:#fdecea}
.badge.degraded{color:#6f52b8;border-color:#d9cdf0;background:#f6f2fd}
.badge.error{color:#E4002B;border-color:#f3c2bd;background:#fdecea}
.ts{margin-left:auto;font-size:11px;color:#98a1af}

.toolbtn{cursor:pointer;border:1px dashed #b9c4d6;background:#f6f8fb;color:#2456c9;
  padding:2px 9px;border-radius:8px;font:11.5px/1.6 ui-monospace,Menlo,Consolas,monospace;
  margin:0 6px 8px 0;display:inline-block;transition:.14s}
.toolbtn:hover{border-color:#2456c9;background:#eef3fe}
.toolbtn.local{border-style:dotted;color:#6d7683;cursor:default}
.toolbtn.local:hover{background:#f6f8fb;border-color:#b9c4d6}

.say{color:#3c4450;margin-bottom:9px}
.facts{display:flex;flex-direction:column;gap:5px;margin-top:4px}
.f{display:flex;gap:9px;align-items:baseline;font-size:12.5px;flex-wrap:wrap}
.f .k{color:#6d7683;min-width:118px}
.f .v{font-weight:600;color:#1b1f27}
.srcbtn{cursor:pointer;border:none;background:#f2f4f7;color:#5a6675;border-radius:5px;
  padding:1px 6px;font:11px/1.6 ui-monospace,Menlo,Consolas,monospace;transition:.14s}
.srcbtn:hover{background:#2456c9;color:#fff}
.srcbtn.nosrc{cursor:default;color:#98a1af}
.srcbtn.nosrc:hover{background:#f2f4f7;color:#98a1af}

.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px}
.rcell{border:1px solid #e5e8ee;border-radius:10px;padding:10px 12px;background:#fff}
.rcell .l{font-size:11px;color:#98a1af;margin-bottom:3px}
.rcell .v{font-size:16px;font-weight:700;color:#1b1f27}
.rcell.good .v{color:#1f9d55}.rcell.warn .v{color:#c9820f}

details.raw{margin-top:7px}
details.raw>summary{cursor:pointer;font-size:11.5px;color:#2456c9;outline:none}
details.raw pre{margin:7px 0 0;background:#1b1f27;color:#e6eaf0;padding:11px 13px;
  border-radius:9px;font-size:11.5px;line-height:1.6;overflow-x:auto;max-height:340px;
  white-space:pre-wrap;word-break:break-all}

.foot{margin-top:26px;padding-top:14px;border-top:1px solid #e5e8ee;
  font-size:11.5px;color:#98a1af;line-height:1.8}
.lens{position:fixed;top:0;right:0;width:min(520px,100%);height:100%;background:#fff;
  box-shadow:-8px 0 28px rgba(18,22,33,.14);transform:translateX(100%);
  transition:transform .22s;z-index:50;display:flex;flex-direction:column}
.lens.on{transform:none}
.lens .lh{display:flex;align-items:center;gap:10px;padding:14px 16px;
  border-bottom:1px solid #e5e8ee}
.lens .lh b{font-size:13.5px}
.lens .x{margin-left:auto;cursor:pointer;border:1px solid #e5e8ee;background:#fff;
  width:26px;height:26px;border-radius:7px;font-size:15px;color:#6d7683}
.lens .x:hover{background:#f4f6f8}
.lens .lb{padding:14px 16px;overflow:auto;flex:1;font-size:12.5px}
.lens pre{background:#1b1f27;color:#e6eaf0;padding:11px 13px;border-radius:9px;
  font-size:11.5px;line-height:1.6;overflow-x:auto;max-height:none;
  white-space:pre-wrap;word-break:break-all;margin:7px 0}
.ov{position:fixed;inset:0;background:rgba(18,22,33,.28);display:none;z-index:49}
.ov.on{display:block}
@media (max-width:600px){ .ts{margin-left:0} .f .k{min-width:auto} }
"""

JS = r"""
(function(){
  function pretty(o){
    try{ return JSON.stringify(o, null, 2); }
    catch(e){ return String(o); }
  }
  var lens = document.getElementById("lens"), ov = document.getElementById("ov");
  function openLens(title, html){
    document.getElementById("lensTitle").textContent = title;
    document.getElementById("lensBody").innerHTML = html;
    lens.classList.add("on"); ov.classList.add("on");
  }
  function closeLens(){ lens.classList.remove("on"); ov.classList.remove("on"); }
  document.getElementById("lensClose").onclick = closeLens;
  ov.onclick = closeLens;
  document.addEventListener("keydown", function(e){ if(e.key === "Escape") closeLens(); });

  window.mcShowRaw = function(tool, which){
    var card = this;
    var raw = card.getAttribute("data-" + which) || "（这一步没有原始返回：本机规则/叙述步骤）";
    openLens(tool + " · " + (which === "req" ? "请求参数" : "原始返回"),
             "<p style='color:#6d7683;margin:0 0 6px'>这部分是麦当劳 MCP 的真实返回，未经加工；"
             + "地址等敏感字段已脱敏。</p><pre>" + raw.replace(/[<>&]/g, function(c){
               return ({'<':"&lt;",'>':"&gt;",'&':"&amp;"})[c]; }) + "</pre>");
  };
  window.mcShowPath = function(path, val){
    openLens("这个数字从哪来",
      "<p style='margin:0 0 8px'>字段路径：<span class='mono' style='background:#f2f4f7;"
      + "padding:2px 7px;border-radius:5px'>" + path + "</span></p>"
      + "<p style='margin:0 0 6px;color:#6d7683'>取到的值</p>"
      + "<pre>" + String(val).replace(/[<>&]/g, function(c){
          return ({'<':"&lt;",'>':"&gt;",'&':"&amp;"})[c]; }) + "</pre>");
  };
  window.mcShowEnt = function(name, role){
    openLens("实体 · " + name,
      "<p style='margin:0 0 6px;color:#6d7683'>它在本次追踪中的角色</p>"
      + "<pre>" + role + "</pre>");
  };
})();
"""


def _esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _trunc(obj, limit=4000):
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    if len(s) > limit:
        s = s[:limit] + "\n… （已截断，完整内容用 mctrace_get_summary 取）"
    return _esc(s)


def render(trace, title=None):
    """把一条 trace 渲染成自包含 HTML 字符串。"""
    events = trace.get("events") or []
    last = events[-1] if events else {}

    res = None
    for ev in reversed(events):
        # response 就是 {"result": {...}}，不要再多取一层
        r = (ev.get("response") or {}).get("result")
        if isinstance(r, dict) and r.get("item"):
            res = r
            break

    head = ((last.get("say") or {}).get("friendly") or "").strip()
    goal = trace.get("goal")
    if goal is None:
        for ev in events:
            for f in (ev.get("facts") or []):
                if f.get("key") == "goal":
                    goal = "fatloss" if "减脂" in str(f.get("value")) else "satiety"

    # ---- 顶部 ----
    chips = []
    if trace.get("isMock"):
        chips.append('<span class="chip mock">⚠ 模拟数据</span>')
    else:
        chips.append('<span class="chip ok">真实麦当劳 MCP 调用</span>')
    if goal:
        chips.append('<span class="chip">目标：%s</span>'
                     % ("减脂低卡" if goal == "fatloss" else "常规顶饱"))
    chips.append('<span class="chip">%d 步</span>' % len(events))
    if trace.get("generatedAt"):
        chips.append('<span class="chip">%s</span>' % _esc(trace["generatedAt"]))

    H = ['<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         '<title>%s</title><style>%s</style></head><body>' % (_esc(title or "McTrace 回放"), CSS),
         '<div class="wrap">',
         '<div class="hero"><div class="brand"><span class="dot"></span>McTrace · 麦搭子'
         '<span class="tid mono">%s</span></div>' % _esc(trace.get("traceId", "")),
         '<h1>%s</h1>' % (_esc(head) or "这次没能跑出结论，详见下方过程。"),
         '<div class="chips">%s</div></div>' % "".join(chips)]

    # ---- 假设声明 ----
    if goal == "fatloss":
        H.append('<div class="notice assumption"><b>「减脂」是我替你理解的，不是你原话。</b>'
                 '我的做法是：在预算和热量上限都通过的前提下，取热量最低的正餐单品。'
                 '如果理解偏了（比如你想吃热的、不想要汉堡、想吃饱），说一声我按你的重来。'
                 '下面的备选都来自本次菜单里真实存在的单品。</div>')

    # ---- 关键约束 ----
    if res:
        cells = []
        def cell(label, val, cls=""):
            cells.append('<div class="rcell %s"><div class="l">%s</div><div class="v">%s</div></div>'
                         % (cls, _esc(label), _esc(val)))
        for k, label, cls in (("store", "门店", ""), ("item", "推荐", ""),
                              ("payableYuan", "总价", "good"), ("kcal", "热量 kcal", "good")):
            if res.get(k) is not None:
                cell(label, res[k], cls)
        if res.get("rule"):
            cell("选品规则", res["rule"][:22] + ("…" if len(str(res["rule"])) > 22 else ""))
        alts = res.get("alternatives")
        if alts:
            cell("备选", "、".join(alts)[:40])
        if cells:
            H.append('<div class="sec">关键结论<small>数字均可点下方「过程」核对来源</small></div>')
            H.append('<div class="grid">%s</div>' % "".join(cells))

    # ---- 过程 ----
    H.append('<div class="sec">执行过程<small>点工具名看原始请求/返回，点来源路径看字段取自哪里</small></div>')
    for ev in events:
        kind = ev.get("kind") or "info"
        st = ev.get("status") or "info"
        tool = ev.get("tool") or ""
        req, resp = ev.get("request"), ev.get("response")
        is_local = not (req or resp)

        H.append('<div class="ev k-%s" data-req="%s" data-res="%s">' % (
            kind, _trunc(req) if req else "", _trunc(resp) if resp else ""))

        badge = STATUS.get(st, st)
        if st in ("warning", "error", "degraded"):
            badge = '<span class="badge %s">%s</span>' % (st, badge)
        else:
            badge = '<span class="badge">%s</span>' % badge
        H.append('<div class="ehead"><span class="seq">%s</span><span class="etitle">%s</span>'
                 '%s<span class="ts mono">%s</span></div>'
                 % (ev.get("seq", ""), _esc(ev.get("title") or TOOL_CN.get(tool, tool)),
                    badge, _esc(ev.get("ts", ""))))

        if is_local:
            H.append('<button class="toolbtn local" title="本机步骤，没有调用麦当劳接口">%s'
                     '<span style="font-family:inherit;margin-left:6px">本机步骤</span></button>'
                     % _esc(tool))
        else:
            H.append('<button class="toolbtn" onclick="mcShowRaw.call(this,\'%s\',\'req\')">%s</button>'
                     '<button class="toolbtn" onclick="mcShowRaw.call(this,\'%s\',\'res\')">%s'
                     '<span style="font-family:inherit;margin-left:6px">查看原始调用 ›</span></button>'
                     % (_esc(tool), _esc(tool), _esc(tool), _esc(TOOL_CN.get(tool, ""))))

        H.append('<div class="say">%s</div>' % _esc((ev.get("say") or {}).get("friendly", "")))

        ents = ev.get("entities") or {}
        if ents:
            chips_e = []
            for name, role in list(ents.items())[:6]:
                chips_e.append('<button class="srcbtn" onclick="mcShowEnt(\'%s\',\'%s\')">%s ›</button>'
                               % (_esc(name), _esc(role), _esc(str(name)[:16])))
            H.append('<div style="margin:2px 0 8px">%s</div>' % "".join(chips_e))

        facts = ev.get("facts") or []
        if facts:
            rows = []
            for f in facts:
                sp = f.get("sourcePath")
                v = f.get("value")
                if sp:
                    sb = ('<button class="srcbtn" onclick="mcShowPath(\'%s\',\'%s\')">%s</button>'
                          % (_esc(sp), _esc(v), _esc(sp)))
                else:
                    sb = '<span class="srcbtn nosrc">%s</span>' % _esc(f.get("source") or "本机推导")
                rows.append('<div class="f"><span class="k">%s</span><span class="v">%s</span>%s</div>'
                            % (_esc(f.get("key")), _esc(v), sb))
            H.append('<div class="facts">%s</div>' % "".join(rows))

        if ev.get("rule"):
            r = ev["rule"]
            H.append('<div style="margin-top:7px;font-size:12px;color:#c9820f">规则 %s：%s%s</div>'
                     % (_esc(r.get("id", "")),
                        "通过" if r.get("pass") else "未通过",
                        ("" if r.get("pass") else "（超出 %s）" % _esc(
                            r.get("deltaYuan") if r.get("deltaYuan") is not None
                            else r.get("deltaKcal")))))
        H.append("</div>")

    # ---- 边界 ----
    H.append('<div class="foot">'
             '数据来自麦当劳 MCP 实时只读调用。算价接口未返回明细时，已标注来源为菜单标价，不假装算价成功；'
             '营养表未覆盖的在售单品不参与推荐；地址门牌已脱敏。<br>'
             '全程只读：未调用 create-order / draw-lottery / auto-bind-coupons 等任何下单、抽奖、领券、兑换写操作。<br>'
             'McTrace · 工具调用成功 ≠ 用户目标达成。追踪号 %s</div>'
             % _esc(trace.get("traceId", "")))
    H.append("</div>")

    H.append('<div class="ov" id="ov"></div>'
             '<aside class="lens" id="lens"><div class="lh"><b id="lensTitle">证据透镜</b>'
             '<button class="x" id="lensClose">×</button></div>'
             '<div class="lb" id="lensBody"></div></aside>')
    H.append("<script>%s</script></body></html>" % JS)
    return "\n".join(H)


def write(trace, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    html = render(trace)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    return out_path


if __name__ == "__main__":
    import sys
    tr = json.load(open(sys.argv[1], encoding="utf-8"))
    print(write(tr, sys.argv[2] if len(sys.argv) > 2 else "trace.html"))