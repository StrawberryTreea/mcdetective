"""
麦探长 开发探针：真实只读跑一遍「静安寺早餐」场景，dump 原始响应。

用途：拿到官方实时 schema 后，再写 normalizer / rules / narrator。
仅调用只读工具，绝不下单。

用法：
  python packages/core/probe_scenario.py https://mcp.mcd.cn
Token：环境变量 MCD_TOKEN，或仓库根 token.txt（已 gitignore）。
输出：examples/raw/raw.json（已 gitignore，仅本地留档）。
"""
import os
import json
import sys

sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import McdMCPClient

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT = os.path.join(REPO, "examples", "raw", "raw.json")
TOKEN_FILE = os.environ.get("MCD_TOKEN_FILE", os.path.join(REPO, "token.txt"))


def _load_token():
    tok = os.environ.get("MCD_TOKEN")
    if tok and tok.strip():
        return tok.strip()
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, encoding="utf-8") as fh:
            return fh.read().strip()
    return None


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://mcp.mcd.cn"
    token = _load_token()
    if not token:
        print("NO_TOKEN（请设置 MCD_TOKEN 或在仓库根放置 token.txt）")
        sys.exit(2)
    c = McdMCPClient(token, url=url)
    c.initialize()
    raw = {}

    # 1) 附近门店
    raw["nearby-stores"] = c.call("query-nearby-stores", {
        "beType": 1, "searchType": 2, "city": "上海市", "keyword": "静安寺",
    })

    store_code = None
    store_name = None
    nb = raw["nearby-stores"]
    if isinstance(nb, dict) and "data" in nb:
        stores = nb["data"]
        if isinstance(stores, list) and stores:
            s0 = stores[0]
            store_code = s0.get("storeCode") or s0.get("code")
            store_name = s0.get("storeName") or s0.get("name")
    print("STORE:", store_code, store_name)

    # 2) 菜单
    raw["meals"] = c.call("query-meals", {
        "storeCode": store_code, "orderType": 1, "beType": 1,
    })

    meal_codes = []
    ml = raw["meals"]
    if isinstance(ml, dict):
        items = ml.get("data") or ml.get("items") or []
        if isinstance(items, list):
            for it in items[:6]:
                if isinstance(it, dict):
                    code = it.get("code") or it.get("itemCode")
                    name = it.get("name") or it.get("itemName")
                    if code:
                        meal_codes.append((code, name))
    print("MEALS:", meal_codes[:6])

    # 3) 营养
    raw["nutrition"] = c.call("list-nutrition-foods", {})

    # 4) 门店券
    raw["store-coupons"] = c.call("query-store-coupons", {
        "orderType": 1, "beType": 1, "storeCode": store_code,
    })

    # 5) 算价（用前 1 个餐品试 items 格式）
    items_arg = [{"code": meal_codes[0][0], "quantity": 1}] if meal_codes else []
    raw["calculate-price"] = c.call("calculate-price", {
        "storeCode": store_code, "orderType": 1, "beType": 1, "items": items_arg,
    })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print("DUMPED ->", OUT)
    cp = raw["calculate-price"]
    print("PRICE_KEYS:", list(cp.keys()) if isinstance(cp, dict) else type(cp))


if __name__ == "__main__":
    main()
