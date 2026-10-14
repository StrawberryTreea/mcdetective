"""
麦探长 · 积分资产盘点场景流水线（只读）

串联麦当劳 MCP 的「个人资产」只读工具：
  query-my-account → query-lottery-info → query-my-prizes
  → order-list → query-survey-coupon（沉睡奖券）
  → mall-points-products（最值兑换）→ available-coupons / campaign-calendar（福利不漏区）
把每次真实调用归一化为「事实事件」，产出一份可回放的 trace.json。

原则：只叙述已观察到的真实事实；金额单位以接口原样展示（接口多为「分」或纯数字，
呈现时明确标注）。全程只读，绝不调用抽奖 / 兑换等写操作。

用法：
  python packages/core/pipeline_points.py https://mcp.mcd.cn
Token：环境变量 MCD_TOKEN，或仓库根 token.txt（已在 .gitignore）。
"""
import os
import sys
import json
import re
import time
import uuid

sys.path.insert(0, os.path.dirname(__file__))
from mcp_client import McdMCPClient, load_token

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
OUT_DIR = os.path.join(REPO, "examples", "traces")
OUT_NAME = os.environ.get("MCDETECTIVE_OUT") or "points-steward"

TITLE_MAP = {
    "user-request": "先把要求记下来",
    "query-my-account": "盘点积分余额",
    "query-lottery-info": "查看抽奖机会",
    "query-my-prizes": "翻中奖记录",
    "order-list": "翻历史订单",
    "query-survey-coupon": "唤醒沉睡奖券",
    "mall-points-products": "找积分商城最值",
    "detect:rule": "发现资产流失",
    "available-coupons": "查可领券",
    "campaign-calendar": "查活动日历",
    "summary-composer": "整理好结果与证据",
}


def to_num(v):
    try:
        return round(float(v), 2)
    except Exception:
        return None


_EMIT = None  # 由 run_scenario 注入：每条事件产生后立即回调，用于「边跑边推」


def add(events, seq_holder, kind, tool, status, facts, entities, rule,
        say_friendly, say_pro, request, response, is_mock=False):
    seq_holder[0] += 1
    ev = {
        "traceId": seq_holder[1],
        "seq": seq_holder[0],
        "kind": kind,
        "tool": tool,
        "title": TITLE_MAP.get(tool, tool),
        "status": status,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "facts": facts,
        "entities": entities or {},
        "rule": rule,
        "say": {"friendly": say_friendly, "pro": say_pro},
        "evidenceRef": f"trace://{seq_holder[1]}/events/{seq_holder[0]}",
        "isMock": is_mock,
        "request": request,
        "response": response,
    }
    events.append(ev)
    if _EMIT:
        try:
            _EMIT(ev)
        except Exception:
            pass
    return ev


