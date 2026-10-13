"""
券类工具的 Markdown 返回解析器。

背景（实测）：`available-coupons` / `query-my-coupons` 返回的不是 JSON，
而是一段 Markdown 列表：

    ### 麦麦省优惠券列表：
    - 优惠券标题：巧克力味厚松饼猪柳蛋套餐 \
      状态：已领取 \
      优惠券图片：<img src="...">
    - 优惠券标题：免费脆薯饼 \
      状态：可领取 \
      优惠券图片：<img ...>

早期版本把这类返回当作「解析失败 → 视为无券」，于是明明有「免费脆薯饼（可领取）」
却对用户说"这家店暂时没有可用券"。这是把工具返回的事实搞错了，比漏报更严重。

本模块只做**保守抽取**：认得的字段抽出来，认不出就留空，不推断。
"""


def parse_coupon_markdown(text):
    """把券类工具的 Markdown 返回解析成 [{title, status, image}]。

    返回 (coupons, meta)：
      coupons —— 列表，每项至少含 title；status 认不出时为 None
      meta    —— {'lines': 总条目数, 'parsed': 解析成功与否, 'format': 'markdown'}
    """
    meta = {"lines": 0, "parsed": False, "format": "markdown"}
    if not isinstance(text, str) or not text.strip():
        return [], meta

    out = []
    cur = None
    for raw in text.splitlines():
        ln = raw.strip()
        if not ln:
            continue
        is_new = ln.startswith("- ") or ln.startswith("* ")
        body = ln[2:].strip() if is_new else ln
        # 续行是「状态：…」/「优惠券图片：…」/ 缩进的 <img …>
        if body.startswith("状态"):
            if cur is not None:
                cur["status"] = body.split("：", 1)[-1].strip() if "：" in body else body
            continue
        if body.startswith("优惠券图片"):
            continue
        if "<img" in body:
            i = body.find('src="')
            j = body.find('"', i + 5) if i >= 0 else -1
            if cur is not None and j > i:
                cur["image"] = body[i + 5:j]
            continue
        # 其余带「键：值」形态的行：只在能确认是新条目时才起头
        if is_new or cur is None:
            if "标题" in body:
                if cur:
                    out.append(cur)
                title = body.split("：", 1)[-1].strip() if "：" in body else body
                cur = {"title": title.rstrip("\\").strip(),
                       "status": None, "image": None}
                continue
        # 不认识的续行：明确忽略，不猜
    if cur:
        out.append(cur)

    coupons = [c for c in out if c["title"]]
    meta["lines"] = len(coupons)
    meta["parsed"] = bool(coupons)
    return coupons, meta


def usable_coupons(coupons):
    """筛出「还没用掉、能直接用」的券。

    只认明确写着「可领取」/「未领取」的；其余状态一律不算可用 —— 宁可少说，
    也不能把「已领取」当成能用的券报给用户。
    """
    ok = []
    for c in coupons or []:
        st = (c.get("status") or "").strip()
        if any(k in st for k in ("可领取", "未领取", "可使用", "未使用")):
            ok.append(c)
    return ok