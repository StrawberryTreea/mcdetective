"""
McTrace MCP App · 端到端自检

以子进程启动 server.py（offline 模式，不联网），把真实宿主会发的那几句话挨个走一遍，
并断言 MCP Apps 的关键约定都成立：

  ① initialize      → capabilities 里声明 io.modelcontextprotocol/ui 扩展
  ② tools/list      → 工具带 _meta.ui.resourceUri（含 Apps SDK 别名）
  ③ resources/list  → ui://mctrace/live-story
  ④ resources/read  → mimeType = text/html;profile=mcp-app，且 HTML 里有界面渲染内核
  ⑤ tools/call      → 返回 text + resource 链接 + structuredContent(trace)
  ⑥ 无 UI 的宿主只看 content：text 必须非空 available（向后兼容）

用法：
  python selftest.py            # 离线（跑 examples/traces 里的样本）
  python selftest.py --live     # 真实调用麦当劳 MCP
"""
import os
import sys
import json
import time
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))

UI_MIME = "text/html;profile=mcp-app"
UI_URI = "ui://mctrace/live-story"
UI_EXT = "io.modelcontextprotocol/ui"

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("  ✅ " if cond else "  ❌ ") + name + (("  → " + detail) if detail else ""))


class Client:
    """极简 stdio MCP 客户端，只做自检够用的部分。"""

    def __init__(self, offline=True):
        args = [sys.executable, os.path.join(HERE, "server.py")]
        if offline:
            args.append("--offline")
        self.p = subprocess.Popen(
            args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", bufsize=1, cwd=HERE,
        )
        self._id = 0

    def request(self, method, params=None):
        self._id += 1
        msg = {"jsonrpc": "2.0", "id": self._id, "method": method, "params": params or {}}
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.p.stdin.flush()
        while True:
            line = self.p.stdout.readline()
            if not line:
                raise RuntimeError("服务器关闭了连接；stderr=" + self.p.stderr.read())
            obj = json.loads(line)
            if obj.get("id") == self._id:
                return obj

    def notify(self, method, params=None):
        msg = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        self.p.stdin.write(json.dumps(msg, ensure_ascii=False) + "\n")
        self.p.stdin.flush()

    def close(self):
        try:
            self.p.stdin.close()
        except Exception:
            pass
        try:
            self.p.terminate()
        except Exception:
            pass