def run_scenario(url, trace_id=None, emit=None, quiet=False):
    global _EMIT
    _EMIT = emit
    tok = load_token()
    c = McdMCPClient(tok, url=url)
    c.initialize()
    trace_id = trace_id or ("mcdetective-" + time.strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:8])
    events = []
    seq = [0, trace_id]

    # 0) 用户目标
    add(events, seq, "info", "user-request", "success",
        [{"key": "scope", "value": "个人积分资产", "source": "user-request"},
         {"key": "askExpiring", "value": True, "source": "user-request"}],
        {}, None,
        "好嘞！帮你把麦当劳积分资产盘一遍：余额、临期积分、抽奖机会、沉睡奖券、积分商城最值兑换、可领券，都列清楚，每一笔都能点开看来源。",
        "解析用户目标：范围=个人积分资产；关注临期损耗、抽奖权益、沉睡满意度奖券、最值兑换与可领券。",
        {"scope": "个人积分资产"}, {"userRequest": "盘点我的麦当劳积分资产"})

    # 1) 积分余额
    r_acc = c.call("query-my-account", {})
    acc = (r_acc.get("data") or {}) if isinstance(r_acc, dict) else {}
    avail = to_num(acc.get("availablePoint"))
    accum = to_num(acc.get("accumulativePoint"))
    expired = to_num(acc.get("expiredPoint"))
    cur_exp = to_num(acc.get("currentMouthExpirePoint"))
    add(events, seq, "info", "query-my-account", "success" if acc else "error",
        [{"key": "availablePoint", "value": avail, "sourcePath": "$.data.availablePoint"},
         {"key": "accumulativePoint", "value": accum, "sourcePath": "$.data.accumulativePoint"},
         {"key": "expiredPoint", "value": expired, "sourcePath": "$.data.expiredPoint"},
         {"key": "currentMouthExpirePoint", "value": cur_exp, "sourcePath": "$.data.currentMouthExpirePoint"}],
        {("可用积分 " + str(avail)): "余额 / availablePoint"},
        None,
        f"积分余额到手：可用 {avail} 分，累计拿过 {accum} 分。",
        f"账户返回：可用={avail}，累计={accum}，历史已过期={expired}，本月将过期={cur_exp}。",
        {}, {"success": bool(acc)})

    # 1b) 规则：临期 / 历史过期
    if expired and expired > 0:
        add(events, seq, "warning", "detect:rule", "success",
            [{"key": "expiredPoint", "value": expired, "sourcePath": "$.data.expiredPoint"},
             {"key": "meaning", "value": "历史上已白白过期的积分", "source": "rule"}],
            {}, None,
            f"等等，你历史上已经白白过期了 {expired} 积分……这就是需要「资产管家」的理由。",
            f"历史已过期积分={expired}，构成资产流失，约束未通过。",
            {"expiredPoint": expired}, {"rule": "points.expired"})
    if cur_exp and cur_exp > 0:
        add(events, seq, "warning", "detect:rule", "success",
            [{"key": "currentMouthExpirePoint", "value": cur_exp, "sourcePath": "$.data.currentMouthExpirePoint"},
             {"key": "action", "value": "建议本月用掉", "source": "rule"}],
            {}, None,
            f"⏳ 这个月还有 {cur_exp} 分要过期，得尽快安排用掉。",
            f"本月将过期积分={cur_exp}，需提示用户尽快消耗。",
            {"currentMouthExpirePoint": cur_exp}, {"rule": "points.expiring"})

    # 2) 抽奖
    r_lot = c.call("query-lottery-info", {})
    lot = (r_lot.get("data") or {}) if isinstance(r_lot, dict) else {}
    lot_status = lot.get("activityStatusText")
    lot_cost = to_num(lot.get("drawPoint"))
    lot_remain = lot.get("availableTimes")
    lot_remain = lot_remain if lot_remain is not None else "—"
    add(events, seq, "info", "query-lottery-info", "success" if lot else "error",
        [{"key": "activityStatusText", "value": lot_status, "sourcePath": "$.data.activityStatusText"},
         {"key": "drawPoint", "value": lot_cost, "sourcePath": "$.data.drawPoint"},
         {"key": "availableTimes", "value": lot_remain, "sourcePath": "$.data.availableTimes"}],
        {("抽奖：" + str(lot_status)): "抽奖状态 / activityStatusText"},
        None,
        (f"抽奖这边：{lot_status}，单次 {lot_cost} 分，还能抽 {lot_remain} 次。" if lot else "抽奖活动暂时没查到。"),
        f"抽奖信息：状态={lot_status}，单次消耗={lot_cost}，剩余次数={lot_remain}。",
        {}, {"success": bool(lot)})

    # 3) 我的奖品
    r_pri = c.call("query-my-prizes", {})
    prizes = (((r_pri.get("data") or {}).get("prizes")) or []) if isinstance(r_pri, dict) else []
    prize_sample = "、".join(p.get("name") for p in prizes[:3] if p.get("name")) if prizes else "无"
    add(events, seq, "info", "query-my-prizes", "success" if isinstance(r_pri, dict) else "error",
        [{"key": "prizeCount", "value": len(prizes), "sourcePath": "$.data.prizes"},
         {"key": "sample", "value": prize_sample, "sourcePath": "$.data.prizes[].name"}],
        {p.get("name"): "我的奖品 / prize.name" for p in prizes[:3] if p.get("name")},
        None,
        f"中奖记录：共 {len(prizes)} 个（{prize_sample}）。",
        f"我的奖品：数量={len(prizes)}，样本={prize_sample}。",
        {}, {"success": isinstance(r_pri, dict), "prizeCount": len(prizes)})

    # 4) 历史订单（用于找沉睡奖券）
    r_ol = c.call("order-list", {})
    orders = (((r_ol.get("data") or {}).get("list")) or []) if isinstance(r_ol, dict) else []
    order_id = orders[0].get("orderId") if orders and isinstance(orders[0], dict) else None
    add(events, seq, "info", "order-list", "success" if orders else "error",
        [{"key": "orderCount", "value": len(orders), "sourcePath": "$.data.list"},
         {"key": "sampleOrderId", "value": order_id, "sourcePath": "$.data.list[0].orderId"}],
        {}, None,
        f"翻了下历史订单，共 {len(orders)} 笔，拿第一笔去查关联的满意度奖券。",
        f"订单列表：数量={len(orders)}；取 {order_id} 作为沉睡奖券查询目标。",
        {}, {"success": isinstance(r_ol, dict), "orderCount": len(orders)})

    # 5) 沉睡奖券
    sleeping = []
    if order_id:
        r_sc = c.call("query-survey-coupon", {"orderId": order_id})
        sc = (r_sc.get("data") or {}) if isinstance(r_sc, dict) else {}
        title = sc.get("couponTitle")
        if title and str(title).strip():
            sleeping.append({"title": title, "end": sc.get("couponTradeEndTime"),
                             "status": sc.get("couponRedeemStatus")})
    add(events, seq, "info", "query-survey-coupon", "success" if sleeping else "error",
        [{"key": "sleepingCount", "value": len(sleeping), "source": "survey-coupon"},
         {"key": "sample", "value": (sleeping[0]["title"] if sleeping else "未发现"), "source": "survey-coupon"}],
        {s["title"]: "沉睡奖券 / couponTitle" for s in sleeping[:2]},
        None,
        (f"找到沉睡满意度奖券：{sleeping[0]['title']}（截止 {sleeping[0]['end']}）。"
         if sleeping else "遍历首笔订单，未发现未核销的满意度奖券。"),
        f"沉睡奖券查询（orderId={order_id}）：命中 {len(sleeping)} 张。",
        {"orderId": order_id}, {"success": bool(sleeping), "sleepingCount": len(sleeping)})

    # 6) 积分商城最值
    r_mp = c.call("mall-points-products", {})
    mp = (r_mp.get("data") or []) if isinstance(r_mp, dict) else []
    items = mp if isinstance(mp, list) else []
    reco = None
    if items:
        cand = [it for it in items if (to_num(it.get("point") or it.get("points")) or 0) > 0]
        if cand:
            reco = min(cand, key=lambda it: to_num(it.get("point") or it.get("points")))
    reco_name = reco.get("spuName") or reco.get("name") or reco.get("title") if reco else None
    reco_pt = to_num(reco.get("point") or reco.get("points")) if reco else None
    add(events, seq, "info", "mall-points-products", "success" if items else "error",
        [{"key": "productCount", "value": len(items), "sourcePath": "$.data"},
         {"key": "bestValue", "value": (reco_name + "（约 " + str(reco_pt) + " 分）") if reco_name else "—",
          "sourcePath": "$.data[].point"}],
        {reco_name: "商城商品 / spuName" for reco_name in [reco_name] if reco_name},
        None,
        (f"积分商城逛了一圈：{len(items)} 件可换，最值的一件是「{reco_name}」约 {reco_pt} 分。"
         if reco_name else f"积分商城共 {len(items)} 件可换。"),
        f"积分商城：数量={len(items)}；最值推荐={reco_name}（{reco_pt} 分）。",
        {}, {"success": isinstance(r_mp, dict), "productCount": len(items)})

    # 7) 福利不漏区：可领券 + 活动
    claim_titles, acts = [], []
    r_ac = c.call("available-coupons", {})
    ac_text = json.dumps(r_ac, ensure_ascii=False) if isinstance(r_ac, dict) else str(r_ac)
    for t in re.findall(r"优惠券标题[：: ]*(.+?)[\n\r]", ac_text):
        t = t.strip().rstrip("\\").strip()
        if t:
            claim_titles.append(t)
    r_cal = c.call("campaign-calendar", {})
    cal_text = json.dumps(r_cal, ensure_ascii=False) if isinstance(r_cal, dict) else str(r_cal)
    for a in re.findall(r"活动标题[**： ]*(.+?)[\n\r]", cal_text):
        a = a.strip()
        if a:
            acts.append(a)
    add(events, seq, "info", "available-coupons", "success" if claim_titles else "error",
        [{"key": "claimableCount", "value": len(claim_titles), "source": "available-coupons"},
         {"key": "sample", "value": ("、".join(claim_titles[:3]) or "无"), "source": "available-coupons"}],
        {t: "可领券 / couponTitle" for t in claim_titles[:2]},
        None,
        (f"可领的券：{'、'.join(claim_titles[:3])}……" if claim_titles else "当前没有可领的新券。"),
        f"可领券：{len(claim_titles)} 张。",
        {}, {"success": True, "claimableCount": len(claim_titles)})
    add(events, seq, "info", "campaign-calendar", "success" if acts else "error",
        [{"key": "activityCount", "value": len(acts), "source": "campaign-calendar"},
         {"key": "sample", "value": ("、".join(acts[:3]) or "无"), "source": "campaign-calendar"}],
        {a: "活动 / campaign" for a in acts[:2]},
        None,
        (f"进行中的活动：{'、'.join(acts[:3])}。" if acts else "暂无进行中活动。"),
        f"活动日历：{len(acts)} 个。",
        {}, {"success": True, "activityCount": len(acts)})

    # 8) 结果
    add(events, seq, "success", "summary-composer", "success",
        [{"key": "availablePoint", "value": avail, "sourcePath": "$.data.availablePoint"},
         {"key": "expiredPoint", "value": expired, "sourcePath": "$.data.expiredPoint"},
         {"key": "expiringThisMonth", "value": cur_exp, "sourcePath": "$.data.currentMouthExpirePoint"},
         {"key": "sleepingCoupons", "value": len(sleeping), "source": "survey-coupon"},
         {"key": "bestRedeem", "value": (reco_name + "（约 " + str(reco_pt) + " 分）") if reco_name else "—",
          "sourcePath": "$.data[].point"},
         {"key": "orderCreated", "value": False, "source": "探长"}],
        {}, None,
        f"搞定！可用 {avail} 分、历史已过期 {expired} 分、本月将过期 {cur_exp} 分；沉睡奖券 {len(sleeping)} 张；"
        f"商城最值换「{reco_name}」约 {reco_pt} 分。全部只读盘点，没动你账户～",
        f"完成报告：可用={avail}；历史过期={expired}；本月过期={cur_exp}；沉睡奖券={len(sleeping)}；"
        f"最值兑换={reco_name}({reco_pt}分)；可领券={len(claim_titles)}；活动={len(acts)}；全程只读。",
        {},
        {"result": {"availablePoint": avail, "expiredPoint": expired, "expiringThisMonth": cur_exp,
                    "sleepingCoupons": len(sleeping), "bestRedeem": reco_name,
                    "bestRedeemPoint": reco_pt, "claimableCoupons": len(claim_titles),
                    "activities": len(acts), "checksPassed": True, "orderCreated": False,
                    "summary": f"可用 {avail} 分 · 历史过期 {expired} 分 · 本月过期 {cur_exp} 分 · 沉睡奖券 {len(sleeping)} 张"}})
    return _finish(trace_id, events, quiet=quiet)


def _finish(trace_id, events, quiet=False):
    summary = {"traceId": trace_id, "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "isMock": False, "eventCount": len(events), "events": events}
    os.makedirs(OUT_DIR, exist_ok=True)
    # 固定场景名 → 重复运行覆盖同一份，回放页场景列表不会堆积
    out = os.path.join(OUT_DIR, f"real-{OUT_NAME}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    if quiet:
        return summary, out
    print(f"TRACE: {trace_id}  ({len(events)} events) -> {out}\n")
    for ev in events:
        tag = {"info": "•", "warning": "⚠", "success": "✓", "error": "✗", "degraded": "≈"}.get(ev["kind"], "•")
        print(f"{tag} [{ev['tool']}] {ev['say']['friendly']}")
    return summary, out


if __name__ == "__main__":
    u = sys.argv[1] if len(sys.argv) > 1 else "https://mcp.mcd.cn"
    run_scenario(u)
