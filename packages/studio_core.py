"""
麦探长 · Live Story UI 内核（Studio 页面与 MCP App 片段共用）

Studio（独立回放页，带场景下拉 / 文件载入）与 MCP App（嵌在对话里的 iframe）
长得不一样，但**卡片渲染、工具按钮、证据透镜必须完全相同**——否则两处会各自漂移。
所以把样式与渲染逻辑抽到这里，两边只做外壳差异。

内核只用原生 DOM + textContent 写值：能在聊天的沙箱 iframe 里跑，也不会把
返回数据当 HTML 执行。
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))

# 工具名 → 人话。工具名本身是给机器看的，页面上一律用中文名打头，
# 英文工具名降为次要信息；desc 用于鼠标悬停解释「这个工具查的是什么」。
TOOL_META = {
    "user-request":      {"cn": "用户需求", "internal": True,
                          "desc": "把你的自然语言请求变成这条轨迹的起点"},
    "detect:rule":      {"cn": "规则校验", "internal": True,
                          "desc": "本机规则引擎对预算 / 热量 / 临期积分等约束做硬校验"},
    "summary-composer":  {"cn": "结果汇总", "internal": True,
                          "desc": "把这条轨迹里的事实汇总成一句结论"},
    "query-nearby-stores":  {"cn": "附近门店", "desc": "按关键词与城市查找附近门店"},
    "query-meals":          {"cn": "门店菜单", "desc": "查该门店在售的餐品与价格"},
    "list-nutrition-foods": {"cn": "营养成分表", "desc": "查餐品的热量等营养数据"},
    "query-store-coupons":  {"cn": "门店优惠券", "desc": "查这家门店当前可用的优惠券"},
    "calculate-price":      {"cn": "价格试算", "desc": "对所选餐品试算应付金额"},
    "query-my-account":     {"cn": "账户积分", "desc": "查可用积分、累计积分、已过期积分"},
    "query-lottery-info":   {"cn": "抽奖活动", "desc": "查抽奖活动状态与单次消耗积分"},
    "query-my-prizes":      {"cn": "中奖记录", "desc": "查历史中奖奖品与核销状态"},
    "order-list":           {"cn": "历史订单", "desc": "查历史订单列表"},
    "query-survey-coupon":  {"cn": "满意度奖券", "desc": "查订单关联的满意度调查奖券"},
    "mall-points-products": {"cn": "积分商城", "desc": "查积分可兑换的商品"},
    "available-coupons":    {"cn": "可领取券", "desc": "查当前可以领取的优惠券"},
    "campaign-calendar":    {"cn": "活动日历", "desc": "查正在进行中的活动日历"},
}

CORE_CSS = r"""
:root{
  --bg:#FFFBF4; --card:#FFFFFF; --ink:#27251F; --muted:#6E6A62; --faint:#9A948A;
  --line:#F0E2CE; --line2:#F7EFE2;
  --red:#DA291C; --red-deep:#B21D12; --red-soft:#FBE9E7;
  --amber:#FFC72C; --amber-deep:#F2A900; --amber-soft:#FFF4D6;
  --green:#1F9D55; --green-soft:#E7F6EE;
  --warn:#E0820C; --warn-soft:#FDF0DD;
  --blue:#DA291C; --blue-soft:#FBE9E7;
  --degraded:#8A4FB0; --degraded-soft:#F3EAFB;
  --shadow:0 1px 2px rgba(39,37,31,.05), 0 10px 28px rgba(39,37,31,.07);
  --shadow-hi:0 3px 8px rgba(39,37,31,.08), 0 20px 44px rgba(39,37,31,.13);
  --r:18px;
  --arch:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M17.243 3.006c2.066 0 3.742 8.714 3.742 19.478H24c0-11.588-3.042-20.968-6.766-20.968-2.127 0-4.007 2.81-5.248 7.227-1.241-4.416-3.121-7.227-5.231-7.227C3.031 1.516 0 10.888 0 22.476h3.014c0-10.763 1.658-19.47 3.724-19.47 2.066 0 3.741 8.05 3.741 17.98h2.997c0-9.93 1.684-17.98 3.75-17.98Z'/%3E%3C/svg%3E");
}
*{box-sizing:border-box}
.mctr{color:var(--ink);
  font:14px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",Segoe UI,Roboto,sans-serif;
  -webkit-font-smoothing:antialiased}
