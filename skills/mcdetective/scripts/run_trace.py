"""
麦探长 · 真实查询入口：用户查什么就查什么，查完生成办案页。

⚠️ 这是**实际使用**的工具，不是演示机：
- **零参数不会自动跑任何固定案子**。没有地点就没有巡查对象——请先问用户「在哪个城市/位置附近」，
  拿到就立刻跑，绝不能拿预设案例顶替真实需求。
- 用户给了地点和餐品就直接查，不加任何默认值。

用法：
  python scripts/run_trace.py 上海市 静安寺 麦香鱼     # 城市 区域 目标餐品（正常用法）
  python scripts/run_trace.py --points                # 积分资产盘点
  python scripts/run_trace.py --order 静安寺 40 500 上海市
  python scripts/run_trace.py --demo                 # 仅调试用：跑固定案例（真实使用中禁止）

产物（写进产品运行时目录）：
  <runtime>/apps/detective/detective.html   ← **用 present_files 打开它**
  <runtime>/apps/studio/live_story.html     ← 深度回放台
  <runtime>/examples/traces/real-*.json     ← 证据样本
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from runtime import require_runtime  # noqa: E402

REPO, HOW = require_runtime()
PY = sys.executable

PIPELINE = os.path.join(REPO, "packages", "core", "pipeline.py")
PIPELINE_POINTS = os.path.join(REPO, "packages", "core", "pipeline_points.py")
PIPELINE_STORES = os.path.join(REPO, "packages", "core", "pipeline_stores.py")
STUDIO = os.path.join(REPO, "apps", "studio", "build_studio.py")
DETECTIVE = os.path.join(REPO, "apps", "detective", "build_detective.py")

URL = "https://mcp.mcd.cn"

# 仅供 --demo 调试用的固定案例；正常查询绝不会自动用它
DEMO_CASE = ["黄冈市", "黄冈万达", "麦香鱼", "3", "10"]


def run(label, cmd):
    print(f"\n==> {label}", flush=True)
    r = subprocess.run([PY] + cmd, cwd=REPO)
    if r.returncode != 0:
        print(f"（{label} 返回码 {r.returncode}）", flush=True)
    return r.returncode


def main():
    print(f"[麦探长] runtime = {REPO}  (来源: {HOW})", flush=True)
    args = sys.argv[1:]
    want_points = "--points" in args or "--all" in args
    want_detective = "--detective" in args or "--all" in args or (
        "--order" not in args and "--points" not in args and "--demo" not in args)
    want_order = "--order" in args or "--all" in args
    rest = [a for a in args if a not in ("--points", "--all", "--detective", "--order", "--demo")]

    # 场景③ 麦探长（主力）：必须有真实地点。缺参数 = 缺需求，不许拿固定案例顶替。
    if want_detective:
        if "--demo" in args:
            case = DEMO_CASE
            run("步骤 1 · 调试案例（真实使用中不应走这条）",
                [PIPELINE_STORES, URL] + case)
        elif len(rest) < 2:
            print("\n缺少地点参数。**不要**跑固定案例顶替——先问用户一句：")
            print("  「在哪个城市 / 哪个位置附近？」")
            print("拿到后执行：python scripts/run_trace.py <城市> <区域> [目标餐品]")
            return
        else:
            case = (rest + ["3", "10"])[:5]
            case[2] = case[2] or ""          # 没点菜名 → 走「在售概览」，不替他选菜
            if case[2]:
                run(f"步骤 1 · 麦探长巡查：{case[0]}{case[1]} {case[2]} 方圆{case[3]}km",
                    [PIPELINE_STORES, URL] + case)
            else:
                run(f"步骤 1 · 麦探长巡查（用户未点菜名，报在售概览）：{case[0]}{case[1]} 方圆{case[3]}km",
                    [PIPELINE_STORES, URL, case[0], case[1], "", case[3], case[4], "--mode", "recommend"])
        # 办案页：本机唯一用户可见的产物，必须生成
        run("步骤 2 · 生成麦探长办案页（接案台 + 案卷 + 证据附录）", [DETECTIVE])

    if want_order:
        kw = rest[0] if len(rest) > 0 else "静安寺"
        budget = rest[1] if len(rest) > 1 else "40"
        kcal = rest[2] if len(rest) > 2 else "500"
        city = rest[3] if len(rest) > 3 else "上海市"
        run("步骤 3 · 场景① 点餐推荐", [PIPELINE, URL, kw, budget, kcal, city])

    if want_points:
        run("步骤 4 · 场景② 积分资产盘点", [PIPELINE_POINTS, URL])

    run("步骤 5 · 生成 Live Story 深度回放台", [STUDIO])

    page = os.path.join(REPO, "apps", "detective", "detective.html")
    studio = os.path.join(REPO, "apps", "studio", "live_story.html")
    print("\n" + "=" * 64)
    print("完成。现在必须做这一步：调用 present_files 打开办案页，让用户看见结果——")
    print("  " + page)
    print("（办案页含接案台与归档案卷；深度回放台在 " + studio + "）")
    print("不要只把路径念给用户，也不要只用文字复述结论。")
    print("=" * 64)


if __name__ == "__main__":
    main()