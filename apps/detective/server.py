# -*- coding: utf-8 -*-
"""
麦探长在线办案服务（后端）

GET  /            → 办案页（index.html）
POST /api/patrol  → 实时巡查：解析报案 → 调用麦当劳 MCP → 渲染案卷
                     流式返回 NDJSON：progress（办案直播）/ clarify（要澄清）/ result（案卷 HTML）/ error

Token 策略（参赛合规红线）：
- **不持有、不存储、不记录任何真实 Token**。仓库、部署目录、沙箱里都没有 Token。
- 访客用自己的 MCP Token（open.mcd.cn/mcd 免费申请）跑，Token 只活在这一次请求的内存里。
- 仅调用只读工具，全程不下单、不领券、不抽奖。

纯标准库，无第三方依赖。
"""
import json
import os
import re
import sys
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for _c in (os.path.join(HERE, "packages", "core"),
           os.path.normpath(os.path.join(HERE, "..", "..", "packages", "core"))):
    if os.path.isdir(_c):
        sys.path.insert(0, _c)
        break

from case_render import render_case  # noqa: E402
from pipeline_stores import run_scenario  # noqa: E402

MCD_URL = "https://mcp.mcd.cn"
INDEX = os.path.join(HERE, "index.html")

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "苏州", "天津", "重庆", "西安",
          "长沙", "郑州", "青岛", "厦门", "福州", "合肥", "南昌", "贵阳", "昆明", "南宁", "佛山", "东莞",
          "宁波", "无锡", "大连", "沈阳", "哈尔滨", "长春", "石家庄", "太原", "济南", "温州", "黄冈", "鄂州",
          "珠海", "中山", "惠州", "汕头", "湛江", "柳州", "桂林", "海口", "三亚", "兰州", "银川", "西宁",
          "乌鲁木齐", "呼和浩特", "宜昌", "襄阳", "洛阳", "开封", "徐州", "常州", "南通", "扬州", "泰州",
          "盐城", "芜湖", "蚌埠", "遵义", "绵阳", "泸州", "唐山", "烟台", "潍坊", "临沂", "台州", "嘉兴",
          "绍兴", "金华", "湖州", "丽水", "衢州", "舟山"]

MEALS = ["精选单人餐三件套", "巨无霸三件套", "板烧鸡腿堡", "麦辣鸡腿堡", "麦辣鸡翅", "不素之霸",
         "双层深海鳕鱼堡", "安格斯厚牛堡", "培根蔬牛堡", "吉士汉堡", "麦香鱼", "巨无霸", "汉堡包",
         "薯条", "麦乐鸡", "甜筒", "麦旋风", "新地", "脆薯饼", "玉米杯", "苹果片", "三件套", "二件套",
         "单人餐", "双人餐", "套餐"]

PLACE_SUFFIX = (r"(?:路|街|巷|区|园|校区|大学|学院|广场|中心|站|门|村|镇|大厦|商场|步行街|公寓|小区|公园"
                r"|湖|山|寺|庙|塔|桥|港|岛|广场|万达|印象城|大悦城|荟聚|来福士|大融城|银泰|万象城)")
STOPWORDS = ["有什么好吃的", "有什么好吃", "有什么推荐", "有什么", "好吃的", "推荐", "请问", "请问一下",
             "帮我查", "帮我", "我想知道", "我想", "想要", "查一下", "查询", "查查", "看看", "哪家便宜",
             "哪家", "哪个", "便宜", "怎么点", "怎么", "如何", "附近", "麦当劳", "麦探长", "的餐厅",
             "餐厅", "好吃", "吃了吗", "点餐", "点单", "比价", "比较", "现在", "今天"]


def load_archive():
    """读仓库里的归档案卷（用于「只说地名没说城市」时推断城市，并明确标注是推断）。"""
    import glob
    d = next((x for x in (os.path.join(HERE, "examples", "traces"),
                          os.path.normpath(os.path.join(HERE, "..", "..", "examples", "traces")))
              if os.path.isdir(x)), "")
    out = []
    for f in glob.glob(os.path.join(d, "real-detective-*.json")):
        try:
            with open(f, encoding="utf-8") as fh:
                t = json.load(fh)
            facts = {x["key"]: x["value"] for x in t["events"][0]["facts"]}
            if facts.get("city") and facts.get("keyword"):
                out.append({"city": facts["city"], "area": facts["keyword"],
                            "target": facts.get("target", "")})
        except Exception:
            continue
    return out


ARCHIVE = load_archive()