.mctr mono,.mctr code,.mctr .mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}

.mlogo{width:30px;height:30px;flex:0 0 30px;display:inline-block;vertical-align:middle}
.mlogo svg{width:100%;height:100%;display:block}

.progress{height:6px;border-radius:999px;background:var(--amber-soft);overflow:hidden;
  box-shadow:inset 0 0 0 1px rgba(242,169,0,.25)}
.progress > i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--red),#F2543B);
  transition:width .35s ease;border-radius:999px}

.timeline{display:flex;flex-direction:column;gap:12px}
.event{display:none;background:var(--card);border:1px solid var(--line);border-left-width:5px;
  border-radius:var(--r);box-shadow:var(--shadow);padding:14px 17px;animation:rise .32s ease both;
  transition:transform .16s ease,box-shadow .16s ease}
.event.show{display:block}
.event:hover{transform:translateY(-2px);box-shadow:0 0 0 1px rgba(242,169,0,.28),var(--shadow-hi)}
.event.k-info{border-left-color:#C9C2B6}
.event.k-warning{border-left-color:var(--warn)}
.event.k-success{border-left-color:var(--green)}
.event.k-error{border-left-color:var(--red)}
.event.k-degraded{border-left-color:var(--degraded)}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}

.ehead{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.seq{width:24px;height:24px;flex:0 0 24px;border-radius:50%;display:flex;align-items:center;justify-content:center;
  font-weight:800;font-size:12px;color:#fff;background:#C9C2B6;font-family:"Fredoka",-apple-system,sans-serif;
  box-shadow:0 0 0 2px var(--amber-soft),0 1px 2px rgba(39,37,31,.18)}
.seq.warning{background:var(--warn)}.seq.success{background:var(--green)}
.seq.error{background:var(--red)}.seq.degraded{background:var(--degraded)}
.etitle{font-weight:800;font-size:15.5px;margin:0;letter-spacing:.1px}
.badge{font-size:11px;font-weight:800;padding:2px 9px;border-radius:999px;letter-spacing:.3px}
.badge.success{background:var(--green-soft);color:#0a7d3c}
.badge.warning{background:var(--warn-soft);color:#9a5a08}
.badge.degraded{background:var(--degraded-soft);color:#5a3ea8}
.badge.error{background:var(--red-soft);color:var(--red-deep)}
.ts{margin-left:auto;color:var(--faint);font-size:11.5px;font-variant-numeric:tabular-nums}

.toolrow{margin:10px 0 0}
.toolbtn{display:inline-flex;align-items:center;gap:8px;cursor:pointer;font-family:inherit;
  border:1.5px solid var(--line);background:#FFFDF9;color:var(--ink);border-radius:11px;
  padding:6px 11px;font-size:12.5px;line-height:1.4;transition:.14s;text-align:left;font-weight:600}
.toolbtn:hover{border-color:var(--red);background:var(--red-soft);color:var(--red-deep);
  box-shadow:0 2px 8px rgba(218,41,28,.12)}
.toolbtn:focus-visible{outline:2px solid var(--amber);outline-offset:1px}
.toolbtn .ticon{position:relative;width:16px;height:16px;flex:0 0 16px;border-radius:6px;
  background:linear-gradient(135deg,#DA291C,#E8432F);box-shadow:inset 0 1px 0 rgba(255,255,255,.18),0 1px 2px rgba(218,41,28,.4)}
.toolbtn .ticon::before{content:"";position:absolute;inset:13%;
  background:var(--amber);-webkit-mask:var(--arch) center/contain no-repeat;mask:var(--arch) center/contain no-repeat}
.toolbtn:hover .ticon{background:linear-gradient(135deg,#C8231A,#DA291C)}
.toolbtn .tname{font-weight:800}
.toolbtn .tcode{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:11px;color:var(--faint);background:#FBF5EA;border-radius:6px;padding:1px 6px}
.toolbtn .tlook{margin-left:2px;color:var(--red);font-weight:800}
.toolbtn .tlook::after{content:" ›"}
.toolbtn.internal{border-style:dashed;background:#FFFBF2}
.toolbtn.internal .tlook{color:var(--muted)}
.toolbtn.internal .ticon{background:linear-gradient(135deg,#EFE7D8,#E0D2BC);box-shadow:inset 0 1px 0 rgba(255,255,255,.5)}
.toolbtn.internal .ticon::before{background:#B7AC99}
.toolbtn.internal:hover{border-color:#E0D5C2;background:#FFFBF2;color:var(--ink);box-shadow:none}
.toolbtn.internal:hover .ticon{background:linear-gradient(135deg,#E8DDCA,#D8C7AC)}

.narr{margin:11px 0 0;padding:11px 14px;border-radius:12px;background:var(--amber-soft);
  border:1px solid #F6E3B0;font-size:14px;color:#4a3a12}
.narr.pro{background:#F8F6F1;border:1px solid var(--line2);font-size:13.5px;color:#4b4640}
.narr .who{font-size:11px;font-weight:800;letter-spacing:.4px;color:var(--red);display:block;margin-bottom:3px}
.narr.pro .who{color:var(--muted)}

.facts{margin-top:11px;display:flex;flex-direction:column;gap:6px}
.fact{display:flex;align-items:baseline;gap:9px;flex-wrap:wrap;font-size:13px}
.fact .k{color:var(--muted);min-width:92px}
.fact .v{font-weight:800;color:var(--ink)}
.srcbtn{cursor:pointer;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:11px;color:#8a5a00;background:#FFF7E3;border:1px dashed #E9CE84;
  border-radius:6px;padding:1px 7px;transition:.14s}
.srcbtn:hover{border-style:solid;border-color:var(--red);background:var(--amber-soft);color:var(--red-deep)}
.srcbtn::after{content:" ↗";color:var(--faint)}
.srcbtn:hover::after{color:var(--red)}

.ents{margin-top:11px;display:flex;gap:7px;flex-wrap:wrap}
.ent{font-size:12px;font-weight:800;color:#8A4B00;background:var(--amber-soft);border:1px solid #F2D98E;
  padding:4px 11px;border-radius:999px;cursor:pointer;transition:.14s;display:inline-flex;align-items:center;gap:5px}
.ent:hover{background:var(--amber);border-color:var(--amber-deep);color:#5a3800;box-shadow:0 2px 8px rgba(242,169,0,.35)}
.ent .role{font-weight:600;color:#b07c11;font-size:11px}
.ent::after{content:" ›";color:#C99A1E;font-weight:700}
.rule{margin-top:9px;font-size:12.5px;font-weight:800;padding:5px 11px;border-radius:9px;display:inline-flex;gap:8px;align-items:center}
.rule.pass{background:var(--green-soft);color:#0a7d3c}
.rule.fail{background:var(--warn-soft);color:#9a5a08}
.rule .id{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-weight:700}

.result{display:none;margin-top:18px;border:1px solid var(--line);border-radius:18px;
  box-shadow:var(--shadow);overflow:hidden;animation:rise .4s ease both;background:#fff}
.result.show{display:block}
.result h3{margin:0;font-size:15px;font-weight:800;color:#fff;background:linear-gradient(135deg,var(--red),#E8432F);
  padding:13px 18px;display:flex;align-items:center;gap:8px;letter-spacing:.3px}
.result h3::before{content:"";width:16px;height:13px;flex:0 0 auto;background:var(--amber);
  -webkit-mask:var(--arch) center/contain no-repeat;mask:var(--arch) center/contain no-repeat}
.result .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:11px;padding:16px 18px 0}
.rcell{background:#FFFBF4;border:1px solid var(--line);border-radius:12px;padding:11px 13px}
.rcell .l{font-size:11.5px;color:var(--muted)}
.rcell .n{font-size:18px;font-weight:800;margin-top:3px;line-height:1.35;font-family:"Fredoka",-apple-system,sans-serif;letter-spacing:.3px}
.rcell.ok .n{color:var(--green)}
.rcell.no .n{color:var(--red)}
.note{margin-top:0;font-size:12.5px;color:var(--muted);border-top:1px dashed var(--line);padding:12px 18px 16px;line-height:1.7}

.lens{position:fixed;top:0;right:0;height:100%;width:440px;max-width:94vw;background:#221E1A;color:#EDE6DA;
  box-shadow:-16px 0 50px rgba(0,0,0,.34);transform:translateX(100%);transition:transform .26s ease;z-index:50;
  display:flex;flex-direction:column}
.lens.open{transform:none}
.lens .lh{padding:14px 17px;border-bottom:1px solid #3A332B;display:flex;align-items:center;gap:9px;
  background:linear-gradient(135deg,#2A241F,#322a23)}
.lens .lh b{font-size:15px;color:#fff;font-weight:800}
.lens .lh .x{margin-left:auto;cursor:pointer;color:#C9BFAE;font-size:22px;line-height:1;background:none;border:0;font-family:inherit;transition:.14s}
.lens .lh .x:hover{color:var(--amber)}
.lens .lb{padding:15px 17px;overflow:auto}
.lens .lv{font-size:13px;margin-bottom:10px}
.lens .lv .l{color:#A89C8A;font-size:11.5px;letter-spacing:.3px}
.lens .lv .v{color:#fff;font-weight:700;word-break:break-all}
.lens pre{background:#15120F;border:1px solid #3A332B;border-radius:11px;padding:12px;font-size:11.5px;
  color:#F0D9A8;overflow:auto;max-height:46vh;white-space:pre-wrap;word-break:break-word;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
.lens .hint{color:#A89C8A;font-size:11.5px;margin:13px 0 6px}
.overlay{position:fixed;inset:0;background:rgba(34,30,26,.42);opacity:0;pointer-events:none;transition:.25s;z-index:40}
.overlay.show{opacity:1;pointer-events:auto}

.empty{text-align:center;color:var(--muted);padding:26px 8px}
.stat{display:flex;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:12px}
.stat b{color:var(--ink)}
@media (max-width:640px){.fact .k{min-width:80px}.lens{width:100%}.result .grid{padding:14px 14px 0}.note{padding:12px 14px 14px}}
"""

CORE_JS = r"""
(function(global){
  "use strict";

  var STATUS_TXT = {success:"成功", warning:"提醒", degraded:"降级", error:"失败"};
  var RESULT_LABELS = {
    availablePoint:"可用积分", accumulativePoint:"累计积分", expiredPoint:"历史已过期",
    currentMouthExpirePoint:"本月将过期", expiringThisMonth:"本月将过期",
    sleepingCoupons:"沉睡奖券", bestRedeem:"最值兑换", bestRedeemPoint:"最值兑换(分)",
    claimableCoupons:"可领券", activities:"进行中活动",
    store:"门店", item:"推荐餐品", payableYuan:"应付金额", kcal:"热量",
    checksPassed:"约束校验", orderCreated:"是否下单",
    patrolStores:"巡查门店", target:"目标餐品", inStockStores:"在售门店",
    verdict:"结论", lowest:"最低价", highest:"最高价",
    deltaYuan:"差价", coveragePct:"可得性覆盖率",
    primaryForm:"比对形态", patrolRange:"实际覆盖"
  };

  function el(tag, cls){ var e=document.createElement(tag); if(cls) e.className=cls; return e; }
  function tx(tag, cls, t){ var e=el(tag, cls); e.textContent = (t==null? "" : String(t)); return e; }
  function btn(cls, t){ var b=el("button", cls); b.type="button"; b.textContent=t==null?"":String(t); return b; }
  function fmt(v){ if(v===true) return "是"; if(v===false) return "否"; if(v===null||v===undefined) return "—"; return String(v); }

  function UI(opts){
    opts = opts || {};
    this.tools = opts.tools || {};
    this.ids = opts.ids || {};
    this.narr = "friendly";
    this.trace = null;
    this.shown = 0;
    if (opts.autoInitLens !== false) this._initLens();
  }

  UI.prototype._q = function(id){ return document.getElementById(id); };
  UI.prototype.meta = function(tool){ return this.tools[tool] || {cn: tool, desc: "真实 MCP 工具调用"}; };
  UI.prototype.hasEvidence = function(ev){ return !!(ev.request || ev.response); };

  UI.prototype._initLens = function(){
    var self=this;
    var ov = this._q("overlay"), closeBtn = this._q("lensClose");
    if(ov) ov.onclick = function(){ self.closeLens(); };
    if(closeBtn) closeBtn.onclick = function(){ self.closeLens(); };
    document.addEventListener("keydown", function(e){ if(e.key === "Escape") self.closeLens(); });
  };
  UI.prototype.openLens = function(){
    var l=this._q("lens"), o=this._q("overlay");
    if(l) l.classList.add("open");
    if(o) o.classList.add("show");
  };
  UI.prototype.closeLens = function(){
    var l=this._q("lens"), o=this._q("overlay");
    if(l) l.classList.remove("open");
    if(o) o.classList.remove("show");
  };

  UI.prototype._lensBody = function(title){
    document.getElementById("lensTitle").textContent = title;
    var b = document.getElementById("lensBody");
    b.innerHTML = "";
    return b;
  };
  UI.prototype._lensLine = function(b, label, value){
    var row = el("div","lv");
    row.appendChild(tx("div","l", label));
    row.appendChild(tx("div","v", value));
    b.appendChild(row);
  };
  UI.prototype._hint = function(b, t){ b.appendChild(tx("div","hint", t)); };
  UI.prototype._json = function(b, obj){
    var pre = el("pre");
    pre.textContent = JSON.stringify(obj, null, 2);
    b.appendChild(pre);
  };

  UI.prototype.openLensForFact = function(f){
    var b = this._lensBody("事实来源：" + f.key);
    this._lensLine(b, "取值", fmt(f.value));
    this._lensLine(b, f.sourcePath ? "取自返回结果的字段" : "来源", f.sourcePath || f.source || "—");
    var ev = this.findEventWithFact(f);
    if(ev){
      this._hint(b, "这条事实来自下面这次真实调用：");
      this._lensLine(b, "工具", this.meta(ev.tool).cn + "（" + ev.tool + "）");
      this._lensLine(b, "状态", STATUS_TXT[ev.status] || ev.status);
      this._json(b, {request: ev.request, response: ev.response});
    }
    this.openLens();
  };
  UI.prototype.openLensForTool = function(ev){
    var m = this.meta(ev.tool), self = this;
    var b = this._lensBody("调用证据：" + m.cn);
    this._lensLine(b, "这个工具做什么", m.desc || "—");
    this._lensLine(b, "工具名", ev.tool);
    this._lensLine(b, "状态", STATUS_TXT[ev.status] || ev.status);
    this._lensLine(b, "证据编号", ev.evidenceRef || "—");
    this._hint(b, "下面是这次调用发给麦当劳 MCP 的原始请求与原始返回：");
    this._json(b, {request: ev.request, response: ev.response});
    if(ev.facts && ev.facts.length){
      this._hint(b, "本次抽取到的事实：");
      ev.facts.forEach(function(f){
        var s = f.sourcePath || f.source || "";
        self._lensLine(b, f.key, fmt(f.value) + (s ? "  ← " + s : ""));
      });
    }
    this.openLens();
  };
  UI.prototype.openLensInternal = function(ev){
    var m = this.meta(ev.tool), self = this;
    var b = this._lensBody("本机步骤：" + m.cn);
    this._lensLine(b, "这一步做什么", m.desc || "—");
    this._lensLine(b, "状态", STATUS_TXT[ev.status] || ev.status);
    this._hint(b, "这一步由 麦探长 本机引擎生成，不对应任何 MCP 调用，因此没有 request/response。它基于上一步的真实返回做处理：");
    if(ev.facts && ev.facts.length){
      ev.facts.forEach(function(f){
        if(f.sourcePath || f.source){ self._lensLine(b, f.key, fmt(f.value) + "  ← " + (f.sourcePath||f.source)); }
      });
    }
    this.openLens();
  };
  UI.prototype.openLensForEntity = function(ev, name, role){
    var m = this.meta(ev.tool), self = this;
    var b = this._lensBody("实体：" + name);
    this._lensLine(b, "角色", role || "—");
    if(this.hasEvidence(ev)){
      this._lensLine(b, "来自工具", m.cn + "（" + ev.tool + "）");
      this._lensLine(b, "证据编号", ev.evidenceRef || "—");
      this._hint(b, "原始请求与返回：");
      this._json(b, {request: ev.request, response: ev.response});
    } else {
      this._hint(b, "该实体由本机步骤归纳，不对应 MCP 调用。");
      if(ev.facts && ev.facts.length){
        ev.facts.forEach(function(f){
          if(f.sourcePath || f.source){ self._lensLine(b, f.key, fmt(f.value) + "  ← " + (f.sourcePath||f.source)); }
        });
      }
    }
    this.openLens();
  };
  UI.prototype.findEventWithFact = function(f){
    if(!this.trace || !this.trace.events) return null;
    for(var i=0;i<this.trace.events.length;i++){
      var e = this.trace.events[i];
      if(e.facts && e.facts.some(function(x){ return x.key===f.key && String(x.value)===String(f.value); })) return e;
    }
    return this.trace.events[this.trace.events.length-1];
  };

  UI.prototype._factRow = function(f){
    var self=this, row = el("div","fact");
    row.appendChild(tx("span","k", f.key));
    row.appendChild(tx("span","v", fmt(f.value)));
    var src = f.sourcePath || f.source;
    if(src){
      var s = btn("srcbtn", src);
      s.title = "这个数值取自返回结果的该字段，点击查看原始调用";
      s.onclick = function(){ self.openLensForFact(f); };
      row.appendChild(s);
    }
    return row;
  };

  UI.prototype._toolBtn = function(ev){
    var self=this, m = this.meta(ev.tool);
    var internal = !!m.internal || !this.hasEvidence(ev);
    var b = el("button","toolbtn"+(internal?" internal":""));
    b.type = "button";
    b.appendChild(el("span","ticon"));
    b.appendChild(tx("span","tname", m.cn));
    if(ev.tool) b.appendChild(tx("code","tcode", ev.tool));
    b.appendChild(tx("span","tlook", internal ? "本机步骤" : "查看原始调用"));
    b.title = (m.desc||"") + (internal ? "（本机处理步骤，不产生 MCP 调用）" : " · 点击查看这次调用的原始请求与返回");
    b.onclick = function(){ internal ? self.openLensInternal(ev) : self.openLensForTool(ev); };
    return b;
  };

  UI.prototype._narrative = function(ev){
    var n = el("div","narr"+(this.narr==="pro"?" pro":""));
    n.appendChild(tx("span","who", this.narr==="friendly" ? "会边做边说的助手" : "业务结果视角"));
    n.appendChild(document.createTextNode((ev.say && ev.say[this.narr]) || ""));
    return n;
  };

  UI.prototype.renderEvent = function(ev){
    var self=this, card = el("div","event k-"+(ev.kind||"info"));

    var head = el("div","ehead");
    head.appendChild(tx("span","seq "+(ev.kind||"info"), ev.seq));
    head.appendChild(tx("h4","etitle", ev.title || this.meta(ev.tool).cn));
    head.appendChild(tx("span","badge "+ev.status, STATUS_TXT[ev.status]||ev.status));
    head.appendChild(tx("span","ts", ev.ts));
    card.appendChild(head);

    var tr = el("div","toolrow");
    tr.appendChild(this._toolBtn(ev));
    card.appendChild(tr);

    card.appendChild(this._narrative(ev));

    if(ev.facts && ev.facts.length){
      var facts = el("div","facts");
      ev.facts.forEach(function(f){ facts.appendChild(self._factRow(f)); });
      card.appendChild(facts);
    }
    if(ev.rule){
      var r = el("div","rule "+(ev.rule.pass?"pass":"fail"));
      r.appendChild(tx("span","id", ev.rule.id));
      var t = ev.rule.pass ? "通过" : "未通过";
      if(ev.rule.deltaKcal!=null) t += "（Δ "+ev.rule.deltaKcal+" kcal）";
      if(ev.rule.deltaYuan!=null) t += "（Δ "+ev.rule.deltaYuan+" 元）";
      r.appendChild(document.createTextNode(t));
      card.appendChild(r);
    }
    if(ev.entities && Object.keys(ev.entities).length){
      var ents = el("div","ents");
      Object.keys(ev.entities).forEach(function(name){
        var e = el("span","ent");
        e.appendChild(document.createTextNode(name));
        e.appendChild(tx("span","role", ev.entities[name]));
        e.title = "点击查看该实体的原始调用证据";
        e.onclick = function(){ self.openLensForEntity(ev, name, ev.entities[name]); };
        ents.appendChild(e);
      });
      card.appendChild(ents);
    }
    card._ev = ev;
    return card;
  };

  UI.prototype.setNarr = function(mode){
    this.narr = mode;
    var tl = this._q(this.ids.timeline);
    if(!tl) return;
    var self = this;
    [].forEach.call(tl.children, function(card){
      if(!card._ev) return;
      var old = card.querySelector(".narr");
      if(old) card.replaceChild(self._narrative(card._ev), old);
    });
  };

  UI.prototype.loadTrace = function(trace){
    this.trace = trace;
    this._seenSeq = {};
    var tl = this._q(this.ids.timeline);
    if(tl) tl.innerHTML = "";
    var res = this._q(this.ids.result);
    if(res) res.classList.remove("show");
    if(!tl) return 0;
    if(!trace || !trace.events || !trace.events.length){
      var empty = el("div","empty");
      empty.appendChild(tx("div","", (this.ids.emptyText || "没有可回放的事件。")));
      tl.appendChild(empty);
      this.shown = 0;
      return 0;
    }
    var self = this;
    trace.events.forEach(function(ev){
      self._seenSeq[String(ev.seq)] = 1;
      tl.appendChild(self.renderEvent(ev));
    });
    this.shown = 0;
    return trace.events.length;
  };

  /* 实时模式：只把「新到」的事件追加进来（按 seq 去重），已有节点不动。
     用于 （已移除的 MCP 工具） 的轮询场景 —— 事件是后台跑出来的，界面边跑边长。 */
  UI.prototype.appendEvents = function(trace){
    if(!trace) return 0;
    var tl = this._q(this.ids.timeline);
    if(!tl) return 0;
    if(!this.trace || !this._seenSeq){
      // 第一次：先把舞台清干净，但**不**走 loadTrace —— 它留给一次性全量模式
      this._seenSeq = {};
      tl.innerHTML = "";
      var r = this._q(this.ids.result);
      if(r) r.classList.remove("show");
    }
    this.trace = trace;
    var self = this, added = 0;
    (trace.events || []).forEach(function(ev){
      var key = String(ev.seq);
      if(self._seenSeq[key]) return;
      self._seenSeq[key] = 1;
      var node = self.renderEvent(ev);
      if(node && node.classList) node.classList.add("show");
      tl.appendChild(node);
      added++;
    });
    if(added){
      this.shown = tl.children.length;
      this._updateBar();
      this.maybeResult();
      if(typeof this.renderStat === "function") this.renderStat();
    }
    return added;
  };

  UI.prototype.revealAll = function(){
    var tl = this._q(this.ids.timeline);
    if(!tl) return;
    for(var i=0;i<tl.children.length;i++){ if(tl.children[i].classList) tl.children[i].classList.add("show"); }
    this.shown = tl.children.length;
    this._updateBar();
    this.maybeResult();
  };
  UI.prototype.reset = function(){
    var tl = this._q(this.ids.timeline);
    if(tl){ for(var i=0;i<tl.children.length;i++){ tl.children[i].classList.remove("show"); } }
    var res = this._q(this.ids.result);
    if(res) res.classList.remove("show");
    this.shown = 0;
    this._updateBar();
  };
  UI.prototype.showNext = function(){
    var tl = this._q(this.ids.timeline);
    if(!tl) return false;
    if(this.shown >= tl.children.length) return false;
    var c = tl.children[this.shown];
    if(c && c.classList) c.classList.add("show");
    this.shown++;
    this._updateBar();
    if(this.shown >= tl.children.length) this.maybeResult();
    return true;
  };
  UI.prototype.done = function(){
    var tl = this._q(this.ids.timeline);
    return tl ? (this.shown >= tl.children.length) : true;
  };
  UI.prototype._updateBar = function(){
    var bar = this._q(this.ids.bar), tl = this._q(this.ids.timeline);
    if(bar && tl) bar.style.width = (tl.children.length ? (this.shown/tl.children.length*100) : 0) + "%";
  };

  UI.prototype.maybeResult = function(){
    var grid = this._q(this.ids.resultGrid), res = this._q(this.ids.result);
    if(!grid || !res || !this.trace) return;
    var found = (this.trace.events||[]).filter(function(e){ return e.response && e.response.result; })[0];
    if(found) this.renderResult(found.response.result, found.facts);
  };

  UI.prototype._cell = function(label, val, cls){
    var c = el("div","rcell "+(cls||""));
    c.appendChild(tx("div","l", label));
    c.appendChild(tx("div","n", fmt(val)));
    return c;
  };
  UI.prototype.renderResult = function(r, facts){
    var self=this, grid = this._q(this.ids.resultGrid), res = this._q(this.ids.result), noteEl = this._q(this.ids.resultNote);
    if(!grid) return;
    grid.innerHTML = "";
    var isOrder = (r.store || r.item || r.payableYuan!=null || r.kcal!=null);
    if(isOrder){
      if(r.store) grid.appendChild(this._cell("门店", r.store));
      if(r.item) grid.appendChild(this._cell("推荐餐品", r.item));
      if(r.payableYuan!=null) grid.appendChild(this._cell("应付金额", typeof r.payableYuan==="number" ? "¥"+r.payableYuan : r.payableYuan));
      if(r.kcal!=null) grid.appendChild(this._cell("热量", r.kcal+" kcal"));
      grid.appendChild(this._cell("约束校验", r.checksPassed?"全部通过":"未通过", r.checksPassed?"ok":"no"));
      grid.appendChild(this._cell("是否下单", r.orderCreated?"已下单":"未下单", r.orderCreated?"":"no"));
    } else {
      Object.keys(r).forEach(function(k){
        if(r[k]===null || r[k]===undefined) return;
        if(k==="summary"||k==="orderCreated"||k==="checksPassed") return;
        var cls = "";
        if((k==="expiredPoint"||k==="expiringThisMonth") && r[k]) cls="no";
        if((k==="sleepingCoupons"||k==="claimableCoupons"||k==="activities") && r[k]) cls="ok";
        grid.appendChild(self._cell(RESULT_LABELS[k]||k, r[k], cls));
      });
      grid.appendChild(this._cell("是否写操作", r.orderCreated?"已下单":"无（只读）", r.orderCreated?"no":"ok"));
    }
    var note = "";
    if(facts){
      var ps = facts.filter(function(f){ return f.key==="priceSource"; })[0];
      if(ps) note += "价格来源：" + ps.value + "（诚实原则：仅叙述真实返回的数据）。 ";
    }
    if(r.summary) note += r.summary + "。";
    note += "全程只读，未调用任何下单/抽奖写操作。";
    if(noteEl) noteEl.textContent = note;
    res.classList.add("show");
  };

  UI.prototype.renderStat = function(){
    var node = this._q(this.ids.stat);
    if(!node || !this.trace) return;
    var tools = {}, warns=0, errs=0;
    (this.trace.events||[]).forEach(function(e){
      tools[e.tool]=(tools[e.tool]||0)+1;
      if(e.kind==="warning") warns++;
      if(e.kind==="error") errs++;
    });
    node.innerHTML = "";
    var parts = [["事件", (this.trace.events||[]).length], ["工具种类", Object.keys(tools).length],
                 ["提醒", warns], ["失败", errs], ["数据", this.trace.isMock ? "模拟" : "真实"]];
    parts.forEach(function(p){
      var s = el("span");
      s.appendChild(document.createTextNode(p[0] + " "));
      s.appendChild(tx("b","", p[1]));
      node.appendChild(s);
    });
  };

  UI.prototype.headline = function(){
    var evs = (this.trace && this.trace.events) || [];
    var last = evs[evs.length-1];
    return (last && last.say && last.say.friendly) || "";
  };

  global.麦探长UI = UI;
  global.麦探长UI.TOOL_META_FALLBACK = {};
})(window);
"""


def embed_tools():
    """给 App / Studio 注入工具表的 <script> 片段。"""
    import json
    return json.dumps(TOOL_META, ensure_ascii=False)