def main():
    live = "--live" in sys.argv
    print("== McTrace MCP App 自检 ==")
    print("   模式：%s" % ("真实调用麦当劳 MCP" if live else "离线样本"))

    c = Client(offline=not live)
    try:
        # ① initialize：声明 UI 扩展
        init = c.request("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {"extensions": {UI_EXT: {"mimeTypes": [UI_MIME]}}},
            "clientInfo": {"name": "mctrace-selftest", "version": "1.0"},
        })["result"]
        caps = init.get("capabilities", {})
        ext = caps.get("extensions", {})
        check("initialize 声明 io.modelcontextprotocol/ui 扩展", UI_EXT in ext, json.dumps(list(ext.keys())))
        check("扩展里给出 text/html;profile=mcp-app",
              UI_MIME in ((ext.get(UI_EXT) or {}).get("mimeTypes") or []))
        c.notify("notifications/initialized")

        # ② tools/list
        tools = c.request("tools/list")["result"]["tools"]
        names = [t["name"] for t in tools]
        check("暴露 scan_order / scan_points / open_studio",
              all(n in names for n in ("mctrace_scan_order", "mctrace_scan_points", "mctrace_open_studio")),
              ", ".join(names))
        WITH_UI = ("mctrace_launch", "mctrace_start", "mctrace_scan_order", "mctrace_scan_points")
        for t in tools:
            m = t.get("_meta", {})
            if t["name"] in WITH_UI:
                check("%s 带 _meta.ui.resourceUri" % t["name"],
                      (m.get("ui") or {}).get("resourceUri") == UI_URI)
                check("%s 带 Apps SDK 别名 openai/outputTemplate" % t["name"],
                      m.get("openai/outputTemplate") == UI_URI)
            else:
                check("%s 不挂界面（它只返回文本结论/路径）" % t["name"],
                      "ui" not in m and "ui/resourceUri" not in m)
        # 减脂/顶饱的目标参数：选错的代价是推荐出高热量餐品，必须锁住
        for tn in ("mctrace_start", "mctrace_scan_order"):
            t = next((x for x in tools if x["name"] == tn), {})
            props = ((t.get("inputSchema") or {}).get("properties") or {})
            check("%s 暴露 goal 参数（fatloss/satiety）" % tn,
                  set((props.get("goal") or {}).get("enum") or []) == {"fatloss", "satiety"},
                  str((props.get("goal") or {}).get("enum")))
        check("mctrace_start 存在（实时模式入口）", "mctrace_start" in names)
        check("mctrace_get_summary 存在（文本兜底入口）", "mctrace_get_summary" in names)

        # ①b 零参数入口：用户只提到产品名时，靠它弹出可交互界面
        lt = next((x for x in tools if x["name"] == "mctrace_launch"), None)
        check("mctrace_launch 存在（提到产品名就弹界面）", lt is not None)
        if lt:
            check("mctrace_launch 是零参数", not ((lt.get("inputSchema") or {}).get("properties")),
                  str(list(((lt.get("inputSchema") or {}).get("properties") or {}).keys())))
            check("mctrace_launch 带界面资源", ((lt.get("_meta") or {}).get("ui") or {}).get("resourceUri") == UI_URI)
        lres = c.request("tools/call", {"name": "mctrace_launch", "arguments": {}})["result"]
        lsc = lres.get("structuredContent") or {}
        check("launch 返回 launcher 视图", lsc.get("view") == "launcher", str(lsc.get("view")))
        check("launch 不带任何 trace 事件（先问再查）", not (lsc.get("events") or []))
        check("launch 声明必填字段 city/keyword",
              set(lsc.get("requiredFields") or []) == {"city", "keyword"}, str(lsc.get("requiredFields")))
        check("launch 提供两种选品目标",
              {g.get("id") for g in (lsc.get("goals") or [])} == {"fatloss", "satiety"})
        # ②b resources/templates：运行快照
        tpls = c.request("resources/templates/list")["result"]["resourceTemplates"]
        check("resources/templates/list 给出 mctrace://runs/{traceId}",
              any("mctrace://runs/" in (t.get("uriTemplate") or "") for t in tpls),
              ", ".join(t.get("uriTemplate", "") for t in tpls))

        # ③ resources/list
        res = c.request("resources/list")["result"]["resources"]
        uris = [r["uri"] for r in res]
        check("resources/list 给出 ui://mctrace/live-story", UI_URI in uris, ", ".join(uris))

        # ④ resources/read
        cts = c.request("resources/read", {"uri": UI_URI})["result"]["contents"]
        html = (cts[0] if cts else {}).get("text", "")
        check("resources/read 的 mimeType 是 %s" % UI_MIME,
              (cts[0] if cts else {}).get("mimeType") == UI_MIME)
        check("界面 HTML 非空且带 McTrace 界面标识", len(html) > 3000 and "McTraceUI" in html,
              "%d bytes" % len(html))
        for marker in ("点工具名", "点来源路径", "查看原始调用", "深度分析"):
            check("界面含「%s」入口" % marker, marker in html)

        # 启动台：零参数入口的落地视图
        for marker in ("开始查，全程摊开给我看", "我不会替你猜", "不会下单"):
            check("启动台界面含「%s」" % marker, marker in html)
        check("启动台可回退重填（再来一次）", "再来一次" in html)
        check("启动台有城市/位置必填标记", 'class="req"' in html)
        for channel in ("ui/notifications/tool-result", "window.openai.toolOutput"):
            check("界面兼容数据通道 %s" % channel, channel in html)

        # ⑤ tools/call（UI 工具）
        call = c.request("tools/call", {"name": "mctrace_scan_order",
                                        "arguments": {"keyword": "静安寺", "budget_yuan": 40,
                                                      "max_kcal": 500, "city": "上海市"}})["result"]
        check("tools/call 不是错误结果", not call.get("isError"))
        content = call.get("content", [])
        kinds = [b.get("type") for b in content]
        check("content 含可读 text", "text" in kinds)
        check("content 为纯文本（这才是用户真正看到的）", kinds == ["text"], str(kinds))
        text = "".join(b.get("text", "") for b in content if b.get("type") == "text")
        check("文本结论非空（无 UI 宿主的兜底可用）", len(text.strip()) > 20, text[:60].replace("\n", " "))
        sc = call.get("structuredContent") or {}
        evs = sc.get("events") or []
        check("structuredContent 带完整 trace 事件", len(evs) > 0, "%d events" % len(evs))
        if evs:
            e0 = evs[0]
            check("事件带 trace 契约字段", all(k in e0 for k in ("seq", "kind", "tool", "title", "status")))
            real = [e for e in evs if e.get("request") or e.get("response")]
            check("存在带原始 request/response 的真实调用步骤", len(real) > 0, "%d 步" % len(real))
            check("trace 标记为真实数据（isMock=false）", sc.get("isMock") is False)
            internal = [e for e in evs if e.get("tool") in ("user-request", "mctrace:rule", "summary-composer")]
            check("区分出本机步骤（无 request/response）", len(internal) > 0, "%d 步" % len(internal))

        # 营养覆盖率：菜单很多在售单品营养表没有条目，这个事实必须显式告诉用户
        nutev = [e for e in evs if e.get("tool") == "list-nutrition-foods"]
        cov_facts = [f for e in nutev for f in (e.get("facts") or [])
                     if f.get("key") == "coveragePct"]
        check("显式给出营养表覆盖率（不隐瞒可选集有多小）", bool(cov_facts),
              str(cov_facts[0].get("value")) if cov_facts else "(缺失)")
        # 结果卡必须写清用了哪条选品规则
        sev = [e for e in evs if e.get("tool") == "summary-composer"]
        rule_facts = [f for e in sev for f in (e.get("facts") or [])
                      if f.get("key") == "选品规则"]
        check("结果卡写明选品规则（可解释）", bool(rule_facts),
              str(rule_facts[0].get("value"))[:40] if rule_facts else "(缺失)")

        # 第二场景
        call2 = c.request("tools/call", {"name": "mctrace_scan_points", "arguments": {}})["result"]
        evs2 = (call2.get("structuredContent") or {}).get("events") or []
        check("积分盘点场景可用", len(evs2) > 0, "%d events" % len(evs2))

        # 兼容后备工具
        fallback = c.request("tools/call", {"name": "mctrace_open_studio", "arguments": {}})["result"]
        sp = (fallback.get("structuredContent") or {}).get("studioPath", "")
        check("open_studio 给出独立 Studio 路径", bool(sp), sp or "(缺失)")

        # ⑦ 实时链路：start 立即返回 → 轮询快照 → 完成
        t0 = time.time()
        st = c.request("tools/call", {"name": "mctrace_start",
                                      "arguments": {"scenario": "order", "keyword": "静安寺",
                                                    "city": "上海市", "goal": "fatloss"}})["result"]
        dt = time.time() - t0
        scs = st.get("structuredContent") or {}
        tid = scs.get("traceId") or ""
        stext = "".join(b.get("text", "") for b in st.get("content", []) if b.get("type") == "text")
        # 这台客户端不渲染 MCP App 界面 → start 必须同步跑完并把结论写进 text
        check("mctrace_start 同步跑完并返回完整 trace（无界面可等）",
              len(scs.get("events") or []) > 0 and not st.get("isError"),
              "events=%d" % len(scs.get("events") or []))
        check("返回文本含【结论】段（用户直接看这个）", "【结论】" in stext)
        check("返回文本含【过程】段（每步可读）", "【过程】" in stext)
        check("返回文本含【证据】段（字段来源可核）", "【证据】" in stext and "$." in stext)
        check("返回文本声明只读边界", "未调用任何下单" in stext)
        check("返回文本不承诺界面/按钮", ("弹出来" not in stext) and ("点按钮" not in stext)
              and ("界面上" not in stext))

        # 事件契约仍然必须成立（Trace 是产品的核心资产，与界面无关）
        seqs = [e.get("seq") for e in (scs.get("events") or [])]
        check("事件 seq 严格递增且无重复",
              len(seqs) == len(set(seqs)) and seqs == sorted(seqs), str(seqs))
        check("每个事件都带工具名与中文标题",
              all(e.get("tool") and e.get("title") for e in (scs.get("events") or [])))

        # ⑦b 缺位置必须反问，不能替用户猜城市
        #   早期 city/keyword 带默认值（上海/静安寺），用户没说自己��哪，
        #   结果"一顿思考"后给出一千公里外的门店，而且每步都 success。
        ask = c.request("tools/call", {"name": "mctrace_start",
                                       "arguments": {"goal": "fatloss"}})["result"]
        ask_sc = ask.get("structuredContent") or {}
        check("缺 city/keyword 时返回 needsClarification（不瞎猜位置）",
              bool(ask_sc.get("needsClarification")), str(ask_sc.get("missing"))[:60])
        ask_txt = "".join(b.get("text", "") for b in ask.get("content", []) if b.get("type") == "text")
        check("反问文案里问到了城市和位置", "城市" in ask_txt and "位置" in ask_txt)
        for pname in ("mctrace_start", "mctrace_scan_order"):
            t = next((x for x in tools if x["name"] == pname), {})
            props = ((t.get("inputSchema") or {}).get("properties") or {})
            check("%s 的 city/keyword 不再带默认值（杜绝瞎猜）" % pname,
                  "default" not in (props.get("city") or {})
                  and "default" not in (props.get("keyword") or {}))

        # ⑧ 文本兜底：不靠界面也能取到结论
        sm = c.request("tools/call", {"name": "mctrace_get_summary",
                                      "arguments": {"traceId": tid}})["result"]
        stext = "".join(b.get("text", "") for b in sm.get("content", []) if b.get("type") == "text")
        check("mctrace_get_summary 返回可读结论", len(stext.strip()) > 30, stext[:50].replace("\n", " "))
        bad = c.request("tools/call", {"name": "mctrace_get_summary",
                                       "arguments": {"traceId": "no-such-trace"}})["result"]
        check("未知 traceId 返回 isError 而非编造", bool(bad.get("isError")))

        # ⑥ 未知方法的错误处理
        err = c.request("tools/call", {"name": "nope", "arguments": {}})["result"]
        check("未知工具返回 isError 而非崩溃", bool(err.get("isError")))
    finally:
        c.close()

    print("\n== 结果：%d 项通过，%d 项失败 ==" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  失败：" + f)
        sys.exit(1)
    print("   全部通过。服务器侧协议无误；本客户端不渲染 MCP App 界面，产品以纯文本形态交付。")


if __name__ == "__main__":
    main()