def parse_query(raw):
    """把一句白话报案解析成 (city, area, target, understood_note)。解析不出来就诚实说要澄清什么。"""
    s = re.sub(r"\s+", "", raw or "")
    s = re.sub(r"[？?！!。，,、]", "", s)
    if not s:
        return None

    # 城市：词表命中
    city = next((c for c in CITIES if c in s), "")
    inferred = ""

    # 目标餐品：词表命中（长词优先）
    target = ""
    for m in sorted(MEALS, key=len, reverse=True):
        if m in s:
            target = m
            break

    # 区域：找「地名后缀」结尾的短语（如「北洋园」「中关村」「南京西路」）
    area = ""
    m = None
    for m in re.finditer(r"[一-龥A-Za-z0-9]{2,8}" + PLACE_SUFFIX, s):
        pass  # 取最后一个（更具体）
    if m:
        area = m.group(0)
        if city and area.startswith(city):
            area = area[len(city):]

    # 剥掉城市/区域/餐品/停用词，剩下的就是用户真正想吃的那东西
    rest = s
    for w in [city, area, target] + sorted(STOPWORDS, key=len, reverse=True):
        if w:
            rest = rest.replace(w, "")
    rest = re.sub(r"[有吗呢呀啊了的吧]+$", "", rest.strip()).strip("有")
    rest = rest.strip()

    # 餐品：词表没命中时，用剩余文本兜底（麦满分、限定款这类不必进词表）
    if not target and 2 <= len(rest) <= 14 and not re.search(r"(有|没|想|要|能|可以|什么|哪家|哪)", rest):
        target = rest
        rest = ""
    # 区域：还没定且剩余像地名，则作为区域
    if not area and 2 <= len(rest) <= 8 and not re.search(r"(有|没|想|要|能|可以|什么|哪家|哪)", rest):
        area = rest
        rest = ""

    # 没写城市 → 若地名命中归档案卷，按档案推断城市（并标注「按归档案卷推断」）
    if not city and area:
        for a in ARCHIVE:
            if area in a["area"] or a["area"] in area:
                city, inferred = a["city"], f"按归档案卷「{a['city']}·{a['area']}」推断"
                break

    return {"city": city, "area": area, "target": target,
            "inferred": inferred, "clean": rest if not area else ""}


# ---- 每 IP 限流：防止拿别人 Token 或本实例额度被刷爆 ----
_hits = {}
_lock = threading.Lock()
RATE_LIMIT = 24      # 每小时次数
RATE_WINDOW = 3600


def rate_ok(ip):
    now = time.time()
    with _lock:
        arr = [t for t in _hits.get(ip, []) if now - t < RATE_WINDOW]
        if len(arr) >= RATE_LIMIT:
            _hits[ip] = arr
            return False
        arr.append(now)
        _hits[ip] = arr
        return True


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.0"

    def log_message(self, *a):  # 静默：避免把访客请求打进日志
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/health"):
            return self._json({"ok": True, "service": "麦探长办案服务",
                               "holdsToken": bool(os.environ.get("MCD_TOKEN"))})
        if self.path.startswith("/api/need_token"):
            return self._json({"needToken": True})
        if os.path.isfile(INDEX):
            with open(INDEX, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self._json({"error": "index.html not found"}, 404)

    def do_POST(self):
        if not self.path.startswith("/api/patrol"):
            return self._json({"error": "not found"}, 404)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            req = json.loads(self.rfile.read(length) or "{}")
        except Exception:
            return self._json({"error": "bad json"}, 400)

        token = (req.get("token") or "").strip()
        radius = float(req.get("radius") or 3)
        max_stores = min(int(req.get("maxStores") or 10), 10)

        # 服务端兜底 Token（仅维护者自建实例时可用；参赛部署不带 Token）
        token = token or (os.environ.get("MCD_TOKEN") or "").strip()

        ip = self.headers.get("X-Forwarded-For", self.client_address[0] if self.client_address else "?")
        if not rate_ok(ip):
            return self._json({"error": "rate_limit",
                               "msg": "这个实例每小时最多受理 24 次巡查，稍后再来（或本地跑：README「快速开始」）"})

        parsed = parse_query(req.get("query"))
        if not parsed:
            return self._json({"error": "empty", "msg": "先说个案子，比如「中关村 精选单人餐三件套 哪家便宜」"})

        # 缺信息就诚实澄清，不瞎猜城市和餐品
        need = []
        if not parsed["city"]:
            need.append("city")
        if not parsed["target"]:
            need.append("target")
        if need and not token:
            return self._json({"error": "need_token", "need": need, "parsed": parsed,
                               "msg": "要真跑，探长需要你的 MCP Token（open.mcd.cn/mcd 免费申请）"})
        if need:
            # 有 token 也先澄清：城市/餐品缺失时跑出来的案子没有意义
            return self._json({"error": "clarify", "need": need, "parsed": parsed,
                               "msg": "探长听明白了地点，但缺一样关键信息（见下方问题）"})

        if not token:
            return self._json({"error": "need_token", "need": [],
                               "msg": "要真跑，探长需要你的 MCP Token（open.mcd.cn/mcd 免费申请，30 秒）"})

        # ---- 流式：边跑边报 ----
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

        def emit(ev):
            line = {"type": "progress", "seq": ev["seq"], "tool": ev["tool"],
                    "title": ev["title"], "kind": ev["kind"], "say": ev["say"]["friendly"]}
            self.wfile.write((json.dumps(line, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()

        t0 = time.time()
        try:
            summary, _out = run_scenario(url=MCD_URL, city=parsed["city"], keyword=parsed["area"],
                                         target=parsed["target"], radius_km=radius,
                                         max_stores=max_stores, token=token,
                                         trace_id=None, emit=emit, quiet=True)
        except Exception as e:
            msg = str(e)
            if "401" in msg or "Token" in msg or "token" in msg:
                tip = "这个 Token 麦当劳 MCP 不认（401），检查是否复制完整、是否已激活"
            else:
                tip = "巡查途中断了：" + msg[:160]
            self.wfile.write((json.dumps({"type": "error", "msg": tip}, ensure_ascii=False) + "\n").encode())
            self.wfile.flush()
            return
        summary["live"] = True
        html = render_case(summary)
        done = {"type": "result", "traceId": summary["traceId"], "events": summary["eventCount"],
                "elapsed": round(time.time() - t0, 1),
                "patrol": parsed, "html": html}
        self.wfile.write((json.dumps(done, ensure_ascii=False) + "\n").encode())
        self.wfile.flush()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"麦探长办案服务已启动 :{port}", flush=True)
    srv.serve_forever()