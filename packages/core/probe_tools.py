"""
探测麦当劳 MCP 当前真实工具清单与 inputSchema。

只为拿到事实：不调用任何写操作，只做 initialize + tools/list。
输出写入 docs/tool-inventory.json（含时间戳），供实现与文档引用。
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_client import McdMCPClient, MCD_URL, load_token  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "docs", "tool-inventory.json"))


def main():
    c = McdMCPClient(load_token(), url=MCD_URL)
    c.initialize()
    tools = c.list_tools()
    names = [t.get("name") for t in tools]
    payload = {
        "probedAt": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "endpoint": MCD_URL,
        "count": len(names),
        "names": names,
        "tools": tools,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    print("total =", len(names))
    for n in names:
        print(" -", n)


if __name__ == "__main__":
    main()
