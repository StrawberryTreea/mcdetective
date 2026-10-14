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


# 渲染内核（办案页生成器与在线后端共用同一份，保证「归档案卷」与「实时案卷」外观一致）
from case_render import esc, short, facts_of, render_case  # noqa: E402


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
.tagline{margin-left:auto;text-align:right;font-size:13px;color:#8a7f68;font-weight:600;line-height:1.55;border-right:3px solid #DA291C;padding-right:12px}
.tagline b{color:#2C2C2A;font-weight:800}
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
.intake-msg.run{background:#FFF8E8;border:1px solid #F2A900;color:#7a5200}
.intake-msg.err{background:#FCEBEB;border:1px solid #E24B4A;color:#A32D2D}
.picks{display:flex;gap:6px;flex-wrap:wrap;margin-top:9px}
.pick{cursor:pointer;font:700 12px inherit;padding:4px 12px;border-radius:999px;border:1.5px solid #F2A900;background:#fff;color:#7a5200}
.pick:hover{background:#F2A900;color:#3a2c00}
.livefeed{margin-top:10px;max-height:230px;overflow:auto;border:1px solid #E5DCC9;border-radius:10px;background:#fff;padding:8px 10px}
.livefeed:empty{display:none}
.lf{display:flex;gap:8px;align-items:baseline;font-size:12px;padding:3px 0;border-bottom:1px dashed #EFE8D8}
.lf:last-child{border-bottom:0}
.lf .n{font:700 10.5px ui-monospace,monospace;color:#B4AE9C;width:20px;flex:0 0 20px}
.lf .t{font-weight:700;color:#6b6350;white-space:nowrap}
.lf.warn .t{color:#B57B00}
.lf.ok .t{color:#2E7D32}
.lf .s{color:#5b5340;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.tokenbox{margin-top:10px;border:1px solid #85B7EB;background:#F2F8FE;border-radius:10px;padding:11px 13px;display:none}
.tokenbox.show{display:block}
.tokenbox .th{font-size:12.5px;font-weight:800;color:#185FA5;margin-bottom:6px}
.tokenbox input{width:100%;font:12.5px ui-monospace,monospace;padding:8px 10px;border:1.5px solid #85B7EB;border-radius:8px;background:#fff}
.tokenbox .note{margin-top:7px}
.ovl{margin-top:4px;border:1px solid #E5DCC9;border-radius:10px;overflow:hidden;background:#fff}
.ovh,.ovrow{display:flex;align-items:center;gap:10px;padding:7px 12px;font-size:12.5px}
.ovh{background:#FAF7EF;font-weight:800;font-size:11.5px;color:#8a7f68;border-bottom:1px solid #E5DCC9}
.ovh span:nth-child(2),.ovcov{flex:0 0 108px}
.ovh span:nth-child(3),.ovprice{flex:0 0 108px;text-align:right;font-family:ui-monospace,monospace}
.ovrow{border-bottom:1px dashed #EFE8D8}
.ovrow:last-child{border-bottom:0}
.ovname{flex:1;font-weight:600}
.ovnote{padding:8px 12px;font-size:11.5px;color:#8a7f68;background:#FAF7EF;border-top:1px solid #E5DCC9}
.warnbar{margin-top:10px;background:#FFF3D6;border:1px solid #F2A900;border-left:4px solid #DA291C;border-radius:9px;padding:9px 13px;font-size:12.5px;color:#7a5200;font-weight:600}
.live-dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:#E24B4A;vertical-align:2px;margin-left:6px;animation:pulse 1.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.livebar{background:linear-gradient(90deg,#DA291C,#F2A900);color:#fff;font-size:12px;font-weight:700;padding:7px 13px;border-radius:10px;margin:10px 0 0;display:inline-block}
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
  var LAST_QUERY = '';
  var $ = function(id){ return document.getElementById(id); };

  function setMsg(cls, html){
    var m = $('intakeMsg');
    m.className = 'intake-msg show ' + (cls||'');
    m.innerHTML = html;
  }
  function clearFeed(){ $('liveFeed').innerHTML = ''; }
  function addLine(cls, seq, title, say){
    var d = document.createElement('div');
    d.className = 'lf ' + (cls||'');
    d.innerHTML = '<span class="n">' + (seq!=null? seq : '') + '</span>'
      + '<span class="t">' + title + '</span><span class="s">' + say + '</span>';
    $('liveFeed').appendChild(d);
    var f = $('liveFeed'); f.scrollTop = f.scrollHeight;
  }
  function showPicks(items, onPick){
    var box = $('picks'); box.innerHTML = '';
    items.forEach(function(it){
      var b = document.createElement('button');
      b.className = 'pick'; b.type = 'button'; b.textContent = it.label;
      b.onclick = function(){ box.innerHTML = ''; onPick(it.value); };
      box.appendChild(b);
    });
  }

  // 调档（已归档真实案卷）
  function showCase(key){
    CASES.forEach(function(c){
      var el = $('case-' + c.key);
      if(el) el.style.display = (c.key === key) ? '' : 'none';
    });
    var live = $('liveCase');
    if(live) live.style.display = 'none';
    document.querySelectorAll('.casechip').forEach(function(b){
      b.classList.toggle('on', b.dataset.key === key);
    });
    window.scrollTo({top:0, behavior:'smooth'});
  }
  document.querySelectorAll('.casechip').forEach(function(b){
    b.onclick = function(){
      showCase(b.dataset.key);
      setMsg('ok','已调阅归档案卷：<b>' + b.textContent + '</b>。想查新案子，点上面「探长出勤」。');
      clearFeed(); $('picks').innerHTML = '';
    };
  });

  // —— 真跑：接案台 → /api/patrol（NDJSON 流式）——
  function run(query){
    LAST_QUERY = query;
    clearFeed();
    $('picks').innerHTML = '';
    var token = ($('fToken') && $('fToken').value || '').trim();
    setMsg('run','探长出勤中…… 正在划定巡查范围、逐店取证（全过程只读，不下单）');
    fetch('api/patrol', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({query: query, token: token})
    }).then(function(resp){
      var reader = resp.body.getReader(), dec = new TextDecoder(), buf = '', t0 = Date.now();
      function pump(){
        return reader.read().then(function(r){
          buf += dec.decode(r.value || new Uint8Array(), {stream:true});
          var lines = buf.split('\\n'); buf = lines.pop();
          lines.forEach(function(l){ if(l.trim()) handle(JSON.parse(l)); });
          if(!r.done) return pump();
        });
      }
      return pump().then(function(){ setTimeout(function(){ location.reload(); }, 1500); });
    }).catch(function(err){
      offlineNotice(err);
    });
  }

  function handle(m){
    if(m.type === 'progress'){
      var cls = m.kind === 'warning' ? 'warn' : (m.kind === 'success' ? 'ok' : '');
      addLine(cls, m.seq, m.title, m.say);
      return;
    }
    if(m.type === 'clarify'){
      var p = m.parsed || {};
      var where = (p.city||'？') + ' ' + (p.area||'');
      var qs = [];
      if((m.need||[]).indexOf('city') >= 0) qs.push('在哪个城市查？（例如：北京市 / 上海市）');
      if((m.need||[]).indexOf('target') >= 0) qs.push('想比哪款餐品的价格？');
      setMsg('new','探长听明白了：<b>' + where + '</b>' + (p.inferred ? '（' + p.inferred + '）' : '')
        + '，但缺一样：<b>' + qs.join(' ') + '</b>——不瞎猜，你点一下或者补一句：');
      showPicks((m.need||[]).indexOf('target') >= 0
        ? [{label:'巨无霸', value: targetOf(LAST_QUERY) + ' 巨无霸'},
           {label:'麦香鱼', value: targetOf(LAST_QUERY) + ' 麦香鱼'},
           {label:'板烧鸡腿堡', value: targetOf(LAST_QUERY) + ' 板烧鸡腿堡'},
           {label:'精选单人餐三件套', value: targetOf(LAST_QUERY) + ' 精选单人餐三件套'}]
        : [], function(v){ run(v); });
      return;
    }
    if(m.type === 'need_token'){
      $('tokenBox').classList.add('show');
      setMsg('new', m.msg || '探长需要你的 MCP Token 才能真出勤（Token 只用于这一次请求）。');
      return;
    }
    if(m.type === 'error'){
      setMsg('err', '巡查未完成：' + (m.msg || '未知错误'));
      return;
    }
    if(m.type === 'result'){
      addLine('ok', '✓', '结案', m.traceId + ' · ' + m.events + ' 条证据 · 服务端 ' + m.elapsed + 's');
      // 注入实时案卷（与归档案卷同一套渲染）
      var live = $('liveCase');
      live.innerHTML = '<div class="livebar">实时巡查结果 · 案号 ' + m.traceId + '（' + m.events + ' 条证据，' + m.elapsed + ' 秒）</div>' + m.html;
      live.style.display = '';
      document.querySelectorAll('.caseview-wrap').forEach(function(w){ w.style.display = 'none'; });
      setMsg('ok','结案！这份是<b>刚刚真跑</b>的：探长只读地巡查了麦当劳 MCP，全程可核验。');
      window.scrollTo({top: $('liveCase').offsetTop - 20, behavior:'smooth'});
      return;
    }
  }

  function targetOf(q){
    // 从原句里保留地点部分：去掉常见问句尾巴
    return (q||'').replace(/(有什么.*|哪家.*|哪个.*|怎么.*|附近.*|吗[?？]?)$/,'').trim();
  }

  function offlineNotice(err){
    // 本地打开（file://）或后端不在时，诚实说明并给出可行路径
    setMsg('new','这一页的「真跑」需要办案服务在线（浏览器要经它转发麦当劳 MCP——麦当劳 MCP 不允许浏览器跨域直连）。'
      + '你现在打开的是<b>离线归档版</b>：下面三册归档案卷都是真数据，随便看；'
      + '要真查新案子，二选一：① 用 WorkBuddy 装 Skill 后说一句话；② 本地起服务：'
      + '<code>python apps/detective/server.py</code>。');
    clearFeed();
  }

  document.getElementById('intakeForm').addEventListener('submit', function(ev){
    ev.preventDefault();
    var q = $('fQ').value.trim();
    if(!q){ setMsg('new','先得说个案子，比如「中关村 精选单人餐三件套哪家便宜」。'); return; }
    run(q);
  });

  // 页面打开时先探一下服务在不在
  fetch('api/health').then(function(r){ return r.json(); }).then(function(h){
    if(h && h.ok){ setMsg('ok','办案服务在线，报个案试试（真跑，全程只读）。Token 只在你贴了之后用于这一次请求。'); }
    else { offlineNotice(); }
  }).catch(offlineNotice);
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
  <div class="tagline"><b>哪家便宜、哪家有货</b>，查个底掉<br/>每一步，都有据可查</div>
</header>

<section class="card intake">
  <h2><span class="no">台</span>接案台 · 报个案</h2>
  <div class="lead">说一句话就行——城市、地段、想查的餐品，探长自己领会；缺什么他会问你，绝不瞎猜。</div>
  <form id="intakeForm" class="formrow">
    <div class="qbox"><input id="fQ" type="text" autocomplete="off"
      placeholder="比如：中关村 精选单人餐三件套哪家便宜？"/></div>
    <button class="gobtn" type="submit">探长出勤</button>
  </form>
  <div class="hint">默认方圆 3 km、最多 10 店（可在命令里改）· 例如：静安寺 麦香鱼 / 黄冈万达 巨无霸 / 深圳科技园 麦辣鸡腿堡</div>
  <div class="tokenbox" id="tokenBox">
    <div class="th">② 贴上你的 MCP Token，探长才能真出勤</div>
    <input id="fToken" type="password" autocomplete="off" placeholder="粘贴 open.mcd.cn/mcd 控制台申请的 Token"/>
    <div class="note">Token 只活在这一次请求里：不写进页面、不进仓库、不保存。<a href="https://open.mcd.cn/mcp" target="_blank" style="color:#185FA5">去申请（免费，手机号登录）</a> · 探长全程只读，不下单不领券。</div>
  </div>
  <div class="intake-msg" id="intakeMsg"></div>
  <div class="picks" id="picks"></div>
  <div class="livefeed" id="liveFeed"></div>
  <div class="archrow"><span class="lab">没带 Token？先调阅已归档案卷：</span>{chips_html}</div>
</section>

<div id="liveCase"></div>

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
  证据链引擎：麦探长（事实是一等公民，拟人化 ≠ 编造）· 餐品信息、价格及供应状态以麦当劳官方渠道实时结果为准<br/>
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
