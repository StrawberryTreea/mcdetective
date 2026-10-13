"""
McTrace MCP App · 服务器端（stdio，纯标准库）

把 McTrace 变成一个**住在对话里的应用**，而不是把用户赶去另一个产品。

协议：MCP Apps（SEP-1865，稳定版 2026-01-26）
- 工具带 `_meta.ui.resourceUri` → `ui://mctrace/live-story`
- `resources/read` 返回 `text/html;profile=mcp-app`
- 宿主把工具结果（structuredContent，内含完整 trace）送进沙箱 iframe
- 工具**同时**返回可读文本：不支持 UI 的宿主（命令行 / 旧客户端）照样能用

同时带上 OpenAI Apps SDK 的等价字段（`openai/outputTemplate`），两种方言都兼容。

工具：
  mctrace_scan_order    场景① 点餐推荐
  mctrace_scan_points   场景② 积分资产盘点
  mctrace_open_studio   返回独立 Studio 回放页路径（兼容后备 / 深度分析入口）

用法：
  python server.py             # stdio（供 WorkBuddy 等宿主调用）
  python server.py --offline   # 不联网，用本机已有 trace 样本应答（自检 / 演示）
"""
import os
import sys
import json
import time
import uuid
import threading
import contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
for _p in (os.path.join(REPO, "packages"), os.path.join(REPO, "packages", "core"), HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

NAME = "mctrace-app"
VERSION = "1.0.0"
UI_MIME = "text/html;profile=mcp-app"
UI_URI = "ui://mctrace/live-story"
UI_EXT = "io.modelcontextprotocol/ui"
SUPPORTED_PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05", "2026-01-26"]
MCD_URL = "https://mcp.mcd.cn"

EXAMPLES = os.path.join(REPO, "examples", "traces")
PAGES = os.path.join(REPO, "examples", "pages")   # 每次调用自动生成的独立页面
STUDIO_PAGE = os.path.join(REPO, "apps", "studio", "live_story.html")

# 运行中的 trace 快照资源：Widget 走 resources/read 增量拉，不必等工具跑完
RUN_URI_TMPL = "mctrace://runs/{traceId}"
TERMINAL = ("completed", "failed", "cancelled", "unknown")


class TraceStore:
    """进程内 trace 仓库。

    状态机 queued → running → completed | failed。事件只追加、seq 单调递增，
    Widget 按 seq 去重，重复轮询不会重复渲染。
    本地 stdio 单用户场景下进程即身份边界；远程部署必须再加授权隔离。
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._runs = {}

    def create(self, trace_id, scenario, args, is_mock=False):
        with self._lock:
            self._runs[trace_id] = {
                "traceId": trace_id, "scenario": scenario, "args": args,
                "status": "queued", "isMock": is_mock,
                "createdAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "eventCount": 0, "events": [], "error": None,
            }

    def append(self, trace_id, ev):
        with self._lock:
            run = self._runs.get(trace_id)
            if run is None:
                return
            if any(e.get("seq") == ev.get("seq") for e in run["events"]):
                return  # 去重
            run["events"].append(ev)
            run["eventCount"] = len(run["events"])
            run["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            if run["status"] == "queued":
                run["status"] = "running"

    def finish(self, trace_id, summary=None):
        with self._lock:
            run = self._runs.get(trace_id)
            if run is None:
                return
            run["status"] = "completed"
            run["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            if isinstance(summary, dict) and summary.get("events"):
                run["events"] = summary["events"]
                run["eventCount"] = len(run["events"])

    def fail(self, trace_id, message):
        with self._lock:
            run = self._runs.get(trace_id)
            if run is None:
                return
            run["status"] = "failed"
            run["error"] = str(message)
            run["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            run["events"].append({
                "traceId": trace_id, "seq": len(run["events"]) + 1, "kind": "error",
                "tool": "mctrace:runner", "title": "这次没跑完", "status": "failed",
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "facts": [{"key": "error", "value": str(message), "source": "mctrace"}],
                "entities": {}, "rule": None,
                "say": {"friendly": f"跑到一半卡住了：{message}", "pro": f"Runner 失败：{message}"},
                "evidenceRef": f"trace://{trace_id}/events/error", "isMock": False,
                "request": None, "response": None,
            })
            run["eventCount"] = len(run["events"])

    def snapshot(self, trace_id):
        with self._lock:
            run = self._runs.get(trace_id)
            if run is None:
                return {"traceId": trace_id, "status": "unknown", "eventCount": 0, "events": [],
                        "error": "本进程内没有这条 trace（服务器可能已重启），请重新调用 mctrace_start。"}
            return dict(run)

# 标准字段 + Apps SDK 别名，两种宿主方言都认
UI_META = {
    "ui": {"resourceUri": UI_URI, "visibility": ["model", "app"]},
    "ui/resourceUri": UI_URI,
    "openai/outputTemplate": UI_URI,
    "openai/widgetAccessible": True,
    "openai/visibility": ["model", "app"],
}


def log(msg):
    try:
        sys.stderr.write(str(msg) + "\n")
        sys.stderr.flush()
    except Exception:
        pass


def _ui_tools():
    return [
        {
            "name": "mctrace_launch",
            "title": "打开麦搭子（麦当劳点餐追踪）",
            "description": (
                "【用户只是提到「麦搭子」「McTrace」但没说要做什么时，调这个】零参数，"
                "返回产品能做什么、怎么用、以及当前可用的场景清单。"
                "⚠️ 只在对话里给出文字说明与可选项，不要承诺弹出界面、按钮或让用户去点什么东西。"
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "_meta": UI_META,
        },
        {
            "name": "mctrace_start",
            "title": "麦当劳 · 边查边展示（实时）",
            "description": (
                "【首选】立即返回 traceId 并渲染 Live Story，后台再依次真实调用麦当劳 MCP，"
                "界面会一条条往上长出事件。适合想看过程的场景。"
                "预算与热量是硬校验；算价没返回明细时诚实标注「来源：菜单标价」而不是编造金额。"
                "全程只读，不会下单。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "scenario": {"type": "string", "enum": ["order", "points"],
                                 "description": "order=点餐推荐；points=积分资产盘点", "default": "order"},
                    "goal": {"type": "string", "enum": ["fatloss", "satiety"],
                             "description": "选品目标：fatloss=减脂低卡（约束内取热量最低的正餐）；"
                                            "satiety=常规顶饱（约束内取能量最高但不超标）。"
                                            "用户说减脂/控卡/低卡/减肥时用 fatloss，说早餐/正餐/吃饱用 satiety。",
                             "default": "satiety"},
                    "keyword": {"type": "string", "description": "位置关键词，如「静安寺」。**必填**：用户没说位置就调用会查错城市，此时应先反问用户在哪。"},
                    "city": {"type": "string", "description": "市级行政区名，如「上海市」「黄冈市」。**必填**：填错会找到几百公里外的门店。"},
                    "budget_yuan": {"type": "number", "description": "预算上限（元）"},
                    "max_kcal": {"type": "integer", "description": "热量上限（千卡）"},
                    "must_ask_if_missing": {"type": "array", "items": {"type": "string"},
                        "description": "⚠️ 缺任何一项都不要瞎猜：用户没说位置/预算/热量目标时，先反问，不要用默认值代替。",
                        "default": ["city", "keyword"]},
                },
                "required": [],
            },
            "_meta": UI_META,
        },
        {
            "name": "mctrace_scan_order",
            "title": "麦当劳点餐 · 追踪推荐过程",
            "description": (
                "按位置 / 预算 / 热量上限查麦当劳门店与餐品，并输出这次调用过程的可点击轨迹："
                "每一步用了哪个只读工具、抽出了哪些带来源的事实、约束有没有真的通过。"
                "预算与热量是硬校验；算价接口没返回明细时会诚实标注「来源：菜单标价」而不是编造金额。"
                "全程只读，不会下单。"
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "enum": ["fatloss", "satiety"],
                             "description": "选品目标：fatloss=减脂低卡；satiety=常规顶饱",
                             "default": "satiety"},
                    "keyword": {"type": "string", "description": "位置关键词，如「静安寺」。**必填**：用户没说位置就先反问。"},
                    "city": {"type": "string", "description": "市级行政区名，如「上海市」「黄冈市」。**必填**：填错会找到几百公里外的门店。"},
                    "budget_yuan": {"type": "number", "description": "预算上限（元）"},
                    "max_kcal": {"type": "integer", "description": "热量上限（千卡）"},
                    "must_ask_if_missing": {"type": "array", "items": {"type": "string"},
                        "description": "⚠️ 缺任何一项都不要瞎猜：先反问用户。",
                        "default": ["city", "keyword"]},
                },
                "required": [],
            },
            "_meta": UI_META,
        },
        {
            "name": "mctrace_scan_points",
            "title": "麦当劳积分资产 · 盘点已过期与沉睡权益",
            "description": (
                "盘点麦当劳积分资产：可用积分、历史已过期积分、本月将过期、抽奖机会、中奖记录、"
                "沉睡奖券、积分商城最值兑换、可领券与进行中活动，每一步都附原始调用证据。"
                "历史已过期积分会作为资产流失告警给出。全程只读，不消耗积分、不兑换。"
            ),
            "inputSchema": {"type": "object", "properties": {}, "required": []},
            "_meta": UI_META,
        },
    ]


def _summary_tool():
    return {
        "name": "mctrace_get_summary",
        "title": "取回某次追踪的结论",
        "description": (
            "按 traceId 取回一次追踪的当前状态与结论：已完成则返回最终结果和证据，"
            "仍在跑则返回已有事件。用于 Host 不支持界面时的文本兜底，以及取终态结论。"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "traceId": {"type": "string", "description": "mctrace_start 返回的 traceId"},
            },
            "required": ["traceId"],
        },
    }


def _studio_tool():
    return {
        "name": "mctrace_open_studio",
        "title": "打开独立 McTrace Studio（深度分析入口）",
        "description": (
            "返回本机独立 McTrace Studio 回放页的绝对路径。当前宿主不能渲染 MCP 应用界面时，"
            "用它作为兼容后备：那是自包含 HTML，双击即可离线回放同一份 trace，"
            "并支持场景切换、播放控制、载入任意 trace.json。"
        ),
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    }


class McTraceServer:
    def __init__(self, offline=False):
        self.offline = offline
        self.client_ui = False
        self.store = TraceStore()

    # ---------------- JSON-RPC 骨架 ----------------
    def handle(self, msg):
        method = msg.get("method")
        _id = msg.get("id")
        if method is None:
            return None  # 响应或无 id 的通知，不必回复
        params = msg.get("params") or {}

        if method == "initialize":
            return self._resp(_id, self._initialize(params))
        if method in ("notifications/initialized", "initialized", "notifications/cancelled"):
            return None
        if method == "ping":
            return self._resp(_id, {})
        if method == "tools/list":
            return self._resp(_id, {"tools": _ui_tools() + [_summary_tool(), _studio_tool()]})
        if method == "resources/list":
            return self._resp(_id, {"resources": self._resources()})
        if method == "resources/templates/list":
            return self._resp(_id, {"resourceTemplates": self._resource_templates()})
        if method == "resources/read":
            try:
                contents = self._read_resource(params.get("uri"))
                return self._resp(_id, {"contents": contents})
            except ValueError as e:
                return self._err(_id, -32602, str(e))
        if method == "prompts/list":
            return self._resp(_id, {"prompts": []})
        if method == "tools/call":
            return self._resp(_id, self._call_tool(params))
        return self._err(_id, -32601, "method not found: %s" % method)

    @staticmethod
    def _resp(_id, result):
        if _id is None:
            return None
        return {"jsonrpc": "2.0", "id": _id, "result": result}

    @staticmethod
    def _err(_id, code, message):
        if _id is None:
            return None
        return {"jsonrpc": "2.0", "id": _id, "error": {"code": code, "message": message}}

    # ---------------- capabilities ----------------
    def _initialize(self, params):
        proto = params.get("protocolVersion") or SUPPORTED_PROTOCOLS[0]
        caps = (params.get("capabilities") or {}).get("extensions") or {}
        self.client_ui = UI_EXT in caps
        log("[mctrace-app] client=%s protocol=%s ui_capable=%s"
            % ((params.get("clientInfo") or {}).get("name"), proto, self.client_ui))
        return {
            "protocolVersion": proto if proto in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0],
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "extensions": {UI_EXT: {"mimeTypes": [UI_MIME]}},
            },
            "serverInfo": {"name": NAME, "version": VERSION},
            "instructions": (
                "McTrace 把麦当劳 MCP 的调用过程变成可点击、可验证的轨迹。"
                "用 mctrace_scan_order 做点餐推荐、mctrace_scan_points 做积分资产盘点；"
                "两者都会返回交互界面 + 可读文本。若当前环境无法显示界面，改用 mctrace_open_studio。"
            ),
        }

    # ---------------- resources ----------------
    def _resources(self):
        return [{
            "uri": UI_URI,
            "name": "McTrace Live Story",
            "title": "McTrace 可回放轨迹界面",
            "description": "一条可逐步回放、每步都能点开原始调用证据的轨迹界面。",
            "mimeType": UI_MIME,
        }]

    def _resource_templates(self):
        return [{
            "uriTemplate": RUN_URI_TMPL,
            "name": "McTrace 运行快照",
            "title": "某次追踪的只读快照",
            "description": "Widget 增量读取它来实现「边跑边长」；status=completed 后停止轮询。",
            "mimeType": "application/json",
        }]

    def _read_resource(self, uri):
        uri = uri or ""
        # 运行快照：mctrace://runs/<traceId>
        if uri.startswith("mctrace://runs/"):
            trace_id = uri[len("mctrace://runs/"):].strip("/")
            if not trace_id:
                raise ValueError("缺少 traceId")
            snap = self.store.snapshot(trace_id)
            return [{"uri": uri, "mimeType": "application/json",
                     "text": json.dumps(snap, ensure_ascii=False)}]
        if uri != UI_URI:
            raise ValueError("未知资源：%s（只提供 %s 与 %s）" % (uri, UI_URI, RUN_URI_TMPL))
        studio = STUDIO_PAGE if os.path.exists(STUDIO_PAGE) else ""
        try:
            from build_app import render_html
            html = render_html(studio)
        except Exception as e:  # 生成失败也要给宿主一个诚实的答案
            log("[mctrace-app] 生成界面失败：%r" % (e,))
            html = ("<!DOCTYPE html><html lang=\"zh-CN\"><meta charset=\"utf-8\">"
                    "<body style=\"font:14px sans-serif;padding:16px;color:#333\">"
                    "McTrace 界面生成失败：%s</body></html>" % str(e))
        return [{"uri": UI_URI, "mimeType": UI_MIME, "text": html}]

    # ---------------- tools ----------------
    def _call_tool(self, params):
        # stdio 下 stdout 就是 JSON-RPC 通道。流水线里任何一次 print 都会把它污染成
        # 宿主无法解析的流 —— 所以这里再加一道闸门，把 stdout 临时导向 stderr。
        with contextlib.redirect_stdout(sys.stderr):
            return self._call_tool_inner(params)

    def _call_tool_inner(self, params):
        name = params.get("name")
        args = params.get("arguments") or {}
        if name in ("mctrace_start", "mctrace_scan_order"):
            if (args.get("scenario") or "order") == "order":
                missing = self._need_ask(args)
                if missing:
                    return {
                        "isError": False,   # 不是错误，是"我需要先问一句"
                        "content": [{"type": "text", "text": self.ASK_MESSAGE}],
                        "structuredContent": {"needsClarification": True, "missing": missing,
                                              "hint": "先向用户追问这些信息，拿到后再调用；不要用默认值代替"},
                    }
        if name == "mctrace_launch":
            return self._launch()
        if name == "mctrace_start":
            return self._start(args)
        if name == "mctrace_get_summary":
            return self._summary(args.get("traceId") or "")
        if name == "mctrace_open_studio":
            return self._studio_result()
        if name == "mctrace_scan_order":
            trace = self._run_now("order", args, args.get("goal") or "satiety")
        elif name == "mctrace_scan_points":
            trace = self._run_now("points", args, "satiety")
        else:
            return {"isError": True,
                    "content": [{"type": "text", "text": "未知工具：%s" % name}]}
        if isinstance(trace, dict) and trace.get("_error"):
            return {"isError": True,
                    "content": [{"type": "text", "text": trace["_error"]}]}
        return self._text_result(trace)

    # ---------------- 零参数入口：弹出可交互界面 ----------------
    LAUNCH_TEXT = (
        "麦搭子在这儿。我能做的是：真实调用麦当劳 MCP，把每一步查了什么、"
        "为什么这么选摊开给你看，全程只读、不下单。\n"
        "\n"
        "直接对我说需求就行，我会立刻去查，例如：\n"
        "  · 帮我在黄冈万达附近点份减脂晚餐，40 元以内\n"
        "  · 静安寺附近有什么早餐，30 元以内\n"
        "  · 盘点一下我的麦当劳积分资产\n"
        "\n"
        "只有一件我需要先问清楚：你在哪个城市、哪个位置附近？"
        "（不说位置我没法查，总不能随便找个城市糊弄你。）"
    )

    def _launch(self):
        return {
            "content": [{"type": "text", "text": self.LAUNCH_TEXT}],
            "structuredContent": {
                "view": "launcher", "isMock": self.offline,
                "scenarios": [
                    {"id": "order", "name": "点餐推荐",
                     "example": "帮我在{城市}{位置附近}点份{减脂晚餐|早餐}，{预算}元以内",
                     "chain": "门店 → 菜单 → 热量 → 餐品构成 → 券 → 算价"},
                    {"id": "points", "name": "积分资产盘点",
                     "example": "盘点我的麦当劳积分资产",
                     "chain": "余额 → 临期 → 抽奖 → 沉睡奖券 → 最值兑换 → 可领券"},
                ],
                "requiredFields": ["city", "keyword"],
                "goals": [
                    {"id": "fatloss", "name": "减脂 · 低卡", "rule": "约束内取热量最低的正餐单品"},
                    {"id": "satiety", "name": "常规 · 顶饱", "rule": "约束内取能量最高但不超标"},
                ],
                "readonly": True,
            },
            "isError": False,
        }

    # ---------------- 同步执行 ----------------
    # 宿主不渲染 MCP App 界面时，"立即返回 traceId + 界面自己长出来"这套是空的。
    # 所以 mctrace_start 改为**等跑完再返回**，并把完整结论写进 content 文本，
    # 让它像"一次普通的工具调用"那样在对话里直接可读。
    def _start(self, args):
        scenario = (args.get("scenario") or "order").strip()
        if scenario not in ("order", "points"):
            return {"isError": True, "content": [{"type": "text", "text": "scenario 只能是 order 或 points"}]}
        goal = args.get("goal") or "satiety"
        trace = self._run_now(scenario, args, goal)
        if isinstance(trace, dict) and trace.get("_error"):
            return {"isError": True, "content": [{"type": "text", "text": trace["_error"]}]}
        return self._text_result(trace)

    def _run_now(self, scenario, args, goal):
        """跑完整链路并返回 trace。错误以 _error 返回，不抛。"""
        if self.offline:
            key = "points-steward" if scenario == "points" else "jingan-breakfast"
            return self._sample(key)
        try:
            if scenario == "points":
                import pipeline_points
                summary, _out = pipeline_points.run_scenario(MCD_URL, quiet=True)
                return summary
            import pipeline
            req = ("帮我在%s附近点份减脂餐：预算不超过 %s 元、热量不超 %s 千卡，要低卡。"
                   % (args.get("keyword", ""), args.get("budget_yuan", 40),
                      args.get("max_kcal", 500))) if goal == "fatloss" else \
                  ("帮我在%s附近点份早餐：预算不超过 %s 元，热量别超 %s 千卡，有券就用。"
                   % (args.get("keyword", ""), args.get("budget_yuan", 40),
                      args.get("max_kcal", 500)))
            summary, _out = pipeline.run_scenario(
                MCD_URL, req,
                float(args.get("budget_yuan") or 40), int(args.get("max_kcal") or 500),
                args.get("city") or "", args.get("keyword") or "",
                goal=goal, quiet=True)
            return summary
        except SystemExit as e:
            return {"_error": "麦当劳 MCP 未配置：%s" % e}
        except Exception as e:
            return {"_error": "执行失败：%s" % e}

    # ---------------- 异步：立即返回 + 后台跑（保留给支持界面的宿主）----------------

    def _worker(self, trace_id, scenario, args):
        """后台 Runner：把每条新事件立刻写进 Store，Widget 轮询就能看到。"""
        try:
            if self.offline:
                self._worker_offline(trace_id, scenario)
                return
            if scenario == "points":
                import pipeline_points
                summary, _out = pipeline_points.run_scenario(
                    MCD_URL, trace_id=trace_id,
                    emit=lambda ev: self.store.append(trace_id, ev), quiet=True)
            else:
                import pipeline
                req = ("帮我在%s附近点份早餐：预算不超过 %s 元，热量别超 %s 千卡，有券就用。"
                       % (args.get("keyword", "静安寺"), args.get("budget_yuan", 40),
                          args.get("max_kcal", 500)))
                summary, _out = pipeline.run_scenario(
                    MCD_URL, req,
                    float(args.get("budget_yuan") or 40), int(args.get("max_kcal") or 500),
                    args.get("city") or "上海市", args.get("keyword") or "静安寺",
                    goal=args.get("goal") or "satiety",
                    trace_id=trace_id, emit=lambda ev: self.store.append(trace_id, ev), quiet=True)
            self.store.finish(trace_id, summary)
            log("[mctrace-app] %s 完成 events=%s" % (trace_id, len(summary.get("events", []))))
        except SystemExit as e:
            self.store.fail(trace_id, "麦当劳 MCP 未配置：%s" % e)
        except Exception as e:
            log("[mctrace-app] runner 异常：%r" % (e,))
            self.store.fail(trace_id, str(e))

    def _worker_offline(self, trace_id, scenario):
        """离线演示：把已存样例按 800ms 节奏吐出，明确标 isMock。

        这不是真实查询，是用来验证「轮询 + 增量渲染」这条链路的。
        """
        key = "points-steward" if scenario == "points" else "jingan-breakfast"
        p = os.path.join(EXAMPLES, "real-%s.json" % key)
        if not os.path.exists(p):
            self.store.fail(trace_id, "离线样本不存在：%s" % p)
            return
        with open(p, encoding="utf-8") as f:
            sample = json.load(f)
        for ev in sample.get("events", []):
            ev = dict(ev)
            ev["traceId"] = trace_id
            ev["isMock"] = True
            self.store.append(trace_id, ev)
            time.sleep(0.8)
        self.store.finish(trace_id)

    def _summary(self, trace_id):
        if not trace_id:
            return {"isError": True, "content": [{"type": "text", "text": "缺少 traceId"}]}
        snap = self.store.snapshot(trace_id)
        if snap.get("status") == "unknown":
            return {"isError": True, "content": [{"type": "text", "text": snap.get("error", "未知 trace")}]}
        events = snap.get("events") or []
        lines = []
        for ev in events:
            say = (ev.get("say") or {}).get("friendly") or ""
            lines.append("[%s] %s" % (ev.get("tool"), say))
        text = ("追踪 %s：状态=%s，已产生 %s 条事件\n%s"
                % (trace_id, snap.get("status"), len(events), "\n".join(lines)))
        text += "\n全程只读，未调用任何下单 / 抽奖 / 兑换写操作。"
        return {"content": [{"type": "text", "text": text}],
                "structuredContent": snap, "isError": False}

    def _studio_result(self):
        exists = os.path.exists(STUDIO_PAGE)
        text = (
            "独立 McTrace Studio 回放页：%s\n"
            "这是自包含 HTML，双击即可离线回放；支持场景切换、播放控制、载入任意 trace.json。\n"
            % (STUDIO_PAGE if exists else "（尚未生成，请先运行 build_studio.py）")
        )
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": {"studioPath": STUDIO_PAGE if exists else "", "exists": exists},
            "isError": False,
        }

    def _text_result(self, trace):
        """把整条 trace 渲染成对话里能直接读的文本。

        宿主不渲染 MCP App 界面时，这段文字就是用户唯一能看到的东西 ——
        它必须自己站得住：先结论，再过程，再证据，最后说清边界。
        """
        events = trace.get("events") or []
        goal_label = "减脂低卡" if (trace.get("goal") == "fatloss") else "常规顶饱"
        L = []
        last = events[-1] if events else {}
        res = None
        for ev in reversed(events):
            # response 就是 {"result": {...}}，不要再多取一层（这个 bug 让结论字段一直是空的）
            r = (ev.get("response") or {}).get("result")
            if isinstance(r, dict) and r.get("item"):
                res = r
                break

        # —— 结论 ——
        head = ((last.get("say") or {}).get("friendly") or "").strip()
        if head:
            L.append("【结论】" + head)
        else:
            L.append("【结论】这次没能跑出结论（详见下方过程）。")
        if res:
            for k in ("store", "item", "payableYuan", "kcal", "rule", "alternatives"):
                if k in res:
                    v = res[k]
                    if k == "alternatives" and isinstance(v, list):
                        v = "、".join(v) if v else "无"
                    L.append("  · %s：%s" % (k, v))
        L.append("")

        # —— 过程 ——
        L.append("【过程】一共 %d 步，每步都能点开看原始返回：" % len(events))
        tool_cn = {
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
        for ev in events:
            icon = {"warning": "⚠", "success": "✓", "error": "✗",
                    "degraded": "≈"}.get(ev.get("kind"), "·")
            tname = tool_cn.get(ev.get("tool"), ev.get("tool"))
            say = ((ev.get("say") or {}).get("friendly") or "").strip()
            L.append("  %s %s %s" % (icon, tname, say))

        # —— 证据 ——
        # 只列真正指向麦当劳返回字段的（sourcePath），其余是本机推导值（rule/覆盖率等），
        # 混在一起会让人分不清哪些是"平台说的"、哪些是"我们算的"。
        L.append("")
        L.append("【证据】以下数字直接取自麦当劳 MCP 的返回字段：")
        seen_src = set()
        for ev in events:
            for f in (ev.get("facts") or []):
                sp = f.get("sourcePath")
                if not sp:
                    continue
                key = (f.get("key"), sp)
                if key in seen_src:
                    continue
                seen_src.add(key)
                L.append("  · %s = %s  ← %s" % (f.get("key"), f.get("value"), sp))
        if not seen_src:
            L.append("  （本次没有直接取自返回字段的事实）")

        # —— 边界 ——
        L.append("")
        L.append("【边界】" + (
            "数据来自麦当劳 MCP 实时调用；算价没返回明细时已标注来源为菜单标价；"
            "营养表未覆盖的餐品不参与推荐。"
            if trace.get("isMock") is False else
            "⚠️ 当前是离线演示数据，不是真实查询结果。"))
        L.append("全程只读：未调用任何下单 / 抽奖 / 领券 / 兑换写操作。")
        page = self._write_page(trace)
        if trace.get("traceId"):
            L.append("追踪号 %s（可用 mctrace_get_summary 取完整轨迹）" % trace["traceId"])
        if page:
            L.append("")
            L.append("可交互回放页（双击即开，离线可用，每步都能点开看原始返回）：")
            L.append(page)
        return {
            "content": [{"type": "text", "text": "\n".join(L)}],
            "structuredContent": dict(trace, pagePath=page or ""),
            "isError": False,
        }

    @staticmethod
    def _write_page(trace):
        """把本次 trace 落成一个自包含 HTML 页面。

        这台客户端不渲染 MCP App 界面，所以"页面"就得由我们生成、自己打开。
        页面是自包含的：双击即开、离线可用、每一步都能点开看原始返回。
        """
        try:
            sys.path.insert(0, os.path.join(REPO, "packages", "core")) if \
                os.path.join(REPO, "packages", "core") not in sys.path else None
            import report
            os.makedirs(PAGES, exist_ok=True)
            name = "trace-%s.html" % (trace.get("traceId") or time.strftime("%Y%m%d-%H%M%S"))
            return report.write(trace, os.path.join(PAGES, name))
        except Exception as e:
            log("[mctrace-app] 生成页面失败：%r" % (e,))
            return ""

    def _ui_result(self, trace):
        events = trace.get("events") or []
        last = events[-1] if events else {}
        say = (last.get("say") or {}).get("friendly", "")
        bits = []
        for ev in events:
            r = ((ev.get("response") or {}).get("result")) or None
            if isinstance(r, dict) and r.get("summary"):
                bits.append(r["summary"])
        tail = bits[-1] if bits else ""
        text = " ".join(x for x in (say, tail) if x).strip()
        text += "\n全程只读，未调用任何下单 / 抽奖 / 兑换写操作。"
        return {
            "content": [
                {"type": "text", "text": text},
                {"type": "resource",
                 "resource": {"uri": UI_URI, "mimeType": UI_MIME, "title": "McTrace Live Story"}},
            ],
            "structuredContent": trace,
            "isError": False,
        }

    # ---------------- 参数校验：缺关键信息就拒绝执行 ----------------
    # 早期版本 city/keyword 带默认值（上海/静安寺），用户没说自己��哪，
    # 结果"一顿思考"后给出一千公里外的门店 —— 而且每一步都显示 success。
    # 这正是本产品批判的那类失败，却发生在自己身上。这里从代码层面堵死。
    def _need_ask(self, args):
        missing = []
        if not (args.get("city") or "").strip():
            missing.append("city（你在哪个城市？市级名字，如「上海市」「黄冈市」）")
        if not (args.get("keyword") or "").strip():
            missing.append("keyword（你在哪个位置附近？如「静安寺」「万达广场」）")
        if missing:
            return missing
        return None

    ASK_MESSAGE = (
        "我需要先确认两件事再查，否则大概率给你错的门店：\n"
        "  1. 你在哪个城市？\n"
        "  2. 你在哪个位置附近（比如地铁站、商场、写字楼）？\n"
        "你说完我就直接跑，把每一步查了什么、为什么选它摊开给你看。"
    )

    # 「减脂」「低卡」本身是宽泛诉求。工具不该替用户把话说死 ——
    # 应该在结果里显式标出"这句话我替你理解成了什么"，并把备选一起摊出来。
    ASSUMPTION_NOTE = (
        "⚠️ 你说的「%s」我没敢当成精确要求。我的理解是：%s。\n"
        "如果理解偏了，直接说，比如「我想吃热的」「不要汉堡」「我在减脂期但想吃主食」。\n"
        "下面这些备选不是我猜的，是本次菜单里真实存在的单品，你可以点着换。"
    )

    CLARIFY_HINTS = {
        "fatloss": "在预算和热量上限内，取热量最低的正餐单品（不替你决定「饱腹感」这类主观偏好）",
        "satiety": "在预算和热量上限内，取最顶饱的单品",
    }

    # ---------------- 场景数据 ----------------
    def _sample(self, key):
        p = os.path.join(EXAMPLES, "real-%s.json" % key)
        if not os.path.exists(p):
            return {"_error": "离线样本不存在：%s（请先跑一次真实流水线）" % p}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    def _trace_order(self, args):
        if self.offline:
            return self._sample("jingan-breakfast")
        try:
            import pipeline
        except Exception as e:
            return {"_error": "无法加载点餐流水线：%s" % e}
        _g = args.get("goal") or "satiety"
        req = ("帮我在%s附近点份减脂餐：预算不超过 %s 元、热量不超 %s 千卡，要低卡。"
               % (args.get("keyword", "静安寺"), args.get("budget_yuan", 40), args.get("max_kcal", 500))
               ) if _g == "fatloss" else \
              ("帮我在%s附近点份早餐：预算不超过 %s 元，热量别超 %s 千卡，有券就用。"
               % (args.get("keyword", "静安寺"), args.get("budget_yuan", 40), args.get("max_kcal", 500)))
        try:
            summary, _out = pipeline.run_scenario(
                MCD_URL, req,
                float(args.get("budget_yuan") or 40),
                int(args.get("max_kcal") or 500),
                args.get("city") or "上海市",
                args.get("keyword") or "静安寺",
                goal=args.get("goal") or "satiety",
                quiet=True,
            )
        except SystemExit as e:
            return {"_error": "麦当劳 MCP 未配置：%s" % e}
        except Exception as e:
            return {"_error": "点餐流水线执行失败：%s" % e}
        return summary

    def _trace_points(self):
        if self.offline:
            return self._sample("points-steward")
        try:
            import pipeline_points
        except Exception as e:
            return {"_error": "无法加载积分盘点流水线：%s" % e}
        try:
            summary, _out = pipeline_points.run_scenario(MCD_URL, quiet=True)
        except SystemExit as e:
            return {"_error": "麦当劳 MCP 未配置：%s" % e}
        except Exception as e:
            return {"_error": "积分盘点流水线执行失败：%s" % e}
        return summary


def main():
    offline = "--offline" in sys.argv
    # Windows 控制台可能是 GBK：明确用 UTF-8 收发 JSON-RPC
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

    srv = McTraceServer(offline=offline)
    log("[mctrace-app] 启动 offline=%s repo=%s" % (offline, REPO))
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except Exception as e:
            log("[mctrace-app] 解析失败：%s" % e)
            continue
        try:
            out = srv.handle(msg)
        except Exception as e:
            import traceback
            log("[mctrace-app] 处理异常：%s" % traceback.format_exc())
            out = {"jsonrpc": "2.0", "id": msg.get("id"),
                   "error": {"code": -32603, "message": "内部错误：%s" % e}}
        if out is None:
            continue
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
