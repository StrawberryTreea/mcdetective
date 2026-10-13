"""
McTrace · 纯标准库麦当劳 MCP 客户端（带 Trace 捕获）

设计原则（来自产品蓝图）：
- 语言模型/文案模板负责「怎么说」，MCP 数据与规则引擎负责「能说什么」。
- 本客户端只负责「抓到真实数据」：封装 initialize / tools/call，并原样记录
  每一次工具调用的 request / response / 时间戳 / 状态，供上层 normalizer 抽取事实。
- 仅调用只读工具；任何写操作（create-order / draw-lottery / mall-create-order /
  auto-bind-coupons / cancel-order 等）都必须在 McTrace 之外经用户明确确认后执行。
"""
import urllib.request
import urllib.error
import json
import time
import uuid
import os

MCD_URL = "https://mcp.mcd.cn"

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
WB_MCP = os.path.join(os.path.expanduser("~"), ".workbuddy", "mcp.json")


def load_token():
    """按优先级解析麦当劳 MCP Token：
    环境变量 MCD_TOKEN → 环境变量 MCD_TOKEN_FILE 指向的文件 → 仓库根 token.txt
    → ~/.workbuddy/mcp.json 中 mcd-mcp 连接器的 Authorization 头。
    都不存在则抛错（由调用方捕获并提示用户配置连接器）。
    """
    tok = os.environ.get("MCD_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    f = os.environ.get("MCD_TOKEN_FILE") or os.path.join(REPO, "token.txt")
    if os.path.exists(f):
        with open(f, encoding="utf-8") as fh:
            return fh.read().strip()
    if os.path.exists(WB_MCP):
        try:
            cfg = json.load(open(WB_MCP, encoding="utf-8"))
            srv = (cfg.get("mcpServers") or {}).get("mcd-mcp") or {}
            auth = ((srv.get("headers") or {}).get("Authorization") or "").strip()
            if auth:
                return auth[7:] if auth.lower().startswith("bearer ") else auth
        except Exception:
            pass
    raise SystemExit(
        "未找到麦当劳 MCP Token。请在 WorkBuddy 连接器中心配置 mcd-mcp，"
        "或在环境变量 MCD_TOKEN 中提供。"
    )


class McdMCPError(Exception):
    pass


def _balance_parse(cand):
    """从 cand[0] 起做括号配平，返回第一个完整 JSON 对象；失败返回 None。"""
    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(cand):
        if esc:
            esc = False
            continue
        if ch == "\\":
            esc = True
            continue
        if ch == '"':
            in_str = not in_str
            continue
        if in_str:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(cand[:i + 1])
                except Exception:
                    return None
    return None


def extract_json(text):
    """从 MCP tools/call 返回的 content[].text 中取出真实 JSON。

    实测返回常含：Response Structure 的 markdown 表（带伪花括号 {data[].x}）+
    '## Original Response' 标记 + 真实 JSON。策略：
    1) 优先在 '## Original Response' 之后找；
    2) 否则在每一个 '"success"' 前最近的 '{' 起做括号配平（真实 JSON 必含 success）；
    3) 退化：从第一个 '{' 起配平。
    """
    if not isinstance(text, str):
        return None
    candidates = []
    idx = text.find("## Original Response")
    if idx != -1:
        candidates.append(text[idx:])
    import re
    for m in re.finditer(r'"success"', text):
        s = text.rfind("{", 0, m.start())
        if s != -1:
            candidates.append(text[s:])
    fb = text.find("{")
    if fb != -1:
        candidates.append(text[fb:])
    for cand in candidates:
        obj = _balance_parse(cand)
        if isinstance(obj, dict):
            return obj
    return None


class McdMCPClient:
    def __init__(self, token, url=MCD_URL):
        self.url = url
        self.token = token
        self.session = None
        self._id = 0

    # ---- 底层传输 ----
    def _post(self, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        req.add_header("Authorization", f"Bearer {self.token}")
        if self.session:
            req.add_header("Mcp-Session-Id", self.session)
        try:
            resp = urllib.request.urlopen(req, timeout=45)
        except urllib.error.HTTPError as e:
            return None, e.read().decode("utf-8", "replace")[:1200], e.code
        except Exception as e:  # 网络/超时
            return None, f"{type(e).__name__}: {e}", 0
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session = sid
        raw = resp.read().decode("utf-8", "replace")
        return self._parse_sse(raw), None, resp.status

    @staticmethod
    def _parse_sse(raw):
        if not raw or not raw.strip():
            return {}
        if raw.strip().startswith("event:") or "data:" in raw:
            out = []
            for line in raw.splitlines():
                line = line.strip()
                if line.startswith("data:"):
                    out.append(line[5:].strip())
            body = "\n".join(out)
        else:
            body = raw
        try:
            return json.loads(body)
        except Exception:
            for line in body.splitlines()[::-1]:
                if line.strip().startswith("{"):
                    try:
                        return json.loads(line)
                    except Exception:
                        pass
        return {}

    # ---- MCP 握手 ----
    def initialize(self):
        self._post({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mctrace", "version": "0.1"},
            },
        })
        # initialized 通知可能返回 202 空体，忽略
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    # ---- 工具发现 ----
    def list_tools(self):
        """tools/list：拿到服务端当前真实工具名与 inputSchema。

        返回 tools 数组；失败返回 []。绝不硬编码工具清单——服务端会变。
        """
        self._id += 1
        body, err, code = self._post({
            "jsonrpc": "2.0", "id": self._id, "method": "tools/list", "params": {},
        })
        if err or not isinstance(body, dict):
            return []
        return ((body.get("result") or {}).get("tools") or [])

    # ---- 工具调用（返回工具真实数据 dict，或带 _error 的 dict）----
    def call(self, tool, arguments):
        self._id += 1
        payload = {
            "jsonrpc": "2.0", "id": self._id, "method": "tools/call",
            "params": {"name": tool, "arguments": arguments},
        }
        body, err, code = self._post(payload)
        if err:
            return {"_error": err, "_http": code, "tool": tool, "arguments": arguments}
        if not isinstance(body, dict):
            return {"_error": "bad_body", "raw": str(body)[:500]}
        result = body.get("result")
        if result is None:
            # 可能是 error 字段
            if "error" in body:
                return {"_error": "rpc_error", "detail": body["error"]}
            return {"_error": "no_result", "raw": str(body)[:500]}
        content = result.get("content", [])
        # 拼接所有 text 片段
        text_parts = []
        for blk in content:
            if isinstance(blk, dict) and blk.get("type") == "text":
                text_parts.append(blk.get("text", ""))
        text = "\n".join(text_parts)
        data = extract_json(text)
        if data is None:
            # 有些工具（available-coupons / query-my-coupons / query-lottery-info 等）
            # 返回的是 Markdown 文本而不是 JSON。丢掉它 = 把「有券」误报成「没券」，
            # 所以这里保留原文并标出格式，由上层决定怎么解析。
            return {"_raw_text": text[:4000], "_format": "markdown",
                    "parsed": False,
                    "note": "该工具返回的是 Markdown 文本而非 JSON，需专用解析器"}
        # 同样要兜住「JSON 外层包着文本」的形态
        if isinstance(data, dict) and data.get("_raw_text"):
            data["_format"] = "markdown"
            data["parsed"] = False
            data["note"] = data.get("note") or "文本型返回，需专用解析器"
        return data
