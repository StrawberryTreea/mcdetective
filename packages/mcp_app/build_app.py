"""
McTrace MCP App · 可嵌入对话的 Live Story 片段（生成器）

产出 packages/mcp_app/assets/live_story_app.html：
一段 **单个自包含 HTML**，宿主把它塞进沙箱 iframe，就有了和独立 Studio 完全一样的
可点击 Live Story（共用 packages/studio_core.py 的渲染内核）。

外壳差异只有三处：
1. 没有 header / 场景下拉 / 文件载入（这些属于独立 Studio）；
2. 数据来自宿主而非内置：兼容两种通道
   - MCP Apps（SEP-1865）：ui/notifications/tool-result 的 structuredContent
   - OpenAI Apps SDK：window.openai.toolOutput
   拿不到数据时给诚实降级面板，不假装成功；
3. 多一个「深度分析」出口：向宿主发 ui/message / ui/open-link，
   把用户带回独立 Studio（兼容后备 + 深度分析入口）。

用法：
  python build_app.py                 # 生成 assets/live_story_app.html
  from build_app import render_html   # 被 server.py 直接调用
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
CORE_DIR = os.path.join(REPO, "packages")
for _p in (CORE_DIR, os.path.join(CORE_DIR, "core")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from studio_core import CORE_CSS, CORE_JS, TOOL_META  # noqa: E402

ASSETS = os.path.join(HERE, "assets")

APP_CSS = r"""
html,body{margin:0}
body{background:transparent}
.app{max-width:100%;padding:2px 2px 6px}
.apphead{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:11px;
  padding:8px 11px;border-radius:13px;background:linear-gradient(135deg,var(--red),#E8432F);
  box-shadow:0 4px 14px rgba(218,41,28,.22);position:relative;overflow:hidden}
.apphead::after{content:"";position:absolute;left:0;right:0;bottom:0;height:5px;
  background:repeating-linear-gradient(90deg, rgba(255,255,255,.92) 0 12px, var(--amber) 12px 24px)}
.apphead .brand{font-weight:800;font-size:15px;display:flex;align-items:center;gap:7px;color:#fff;
  font-family:"Fredoka",-apple-system,sans-serif}
.apphead .brand .dot{display:none}
.apphead .tid{font-size:11.5px;color:rgba(255,255,255,.9);font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.chip.real{color:#5a3a00;background:var(--amber);border-color:var(--amber)}
.chip.mock{color:#fff;background:rgba(0,0,0,.22);border-color:rgba(255,255,255,.3)}
.chip{font-size:11px;padding:2px 9px;border-radius:999px;border:1px solid rgba(255,255,255,.4);background:rgba(255,255,255,.16);color:#fff;font-weight:700;font-family:ui-monospace,monospace}
.spacer{flex:1}
.appacts{display:flex;gap:6px;flex-wrap:wrap}
.appacts button{cursor:pointer;border:1.5px solid rgba(255,255,255,.6);background:#fff;color:var(--red);
  padding:5px 11px;border-radius:9px;font-weight:800;font-size:12px;font-family:inherit;transition:.14s}
.appacts button:hover{border-color:#fff;background:var(--amber-soft);transform:translateY(-1px)}
.appacts button:disabled{opacity:.5;cursor:default;transform:none}
.tipbar{margin:0 0 11px;padding:9px 12px;background:#fff;border:1px solid var(--line);
  border-left:4px solid var(--amber);border-radius:10px;color:#5b5346;font-size:12.5px}
.tipbar b{color:var(--red-deep)}
.livenote{margin:-4px 0 11px;font-size:12px;color:var(--muted);min-height:16px}
.livenote:empty{display:none}

  /* ===== 启动台：零参数入口的落地视图，交互全在这里完成 ===== */
  #launcher .lch{max-width:660px}
  .lch-hero h2{margin:0 0 6px;font-size:17px;color:var(--ink);letter-spacing:.2px}
  .lch-hero p{margin:0 0 14px;color:var(--muted);font-size:13px;line-height:1.7}
  .lch-hero b{color:var(--ink)}
  .lch-scenes{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
  .scene{display:block;cursor:pointer}
  .scene input{position:absolute;opacity:0;pointer-events:none}
  .sc-in{display:block;padding:11px 13px;border:1px solid var(--line);border-radius:11px;
    background:#fff;transition:.14s}
  .sc-in b{display:block;font-size:13.5px;color:var(--ink);margin-bottom:3px}
  .sc-in i{display:block;font-style:normal;font-size:11.5px;color:var(--faint);line-height:1.5}
  .scene input:checked + .sc-in{border-color:var(--red);background:#fff5f6;box-shadow:0 0 0 2px rgba(218,41,28,.12)}
  .scene input:checked + .sc-in b{color:var(--red)}
  .lch-form{display:grid;gap:10px;margin-bottom:13px}
  .row2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .lch-form label{display:block;font-size:11.5px;color:var(--muted);font-weight:600}
  .lch-form .req{color:var(--red)}
  .lch-form input,.lch-form select{width:100%;box-sizing:border-box;margin-top:4px;
    padding:8px 10px;border:1px solid var(--line);border-radius:9px;background:#fff;
    font:13px inherit;color:var(--ink)}
  .lch-form input:focus,.lch-form select:focus{outline:0;border-color:var(--red);
    box-shadow:0 0 0 3px rgba(218,41,28,.1)}
  .lch-go{display:flex;align-items:center;gap:11px;flex-wrap:wrap}
  .lch-go .primary{cursor:pointer;border:0;background:var(--red);color:#fff;padding:9px 18px;
    border-radius:10px;font:600 13.5px inherit;transition:.14s}
  .lch-go .primary:hover{background:#b8231a}
  .lch-go .primary:disabled{opacity:.45;cursor:default}
  .lch-hint{font-size:11.5px;color:var(--faint)}
  .lch-hint b{color:var(--red)}
  .lch-hint.warn{color:var(--amber);font-weight:600}
  .lch-readonly{margin-top:14px;padding:9px 11px;background:#f7f9fb;border:1px solid var(--line);
    border-radius:9px;font-size:11.5px;color:var(--muted);line-height:1.65}
  .lch-readonly b{color:var(--ink)}
  @media (max-width:520px){
    .lch-scenes,.row2{grid-template-columns:1fr}
  }
.fallback{border:1.5px dashed #E0D2BC;border-radius:13px;background:#FFFDF8;padding:16px 18px;color:var(--muted);font-size:13px}
.fallback h4{margin:0 0 7px;font-size:14px;color:var(--ink)}
.fallback code{background:#FBF1DC;border-radius:5px;padding:1px 5px;font-size:12px;color:#8a5a00}
.appfoot{margin-top:11px;color:var(--faint);font-size:11.5px;line-height:1.6}
.timeline{display:flex;flex-direction:column;gap:10px}
.stat{margin-top:10px}
"""

APP_JS = r"""
(function(){
  "use strict";
  var ui = new McTraceUI({
    tools: window.__MCTRACE_TOOLS__ || {},
    ids: {timeline:"timeline", result:"result", resultGrid:"resultGrid", resultNote:"resultNote",
          bar:"bar"},
    emptyText: "这次没有抓到事件。"
  });
  var STUDIO_PATH = window.__MCTRACE_STUDIO__ || "";
  var got = false, rpcId = 0, hostHeard = false;

  var fallback = document.getElementById("fallback");
  var traceIdEl = document.getElementById("tid");
  var mockEl = document.getElementById("mockchip");
  var btnToggle = document.getElementById("btnToggle");
  var btnDeep = document.getElementById("btnDeep");
  var deepHint = document.getElementById("deepHint");

  /* ---------- 与宿主通信：全部走 postMessage + 可选 window.openai ---------- */
  function host(){
    // 宿主页面优先；在部分实现里 app 的 parent 才是桥接方
    try { return window.parent && window.parent !== window ? window.parent : window.opener || null; }
    catch(e){ return null; }
  }
  function post(msg){
    var h = host();
    try { if (h) h.postMessage(msg, "*"); } catch(e){}
  }
  function notify(method, params){
    post({jsonrpc:"2.0", method:method, params:params||{}});
  }
  // 向回话里塞一句话（让模型去开独立 Studio）；两种 dialect 都尝试
  function sendFollowup(text){
    try{
      if (window.openai && typeof window.openai.sendFollowupMessage === "function"){
        window.openai.sendFollowupMessage(text);
        return true;
      }
    }catch(e){}
    notify("ui/message", {role:"user", content:[{type:"text", text:text}]});
    return true;
  }

  /* ---------- 数据接入 ---------- */
  var TERMINAL = {completed:1, failed:1, cancelled:1, unknown:1};
  var mode = "idle";            // idle | live | replay
  var pending = {};             // rpcId -> callback（等宿主的 resources/read 回包）
  var pollTimer = null, pollFails = 0, lastSeq = 0;

  function pickTrace(payload){
    if(!payload) return null;
    if(payload.events) return payload;                                  // 直接就是 trace
    if(payload.trace && payload.trace.events) return payload.trace;     // {trace:{...}}
    if(payload.structuredContent && payload.structuredContent.events) return payload.structuredContent;
    if(payload.result && payload.result.structuredContent && payload.result.structuredContent.events){
      return payload.result.structuredContent;
    }
    return null;
  }
  function markMock(t){
    mockEl.textContent = t && t.isMock ? "模拟数据" : "真实数据";
    mockEl.className = "chip " + (t && t.isMock ? "mock" : "real");
  }
  function setMode(m){
    mode = m;
    var tag = document.getElementById("modechip");
    if(tag){
      tag.textContent = (m === "live") ? "实时 · 边跑边长"
                      : (m === "replay") ? "回放 · 已跑完" : "等待数据";
      tag.className = "chip " + (m === "live" ? "real" : "");
    }
  }
  function pickScoped(payload){
    if(!payload) return null;
    var c = payload.structuredContent || payload.result || payload;
    if(c && c.view === "launcher") return c;
    if(payload.result && payload.result.structuredContent
       && payload.result.structuredContent.view === "launcher"){
      return payload.result.structuredContent;
    }
    return null;
  }
  function ingestLauncher(sc){
    got = true;
    fallback.style.display = "none";
    traceIdEl.textContent = "待输入";
    markMock({isMock: !!sc.isMock});
    setMode("idle");
    showLauncher();
    return true;
  }
  function ingest(payload){
    if(ingestLauncher(pickScoped(payload))) return true;
    var t = pickTrace(payload);
    if(!t) return false;
    got = true;
    fallback.style.display = "none";
    traceIdEl.textContent = t.traceId || "trace";
    markMock(t);
    ui.loadTrace(t);
    if(typeof ui.renderStat === "function") ui.renderStat();
    ui.revealAll();
    btnToggle.disabled = false;
    return true;
  }

  /* ---- 实时模式：工具只给了 traceId，事件要按 seq 增量拉 ---- */
  function ingestStart(sc){
    var uri = sc.snapshotUri || ("mctrace://runs/" + sc.traceId);
    got = true;
    fallback.style.display = "none";
    traceIdEl.textContent = sc.traceId || "trace";
    markMock({isMock: !!sc.isMock});
    setMode("live");
    btnToggle.disabled = false;
    startPolling(uri);
  }
  function startPolling(uri){
    if(pollTimer) clearInterval(pollTimer);
    var tick = function(){
      if(mode !== "live") return;
      call("resources/read", {uri: uri}, function(reply){
        if(!reply) { onPollFail(uri); return; }
        pollFails = 0;
        var snap = reply.contents && reply.contents[0] && reply.contents[0].text;
        if(!snap){ onPollFail(uri); return; }
        try { snap = JSON.parse(snap); } catch(e){ onPollFail(uri); return; }
        if(snap.status === "unknown"){
          // 服务器重启过：这条 trace 不在本进程里了，诚实说，不空转
          setMode("replay");
          note(snap.error || "这条 trace 已不在服务器进程里。");
          if(pollTimer) clearInterval(pollTimer);
          return;
        }
        ui.appendEvents(snap);
        note(snap.status === "completed"
             ? ("跑完了，共 " + (snap.eventCount||0) + " 条事件。")
             : ("正在跑… 已有 " + (snap.eventCount||0) + " 条事件"));
        if(TERMINAL[snap.status]){
          if(pollTimer) clearInterval(pollTimer);
          setMode("replay");
          ui.revealAll();
          if(typeof ui.renderStat === "function") ui.renderStat();
        }
      });
    };
    tick();
    pollTimer = setInterval(tick, 900);
  }
  function onPollFail(uri){
    pollFails++;
    note("读取快照失败（第 " + pollFails + " 次），正在重试…");
    if(pollFails >= 3){
      if(pollTimer) clearInterval(pollTimer);
      setMode("replay");
      note("当前宿主似乎不支持界面读取资源快照，已停止轮询。"
         + "请用 mctrace_get_summary 取文本结论，或打开独立 McTrace Studio。");
    }
  }
  function note(msg){
    var n = document.getElementById("livenote");
    if(n) n.textContent = msg;
  }

  /* ---- 带回包的 RPC：宿主可能不响应，超时要能感知 ---- */
  function call(method, params, cb){
    ++rpcId;
    var id = rpcId;
    if(cb){
      pending[id] = cb;
      setTimeout(function(){
        if(pending[id]){
          delete pending[id];
          cb(null);            // 超时 = 宿主不支持这条链路
        }
      }, 2500);
    }
    post({jsonrpc:"2.0", id:id, method:method, params:params||{}});
    return id;
  }

  /* ================= 启动台：交互全在界面里完成 ================= */
  var launcher = document.getElementById("launcher");
  var story   = document.getElementById("story");
  var btnGo   = document.getElementById("btnGo");
  var btnBack = document.getElementById("btnBack");
  var launchHint = document.getElementById("launchHint");

  function scenario(){
    var el = document.querySelector('input[name="sc"]:checked');
    return el ? el.value : "order";
  }
  function showLauncher(){
    launcher.style.display = "block";
    story.style.display = "none";
    document.getElementById("formOrder").style.display =
      (scenario() === "order") ? "grid" : "none";
    if(scenario() === "order"){ setTimeout(function(){ document.getElementById("fCity").focus(); }, 60); }
  }
  function showStory(){
    launcher.style.display = "none";
    story.style.display = "block";
    btnBack.disabled = false;
  }
  Array.prototype.forEach.call(document.querySelectorAll('input[name="sc"]'), function(r){
    r.addEventListener("change", showLauncher);
  });

  // 界面里直接调 mctrace_start —— 不经过对话，用户全程留在这个界面里
  function startFromLauncher(){
    var sc = scenario();
    var args = {scenario: sc};
    if(sc === "order"){
      var city = (document.getElementById("fCity").value || "").trim();
      var kw   = (document.getElementById("fKeyword").value || "").trim();
      if(!city || !kw){
        launchHint.className = "lch-hint warn";
        launchHint.innerHTML = "先告诉我你在<b>哪个城市</b>、<b>哪个位置附近</b>——不确定位置我不替你猜，免得找到几百公里外的店。";
        (!city ? document.getElementById("fCity") : document.getElementById("fKeyword")).focus();
        return;
      }
      args.city = city;
      args.keyword = kw;
      args.goal = document.getElementById("fGoal").value;
      args.budget_yuan = parseFloat(document.getElementById("fBudget").value) || undefined;
      args.max_kcal = parseFloat(document.getElementById("fKcal").value) || undefined;
      // 注意：不要把局部变量叫 note —— 会遮蔽外层的 note() 函数
      var extra = (document.getElementById("fNote").value || "").trim();
      if(extra) args.user_note = extra;
    }
    btnGo.disabled = true;
    btnGo.textContent = "正在启动…";
    // 重置本次追踪的界面状态
    ui.loadTrace({events:[]});
    showStory();
    setMode("live");
    note("正在启动这次追踪…");

    var payload = {name:"mctrace_start", arguments: args};
    var done = false;
    function accept(sc){
      if(done) return; done = true;
      btnGo.disabled = false; btnGo.textContent = "开始查，全程摊开给我看";
      if(!sc){ setMode("replay"); note("这个界面没法自己发起查询（宿主不支持界面回调工具）。"
        + "请在对话里说一句，或打开独立 Studio。"); return; }
      if(sc.needsClarification){
        setMode("replay");
        note("还差点信息：" + (sc.missing || []).join("；"));
        showLauncher();
        btnGo.disabled = false; btnGo.textContent = "开始查，全程摊开给我看";
        return;
      }
      traceIdEl.textContent = sc.traceId || "trace";
      markMock({isMock: !!sc.isMock});
      startPolling(sc.snapshotUri || ("mctrace://runs/" + sc.traceId));
    }
    // 标准 MCP Apps：界面直接调服务端工具
    call("tools/call", payload, accept);
    // Apps SDK 方言
    try{
      if(window.openai && typeof window.openai.callTool === "function"){
        Promise.resolve(window.openai.callTool(payload.name, payload.arguments))
          .then(function(r){ accept(r && (r.structuredContent || r)); })
          .catch(function(){});
      }
    }catch(e){}
    // 兜底：宿主不支持界面回调时，请对话里的模型代跑
    setTimeout(function(){
      if(done) return;
      done = true;
      btnGo.disabled = false; btnGo.textContent = "开始查，全程摊开给我看";
      sendFollowup("用 McTrace 跑一次：" + (sc === "order"
        ? ("在" + args.city + "的" + args.keyword + "附近，" +
           (args.goal === "fatloss" ? "减脂低卡" : "顶饱") +
           "，预算 " + (args.budget_yuan||40) + " 元、热量不超 " + (args.max_kcal||500) + " 千卡")
        : "盘点我的麦当劳积分资产"));
      note("这个宿主不支持界面自己发起查询，已把请求交给对话里的助手，稍后结果会出现在这里。");
    }, 2600);
  }

  btnGo.addEventListener("click", startFromLauncher);
  btnBack.addEventListener("click", function(){
    if(pollTimer) clearInterval(pollTimer);
    pollTimer = null;
    setMode("idle");
    note("");
    ui.loadTrace({events:[]});
    showLauncher();
  });

  window.addEventListener("message", function(e){
    var m = e.data;
    if(!m || m.jsonrpc !== "2.0") return;
    hostHeard = true;
    // 先看是不是我们发出去的 RPC 的回包
    if(m.id && pending[m.id]){
      var cb = pending[m.id];
      delete pending[m.id];
      cb(m.result || null);
      return;
    }
    var method = m.method || "";
    var p = m.params || {};
    if(method === "ui/notifications/tool-result" || method === "ui/notifications/tool_result" ||
       method === "ui/notifications/tool-input-partial"){
      // 有 snapshotUri 且还没跑完 → 实时模式；否则就是一次性全量
      var sc = p.structuredContent || p.result || p;
      if(sc && sc.view === "launcher"){ ingestLauncher(sc); }
      else if(sc && sc.snapshotUri && !TERMINAL[sc.status]){ ingestStart(sc); }
      else { if(ingest(p)) setMode("replay"); }
    } else if(method === "ui/notifications/tool-input"){
      ingest(p.arguments || p);
    } else if(method === "ui/notifications/tool-cancellation"){
      if(pollTimer) clearInterval(pollTimer);
      setMode("replay");
    }
  });

  // Apps SDK 旧通道（ChatGPT 系宿主）
  try{
    if(window.openai && window.openai.toolOutput){
      if(ingestLauncher(pickScoped(window.openai.toolOutput))) { /* 启动台 */ }
      else if(ingest(window.openai.toolOutput)){ setMode("replay"); }
    }
  }catch(e){}

  // 内联兜底：直接在 HTML 里塞了 trace（自包含分享/离线预览）
  if(!got && window.__MCTRACE_TRACE__){
    if(ingestLauncher(pickScoped(window.__MCTRACE_TRACE__))){ /* 启动台快照 */ }
    else if(ingest(window.__MCTRACE_TRACE__)){ setMode("replay"); }
  }

  // 告诉宿主：我准备好了。不同实现的握手名不统一，多发几个无害：
  // 不认识的方法宿主最多回 JSON-RPC error，不影响数据主通道。
  ["ui/notifications/app-ready", "ui/notifications/app-loaded", "notifications/initialized"].forEach(function(mm){
    notify(mm, {});
  });

  // 拿不到数据时，诚实降级：说明原因 + 指路独立 Studio
  setTimeout(function(){
    if(got) return;
    var why = hostHeard
      ? "宿主已连接，但这次没有把工具结果送进界面。"
      : "没有收到任何宿主消息。可能是当前环境不支持 MCP 应用界面，或这条调用不带数据。";
    document.getElementById("fbWhy").textContent = why;
    fallback.style.display = "block";
    btnToggle.disabled = true;
  }, 1200);

  /* ---------- 交互 ---------- */
  var expanded = true;
  btnToggle.onclick = function(){
    if(expanded){ ui.reset(); expanded = false; btnToggle.textContent = "展开全部步骤"; }
    else { ui.revealAll(); expanded = true; btnToggle.textContent = "收起步骤"; }
  };
  btnDeep.onclick = function(){
    var ask = "请在独立的 McTrace Studio 里打开这次的完整回放做深度分析"
            + (STUDIO_PATH ? ("（" + STUDIO_PATH + "）") : "")
            + "，并把这部追踪的结论再讲一遍。";
    if(STUDIO_PATH){
      // 标准 Host：外部链接；不支持时也不影响并发的 ui/message
      call("ui/open-link", {url: STUDIO_PATH});
    }
    sendFollowup(ask);
    deepHint.textContent = "已请求深度分析：宿主不支持回话时，请手动打开上面的 Studio 路径。";
  };
})();
"""

APP_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>McTrace · Live Story</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@500;600;700&display=swap" rel="stylesheet">
<style>__ALL_CSS__</style>
</head>
<body class="mctr">
<div class="app">

  <!-- ===== 启动台：零参数工具命中时显示，所有交互都在这里完成 ===== -->
  <section id="launcher" style="display:none">
    <div class="lch">
      <div class="lch-hero">
        <h2>麦搭子 · 麦当劳点餐追踪</h2>
        <p>说清你要什么，我一边查一边把过程摊开给你看——<b>每一步用了哪个工具、抽出了什么事实、约束过没过，都可以点开查</b>。</p>
      </div>

      <div class="lch-scenes">
        <label class="scene">
          <input type="radio" name="sc" value="order" checked />
          <span class="sc-in">
            <b>🍽 点餐推荐</b>
            <i>找门店 → 拉菜单 → 核热量 → 拆构成 → 查券 → 算价</i>
          </span>
        </label>
        <label class="scene">
          <input type="radio" name="sc" value="points" />
          <span class="sc-in">
            <b>🎁 积分资产盘点</b>
            <i>余额 → 临期 → 抽奖 → 沉睡奖券 → 最值兑换 → 可领券</i>
          </span>
        </label>
      </div>

      <div class="lch-form" id="formOrder">
        <div class="row2">
          <label>城市 <b class="req">*</b>
            <input id="fCity" type="text" placeholder="上海市 / 黄冈市" autocomplete="off" />
          </label>
          <label>位置附近 <b class="req">*</b>
            <input id="fKeyword" type="text" placeholder="静安寺 / 万达广场" autocomplete="off" />
          </label>
        </div>
        <div class="row2">
          <label>目标
            <select id="fGoal">
              <option value="fatloss">减脂 · 低卡（取热量最低的正餐）</option>
              <option value="satiety" selected>常规 · 顶饱（取能量最高但不超标）</option>
            </select>
          </label>
          <label>怎么理解「减脂」这类宽泛说法
            <input id="fNote" type="text" placeholder="例如：想吃热的 / 不要汉堡" autocomplete="off" />
          </label>
        </div>
        <div class="row2">
          <label>预算上限（元）<input id="fBudget" type="number" value="40" min="1" step="1" /></label>
          <label>热量上限（千卡）<input id="fKcal" type="number" value="500" min="1" step="10" /></label>
        </div>
      </div>

      <div class="lch-go">
        <button id="btnGo" class="primary">开始查，全程摊开给我看</button>
        <span class="lch-hint" id="launchHint">带 <b class="req">*</b> 的两项必须填——不确定你在哪，我不会替你猜。</span>
      </div>

      <div class="lch-readonly">全程只读：只查门店/菜单/热量/券/算价与积分，<b>不会下单、不会领券、不会动你的账户</b>。</div>
    </div>
  </section>

  <!-- ===== 追踪视图 ===== -->
  <div id="story">
  <div class="apphead">
    <span class="brand"><span class="mlogo"><svg viewBox="0 0 24 24" aria-hidden="true"><rect width="24" height="24" rx="6" fill="#DA291C"/><path d="M17.243 3.006c2.066 0 3.742 8.714 3.742 19.478H24c0-11.588-3.042-20.968-6.766-20.968-2.127 0-4.007 2.81-5.248 7.227-1.241-4.416-3.121-7.227-5.231-7.227C3.031 1.516 0 10.888 0 22.476h3.014c0-10.763 1.658-19.47 3.724-19.47 2.066 0 3.741 8.05 3.741 17.98h2.997c0-9.93 1.684-17.98 3.75-17.98Z" fill="#FFC72C"/></svg></span>McTrace</span>
    <span class="tid" id="tid">trace…</span>
    <span class="chip" id="modechip">等待数据</span>
    <span class="chip real" id="mockchip">真实数据</span>
    <span class="spacer"></span>
    <span class="appacts">
      <button id="btnBack" disabled>← 再来一次</button>
      <button id="btnToggle" disabled>收起步骤</button>
      <button id="btnDeep">深度分析 ›</button>
    </span>
  </div>

  <div class="tipbar">每一步都可以点：<b>点工具名</b>看它到底调了什么、返回了什么；<b>点来源路径</b>看这个数字取自返回结果里的哪个字段。</div>

  <div class="livenote" id="livenote"></div>

  <div class="fallback" id="fallback" style="display:none">
    <h4>界面已就绪，但还没拿到这次的数据</h4>
    <div id="fbWhy"></div>
    <div style="margin-top:8px">
      这时请用<strong>独立 McTrace Studio</strong>：它可以离线打开任意 trace，是兼容后备与深度分析入口。<br />
      <code>__STUDIO_PATH__</code>
    </div>
  </div>

  <div class="timeline" id="timeline"></div>

  <div class="result" id="result">
    <h3>结果与证据</h3>
    <div class="grid" id="resultGrid"></div>
    <div class="note" id="resultNote"></div>
  </div>

  <div class="appfoot" id="deepHint">McTrace · 工具调用成功 ≠ 用户目标达成。全程只读，未调用任何下单/抽奖写操作。</div>
  </div>
</div>

<div class="overlay" id="overlay"></div>
<aside class="lens" id="lens">
  <div class="lh"><b id="lensTitle">证据透镜</b><button class="x" id="lensClose">×</button></div>
  <div class="lb" id="lensBody"></div>
</aside>

<script>window.__MCTRACE_TOOLS__ = __TOOLS_JSON__;</script>
<script>window.__MCTRACE_STUDIO__ = "__STUDIO_PATH__";</script>
<script>__CORE_JS__</script>
<script>__APP_JS__</script>
</body>
</html>
"""


def render_html(studio_path: str = "") -> str:
    """返回 App 片段 HTML。studio_path 用于「深度分析」时把用户指回独立 Studio。"""
    safe_path = (studio_path or "").replace("\\", "/").replace('"', "")
    return (APP_TEMPLATE
            .replace("__ALL_CSS__", CORE_CSS + APP_CSS)
            .replace("__TOOLS_JSON__", json.dumps(TOOL_META, ensure_ascii=False))
            .replace("__CORE_JS__", CORE_JS)
            .replace("__APP_JS__", APP_JS)
            .replace("__STUDIO_PATH__", safe_path or "(未生成 Studio 回放页)"))


def build_preview(trace_path: str, out_path: str, studio_path: str = "") -> str:
    """产出「打开即带数据」的快照 —— 用于预览 / Pages 展示 App 形态。

    正常形态下数据由宿主经 postMessage 送进来；这份快照把 trace 内联为
    window.__MCTRACE_TRACE__，双击即可看到它在对话里的样子。
    """
    import json
    with open(trace_path, encoding="utf-8") as f:
        trace = json.load(f)
    html = render_html(studio_path)
    inject = ("<script>window.__MCTRACE_TRACE__ = %s;</script>\n"
              % json.dumps(trace, ensure_ascii=False))
    html = html.replace("</head>", inject + "</head>")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"App 预览 -> {out_path}  (内联 {len(trace.get('events', []))} 个事件)")
    return out_path


def build_live_demo(trace_path: str, out_path: str, studio_path: str = "") -> str:
    """产出「双击就能看到边跑边长」的独立演示页。

    普通预览（build_preview）把 trace 内联进界面，是一次性铺开的「回放」；
    这份把**模拟宿主**也打包进来：iframe 加载界面 → 宿主只先给 traceId →
    界面每 900ms 来要一次快照 → 事件一条条长出来。用来向人证明实时链路是真的。
    """
    with open(trace_path, encoding="utf-8") as f:
        trace = json.load(f)
    sim = os.path.join(HERE, "tests", "host_sim.html")
    with open(sim, encoding="utf-8") as f:
        html = f.read()
    # 界面 HTML 也内联（srcdoc），这样演示页是真正单文件，拷到哪都能双击播放。
    # JSON 字符串里的 "</script" 必须转义，否则会提前闭合这个 script 标签。
    app_html = render_html(studio_path)
    def _js_str(s):
        return json.dumps(s, ensure_ascii=False).replace("</", "<\\/")

    inject = ("<script>window.__SIM_TRACE__ = %s;</script>\n"
              "<script>window.__SIM_APP_HTML__ = %s;</script>\n"
              % (_js_str(trace), _js_str(app_html)))
    html = html.replace("</head>", inject + "</head>")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"实时演示页 -> {out_path}  （内联 {len(trace.get('events', []))} 条事件，双击即可播放）")
    return out_path


def build_launcher_preview(out_path: str, studio_path: str = "") -> str:
    """产出「打开就能看到启动台」的静态快照。

    正常形态下启动台由宿主调 mctrace_launch 后渲染；这份把 launcher 视图内联进 HTML，
    让人双击就能看到"提到产品名之后弹出来的到底是什么"。
    """
    html = render_html(studio_path)
    inject = ("<script>window.__MCTRACE_TRACE__ = {\"view\":\"launcher\",\"isMock\":false,"
              "\"requiredFields\":[\"city\",\"keyword\"],\"events\":[]};</script>\n")
    html = html.replace("</head>", inject + "</head>")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"启动台预览 -> {out_path}  （双击即可看到弹出的界面）")
    return out_path


def build(studio_path: str = "") -> str:
    os.makedirs(ASSETS, exist_ok=True)
    html = render_html(studio_path)
    out = os.path.join(ASSETS, "live_story_app.html")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print(f"App UI -> {out}  ({len(html)} bytes)")
    return out


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--with-trace", default=None, help="内联一份 trace，产出打开即带数据的快照")
    ap.add_argument("--out", default=None, help="快照输出路径")
    ap.add_argument("--launcher-preview", action="store_true",
                    help="产出「打开即见启动台」的静态快照")
    ap.add_argument("--live-demo", default=None,
                    help="打包模拟宿主，产出双击即可看到「边跑边长」的独立演示页")
    args = ap.parse_args()

    sp = os.path.join(REPO, "apps", "studio", "live_story.html")
    sp = sp if os.path.exists(sp) else ""

    if args.launcher_preview:
        out = args.out or os.path.join(REPO, "docs", "launcher-preview.html")
        build_launcher_preview(out, sp)
    elif args.live_demo:
        out = args.out or os.path.join(REPO, "docs", "app-live-demo.html")
        build_live_demo(args.live_demo, out, sp)
    elif args.with_trace:
        out = args.out or os.path.join(REPO, "docs", "app-preview.html")
        build_preview(args.with_trace, out, sp)
    else:
        build(sp)
