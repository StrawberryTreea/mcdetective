"""
麦探长 · Live Story Studio 生成器（独立回放页）

读取 examples/traces 下所有真实 trace，内联进一个自包含的 live_story.html
（双击即可离线回放）。页面顶部带「场景」下拉，可在多个真实场景间切换。

它和 MCP App 片段共用 packages/studio_core.py 里的渲染内核：
本文件只负责「外壳」——场景下拉、播放控制、文件载入、GitHub Pages 落地页。

用法：
  python build_studio.py
产物：
  apps/studio/live_story.html
  docs/index.html   （GitHub Pages 落地页，含同一份回放）
"""
import os
import sys
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
TRACES_DIR = os.path.join(REPO, "examples", "traces")
OUT = os.path.join(HERE, "live_story.html")

# 让 `python build_studio.py` 也能找到共享内核（packages/studio_core.py）
for _p in (os.path.join(REPO, "packages"), os.path.join(REPO, "packages", "core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from studio_core import CORE_CSS, CORE_JS, TOOL_META  # noqa: E402

LABELS = {
    "jingan-breakfast": "① 静安寺早餐 · 点餐推荐",
    "points-steward": "② 积分资产盘点",
    "detective-patrol": "③ 麦探长 · 北京中关村比价",
    "detective-jingan": "④ 麦探长 · 上海静安寺比价",
    "detective-huanggang": "⑤ 麦探长 · 黄冈万达比价（同价案）",
    "减脂晚餐": "⑥ 黄冈万达 · 减脂晚餐",
}
ORDER = ["jingan-breakfast", "points-steward", "detective-patrol", "detective-jingan",
         "detective-huanggang", "减脂晚餐"]


def friendly_name(fname):
    base = fname[:-5] if fname.endswith(".json") else fname
    if base.startswith("real-"):
        base = base[5:]
    if base in LABELS:
        return LABELS[base]
    return base.replace("-", " ").title()


def load_traces():
    files = sorted(glob.glob(os.path.join(TRACES_DIR, "real-*.json")))
    scn = {}
    for f in files:
        try:
            with open(f, encoding="utf-8") as fh:
                t = json.load(fh)
        except Exception:
            continue
        base = os.path.basename(f)[:-5]
        if base.startswith("real-"):
            base = base[5:]
        scn[base] = t
    ordered = [k for k in ORDER if k in scn] + [k for k in scn if k not in ORDER]
    return scn, ordered


SHELL_CSS = r"""
*{box-sizing:border-box}
html,body{margin:0}
body{background:var(--bg);
  font:14px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}
.wrap{max-width:1080px;margin:0 auto;padding:18px 18px 56px}
header.top{display:flex;align-items:center;gap:11px;flex-wrap:wrap;
  padding:13px 17px;border-radius:16px;position:sticky;top:10px;z-index:20;overflow:hidden;
  background:linear-gradient(135deg,var(--red),#E8432F);
  box-shadow:0 8px 24px rgba(218,41,28,.28)}
header.top::after{content:"";position:absolute;left:0;right:0;bottom:0;height:6px;
  background:repeating-linear-gradient(90deg, rgba(255,255,255,.92) 0 13px, var(--amber) 13px 26px)}
.brand{font-weight:800;font-size:18px;letter-spacing:.2px;display:flex;align-items:center;gap:9px;color:#fff;
  font-family:"Fredoka",-apple-system,sans-serif}
.brand .dot{display:none}
.brand small{font-weight:600;color:rgba(255,255,255,.82);font-size:12px;font-family:-apple-system,"PingFang SC",sans-serif}
.chip{font-size:12px;padding:3px 10px;border-radius:999px;border:1px solid rgba(255,255,255,.4);
  color:#fff;background:rgba(255,255,255,.14);font-weight:700;font-family:ui-monospace,monospace}
.chip.real{color:#5a3a00;background:var(--amber);border-color:var(--amber)}
.chip.mock{color:#fff;background:rgba(0,0,0,.22);border-color:rgba(255,255,255,.3)}
.spacer{flex:1}
.controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
button.btn{cursor:pointer;border:1.5px solid rgba(255,255,255,.55);background:#fff;color:var(--red);
  padding:6px 12px;border-radius:10px;font-weight:800;font-size:13px;transition:.15s;font-family:inherit}
button.btn:hover{background:var(--amber-soft);border-color:#fff;transform:translateY(-1px)}
button.btn.primary{background:var(--amber);border-color:var(--amber);color:#5a3a00;box-shadow:0 3px 10px rgba(242,169,0,.4)}
button.btn.primary:hover{filter:brightness(1.05);transform:translateY(-1px)}
.seg{display:inline-flex;border:1.5px solid rgba(255,255,255,.55);border-radius:10px;overflow:hidden;background:#fff}
.seg button{border:0;background:#fff;padding:6px 12px;font-weight:800;font-size:13px;cursor:pointer;color:var(--muted);font-family:inherit}
.seg button.on{background:var(--amber);color:#5a3a00}
select{padding:6px 10px;border-radius:10px;border:1.5px solid rgba(255,255,255,.55);background:#fff;font-weight:700;font-size:13px;color:var(--ink);font-family:inherit;cursor:pointer}
.scnbox{display:inline-flex;align-items:center;gap:6px}
.scnbox label{font-size:12px;color:rgba(255,255,255,.85);font-weight:700}
.tipbar{margin:14px 0 0;padding:10px 14px;background:#fff;border:1px solid var(--line);
  border-left:4px solid var(--amber);border-radius:11px;color:#5b5346;font-size:12.5px;box-shadow:var(--shadow)}
.tipbar b{color:var(--red-deep)}
.progresswrap{margin-top:13px}
footer{margin-top:26px;color:var(--faint);font-size:12px;text-align:center;line-height:1.7}
.timeline{margin-top:14px}
.stat{margin-top:20px}
@media (max-width:640px){.fact .k{min-width:80px}}
"""

TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>麦探长 · Live Story Studio</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&display=swap" rel="stylesheet">
<style>__ALL_CSS__</style>
</head>
<body class="mctr">
<div class="wrap">
  <header class="top">
    <div class="brand"><span class="mlogo"><svg viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="6" fill="#DA291C"/><path d="M17.243 3.006c2.066 0 3.742 8.714 3.742 19.478H24c0-11.588-3.042-20.968-6.766-20.968-2.127 0-4.007 2.81-5.248 7.227-1.241-4.416-3.121-7.227-5.231-7.227C3.031 1.516 0 10.888 0 22.476h3.014c0-10.763 1.658-19.47 3.724-19.47 2.066 0 3.741 8.05 3.741 17.98h2.997c0-9.93 1.684-17.98 3.75-17.98Z" fill="#FFC72C"/></svg></span>麦探长 <small>Live Story Studio</small></div>
    <span class="chip" id="tid">trace…</span>
    <span class="chip real" id="mockchip">真实数据</span>
    <div class="spacer"></div>
    <div class="controls">
      <div class="scnbox"><label>场景</label><select id="scn"></select></div>
      <button class="btn primary" id="play">▶ 播放</button>
      <button class="btn" id="step">下一步</button>
      <button class="btn" id="replay">重播</button>
      <div class="seg" id="narrseg">
        <button data-n="friendly" class="on">俏皮</button>
        <button data-n="pro">专业</button>
      </div>
      <select id="speed" title="播放速度">
        <option value="1100">1×</option>
        <option value="650" selected>1.6×</option>
        <option value="350">3×</option>
      </select>
      <label class="btn" title="载入其他 trace.json">载入…<input id="file" type="file" accept=".json" hidden /></label>
    </div>
  </header>

  <div class="progresswrap"><div class="progress"><i id="bar"></i></div></div>
  <div class="tipbar">每一步都可以点：<b>点工具名</b>看它到底调了什么、返回了什么；<b>点来源路径</b>看这个数字取自返回结果里的哪个字段。</div>
  <div class="timeline" id="timeline"></div>

  <div class="result" id="result">
    <h3>结果与证据</h3>
    <div class="grid" id="resultGrid"></div>
    <div class="note" id="resultNote"></div>
  </div>

  <div class="stat" id="stat"></div>
  <footer>麦探长 · 把「工具调用成功」还原成「用户目标是否真的达成」。事实是一等公民，拟人化 ≠ 编造。</footer>
</div>

<div class="overlay" id="overlay"></div>
<aside class="lens" id="lens">
  <div class="lh"><b id="lensTitle">证据透镜</b><button class="x" id="lensClose">×</button></div>
  <div class="lb" id="lensBody"></div>
</aside>

<script id="embedded-traces" type="application/json">__SCENARIOS_JSON__</script>
<script id="embedded-tools" type="application/json">__TOOLS_JSON__</script>
<script>__CORE_JS__</script>
<script>
(function(){
  "use strict";
  var EMBED = JSON.parse(document.getElementById("embedded-traces").textContent);
  var TOOLS = JSON.parse(document.getElementById("embedded-tools").textContent);
  var SCENARIOS = EMBED.scenarios || {"默认": EMBED};
  var SCN_ORDER = EMBED.order || Object.keys(SCENARIOS);
  var SCN_LABELS = EMBED.labels || {};

  var ui = new 麦探长UI({
    tools: TOOLS,
    ids: {timeline:"timeline", result:"result", resultGrid:"resultGrid", resultNote:"resultNote",
          stat:"stat", bar:"bar"},
    emptyText: "没有可回放的事件。用右上角「载入…」选择一个 trace.json。"
  });

  var timer = null, playing = false;
  var timeline = document.getElementById("timeline");

  function currentKey(){ return document.getElementById("scn").value; }
  function currentTrace(){ return SCENARIOS[currentKey()]; }

  function paintTrace(t){
    document.getElementById("tid").textContent = t.traceId || "trace";
    var mc = document.getElementById("mockchip");
    mc.textContent = t.isMock ? "模拟数据" : "真实数据";
    mc.className = "chip " + (t.isMock ? "mock" : "real");
    ui.loadTrace(t);
    ui.renderStat();
  }

  function play(){ if(playing) return; if(ui.done()) ui.reset(); playing=true;
    document.getElementById("play").textContent = "⏸ 暂停";
    var sp = parseInt(document.getElementById("speed").value, 10);
    timer = setInterval(function(){ if(!ui.showNext()) stop(); }, sp); }
  function stop(){ playing=false; clearInterval(timer); timer=null; document.getElementById("play").textContent="▶ 播放"; }

  document.getElementById("play").onclick = function(){ playing ? stop() : play(); };
  document.getElementById("step").onclick = function(){ if(playing) stop(); ui.showNext(); };
  document.getElementById("replay").onclick = function(){ ui.reset(); play(); };
  document.getElementById("speed").onchange = function(){ if(playing){ stop(); play(); } };
  document.getElementById("narrseg").onclick = function(e){
    var b = e.target.closest("button"); if(!b) return;
    ui.setNarr(b.dataset.n);
    [].forEach.call(this.children, function(x){ x.classList.toggle("on", x===b); });
  };
  var scn = document.getElementById("scn");
  SCN_ORDER.forEach(function(k){
    if(!(k in SCENARIOS)) return;
    var o = document.createElement("option"); o.value = k; o.textContent = (SCN_LABELS[k] || k);
    scn.appendChild(o);
  });
  scn.onchange = function(){ stop(); paintTrace(currentTrace()); };
  document.getElementById("file").onchange = function(e){
    var f = e.target.files[0]; if(!f) return;
    var rd = new FileReader();
    rd.onload = function(){
      try{
        var t = JSON.parse(rd.result);
        SCENARIOS["__loaded__"] = t;
        var exists = [].some.call(scn.options, function(o){ return o.value === "__loaded__"; });
        if(!exists){
          var o2 = document.createElement("option"); o2.value="__loaded__"; o2.textContent="载入的 trace"; scn.appendChild(o2);
        }
        scn.value = "__loaded__"; stop(); paintTrace(t);
      }catch(err){ alert("JSON 解析失败：" + err.message); }
    };
    rd.readAsText(f);
  };

  paintTrace(currentTrace());
})();
</script>
</body>
</html>
"""

scn, order = load_traces()
labels = {k: friendly_name(k) for k in scn}
payload = {"scenarios": scn, "order": order, "labels": labels}
html = (TEMPLATE
        .replace("__ALL_CSS__", CORE_CSS + SHELL_CSS)
        .replace("__SCENARIOS_JSON__", json.dumps(payload, ensure_ascii=False))
        .replace("__TOOLS_JSON__", json.dumps(TOOL_META, ensure_ascii=False))
        .replace("__CORE_JS__", CORE_JS))

with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(html)
print(f"Studio -> {OUT}")
print(f"  场景: {', '.join(order)}")

# -------- 同步产出 GitHub Pages 落地页 docs/index.html（产品说明 + 同一份真实回放）--------
DOCS_DIR = os.path.join(REPO, "docs")
INTRO = """
<style>
  .hero{background:linear-gradient(135deg,#DA291C 0%,#E8432F 60%,#F2543B 100%);border-radius:20px;
    padding:30px 30px 26px;margin:14px 0 0;position:relative;overflow:hidden;color:#fff;
    box-shadow:0 14px 40px rgba(218,41,28,.3)}
  .hero::after{content:"";position:absolute;right:-60px;top:-90px;width:280px;height:280px;border-radius:50%;
    background:radial-gradient(circle,rgba(255,199,44,.22),transparent 70%);pointer-events:none}
  .hero::before{content:"";position:absolute;left:0;right:0;bottom:0;height:7px;
    background:repeating-linear-gradient(90deg, rgba(255,255,255,.92) 0 13px, var(--amber) 13px 26px)}
  .hero h1{margin:0 0 8px;font-size:26px;letter-spacing:.2px;font-family:"Fredoka",-apple-system,sans-serif;font-weight:700;display:flex;align-items:center}
  .hero h1::before{content:"";display:inline-block;width:24px;height:18px;margin-right:10px;flex:0 0 auto;background:var(--amber);
    -webkit-mask:var(--arch) center/contain no-repeat;mask:var(--arch) center/contain no-repeat}
  .hero .sub{color:rgba(255,255,255,.9);font-size:14px;margin-bottom:18px;line-height:1.8;max-width:760px}
  .hero .sub b{color:var(--amber)}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:11px}
  .pcard{background:rgba(255,255,255,.96);border-radius:13px;padding:14px 16px;box-shadow:0 6px 18px rgba(0,0,0,.12);border-top:3px solid var(--amber)}
  .pcard h4{margin:0 0 6px;font-size:14px;color:var(--red-deep);display:flex;align-items:center;gap:7px}
  .pcard h4 .picon{width:22px;height:22px;border-radius:7px;background:var(--amber-soft);color:#9a5a08;
    display:inline-flex;align-items:center;justify-content:center;font-size:13px;flex:0 0 22px;font-weight:800}
  .pcard p{margin:0;font-size:12.5px;color:#5b5346;line-height:1.75}
  .pcard code{background:#FBF1DC;border-radius:5px;padding:1px 5px;font-size:11px;color:#8a5a00}
  .tagrow{margin-top:14px;display:flex;gap:7px;flex-wrap:wrap}
  .tag{font-size:11.5px;font-weight:800;padding:5px 11px;border-radius:999px;border:1.5px solid rgba(255,255,255,.5);
    background:rgba(255,255,255,.14);color:#fff}
  .tag.red{background:var(--amber);border-color:var(--amber);color:#5a3a00}
</style>
<section class="hero">
  <h1>麦探长 · 让每一次麦当劳 MCP 调用都可被验证</h1>
  <div class="sub">一个把「工具调用成功」还原成「<b>用户目标是否真的达成</b>」的 MCP Trace 与证据分析工具。面向普通用户，它是会边做边说的助手；面向开发者，它是一份对业务结果负责的证据链。</div>
  <div class="cards">
    <div class="pcard"><h4><span class="picon">①</span>事实归一化</h4><p>每次调用抽取为「事实」，并标注来源路径（如 <code>$.data.availablePoint</code>），可回溯、可点开。</p></div>
    <div class="pcard"><h4><span class="picon">②</span>规则校验</h4><p>预算、热量、临期积分等约束被真正执行；不满足时给警告，而不是假装成功。</p></div>
    <div class="pcard"><h4><span class="picon">③</span>诚实降级</h4><p>算价接口没返回明细时，明确标注「菜单标价」来源，绝不编造。</p></div>
    <div class="pcard"><h4><span class="picon">④</span>住在对话里</h4><p>既是能渲染进聊天界面的 MCP App（MCP Apps / SEP-1865），也能离线双击打开做深度分析。</p></div>
  </div>
  <div class="tagrow">
    <span class="tag red">0 写操作 · 全程只读</span>
    <span class="tag">工具调用成功 ≠ 用户目标达成</span>
    <span class="tag">拟人化 ≠ 编造思考</span>
    <span class="tag">真实 MCP 数据（非模拟）</span>
  </div>
</section>
"""
docs_html = html.replace('<div class="progresswrap">', INTRO + '<div class="progresswrap">')
os.makedirs(DOCS_DIR, exist_ok=True)
with open(os.path.join(DOCS_DIR, "index.html"), "w", encoding="utf-8", newline="\n") as f:
    f.write(docs_html)
print(f"Pages   -> {os.path.join(DOCS_DIR, 'index.html')}")
